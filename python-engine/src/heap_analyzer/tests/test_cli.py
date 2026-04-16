"""Tests for the CLI: verifies JSON Lines protocol compliance."""

import json
import os
import shutil
import subprocess
import sys

PYTHON = sys.executable
# Use -m __main__ or the entry-point script — whichever is found
_SCRIPT = shutil.which("heap-analyzer")
CLI_BASE = [_SCRIPT] if _SCRIPT else [PYTHON, "-m", "heap_analyzer.cli"]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI with given args and return the result."""
    return subprocess.run(
        [*CLI_BASE, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


def parse_stdout_lines(stdout: str) -> list[dict[str, object]]:
    """Parse stdout as JSON Lines, returning list of parsed objects."""
    lines = [l.strip() for l in stdout.splitlines() if l.strip()]
    return [json.loads(line) for line in lines]


class TestCliJsonProtocol:
    """Verify that CLI stdout is always valid JSON Lines."""

    def test_process_dummy_inputs_outputs_only_json(self) -> None:
        """Every line of stdout must be valid JSON."""
        result = run_cli("process", "--las", "dummy.las", "--tiff", "dummy.tif", "--output", "dummy_out")
        # Must not crash (exit 0)
        assert result.returncode == 0, f"CLI crashed: {result.stderr}"
        lines = parse_stdout_lines(result.stdout)
        assert len(lines) > 0, "CLI produced no output"

    def test_every_stdout_line_has_type_field(self) -> None:
        """Every JSON object on stdout must have a 'type' field."""
        result = run_cli("process", "--las", "dummy.las", "--tiff", "dummy.tif", "--output", "dummy_out")
        lines = parse_stdout_lines(result.stdout)
        for i, obj in enumerate(lines):
            assert "type" in obj, f"Line {i} missing 'type': {obj}"

    def test_type_field_values_are_valid(self) -> None:
        """type field must be one of: progress, result, error, warning."""
        valid_types = {"progress", "result", "error", "warning"}
        result = run_cli("process", "--las", "dummy.las", "--tiff", "dummy.tif", "--output", "dummy_out")
        lines = parse_stdout_lines(result.stdout)
        for obj in lines:
            assert obj.get("type") in valid_types, f"Invalid type: {obj}"

    def test_stderr_contains_no_json(self) -> None:
        """stderr should be human-readable logs, not JSON."""
        result = run_cli("process", "--las", "dummy.las", "--tiff", "dummy.tif", "--output", "dummy_out")
        # stderr may have log lines; none should be parseable as JSON objects
        for line in result.stderr.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                # If it parsed AND has a 'type' field, that's a protocol violation
                if isinstance(parsed, dict) and "type" in parsed:
                    raise AssertionError(f"JSON with 'type' found in stderr: {line}")
            except json.JSONDecodeError:
                pass  # Expected — stderr is free text

    def test_result_message_present(self) -> None:
        """Final message must be a 'result' type."""
        result = run_cli("process", "--las", "dummy.las", "--tiff", "dummy.tif", "--output", "dummy_out")
        lines = parse_stdout_lines(result.stdout)
        result_lines = [o for o in lines if o.get("type") == "result"]
        assert len(result_lines) >= 1, "No 'result' message in output"

    def test_processing_config_defaults_match_spec(self) -> None:
        """ProcessingConfig defaults must match SPEC.md [CONFIG] exactly."""
        from heap_analyzer.config import ProcessingConfig

        cfg = ProcessingConfig()
        assert cfg.dsm_resolution == 0.10
        assert cfg.height_threshold == 0.5
        assert cfg.min_heap_area == 50.0
        assert cfg.max_heap_area == 50000.0
        assert cfg.base_percentile == 5.0
        assert cfg.morpho_kernel_size == 50

    def test_invalid_config_json_emits_error(self) -> None:
        """Passing invalid JSON to --config should emit an error message."""
        result = run_cli(
            "process", "--las", "x", "--tiff", "y", "--output", "z",
            "--config", "{not valid json}",
        )
        lines = parse_stdout_lines(result.stdout)
        error_lines = [o for o in lines if o.get("type") == "error"]
        assert len(error_lines) >= 1, "Expected error for invalid config JSON"
        assert result.returncode != 0, "Should exit non-zero on config error"

    def test_config_override_applied(self) -> None:
        """Config overrides via --config JSON must be reflected in result."""
        import json as _json

        config_json = _json.dumps({"dsm_resolution": 0.05})
        result = run_cli(
            "process", "--las", "x", "--tiff", "y", "--output", "z",
            "--config", config_json,
        )
        lines = parse_stdout_lines(result.stdout)
        result_lines = [o for o in lines if o.get("type") == "result"]
        assert result_lines, "No result message"
        last = result_lines[-1]
        data = last["data"]
        assert isinstance(data, dict)
        meta = data["metadata"]
        assert isinstance(meta, dict)
        config = meta["config"]
        assert isinstance(config, dict)
        assert config["dsm_resolution"] == 0.05
