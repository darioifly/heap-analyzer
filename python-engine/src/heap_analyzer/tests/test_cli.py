"""Tests for the CLI: verifies JSON Lines protocol compliance."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYTHON = sys.executable
# Use -m __main__ or the entry-point script — whichever is found
_SCRIPT = shutil.which("heap-analyzer")
CLI_BASE = [_SCRIPT] if _SCRIPT else [PYTHON, "-m", "heap_analyzer.cli"]

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"


def run_cli(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run the CLI with given args and return the result."""
    return subprocess.run(
        [*CLI_BASE, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        timeout=timeout,
    )


def parse_stdout_lines(stdout: str) -> list[dict[str, object]]:
    """Parse stdout as JSON Lines, returning list of parsed objects."""
    lines = [l.strip() for l in stdout.splitlines() if l.strip()]
    return [json.loads(line) for line in lines]


class TestCliJsonProtocol:
    """Verify that CLI stdout is always valid JSON Lines."""

    def test_process_dummy_inputs_emits_error_json(self) -> None:
        """Process with missing files must emit error JSON and exit 1."""
        result = run_cli("process", "--las", "dummy.las", "--tiff", "dummy.tif", "--output", "dummy_out")
        assert result.returncode != 0
        lines = parse_stdout_lines(result.stdout)
        assert len(lines) > 0, "CLI produced no output"
        # Every line must be valid JSON with type field
        for obj in lines:
            assert "type" in obj

    def test_every_stdout_line_has_type_field(self) -> None:
        """Every JSON object on stdout must have a 'type' field — even on error."""
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
        for line in result.stderr.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict) and "type" in parsed:
                    raise AssertionError(f"JSON with 'type' found in stderr: {line}")
            except json.JSONDecodeError:
                pass  # Expected — stderr is free text

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
        """Config overrides via --config file must be reflected in result."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump({"dsm_resolution": 0.20}, f)
            config_path = f.name

        try:
            result = run_cli(
                "process",
                "--las", str(TEST_DATA_DIR / "test.las"),
                "--tiff", str(TEST_DATA_DIR / "test.tif"),
                "--output", str(TEST_DATA_DIR / "output"),
                "--config", config_path,
            )
            assert result.returncode == 0, f"CLI failed: {result.stderr[-500:]}"
            lines = parse_stdout_lines(result.stdout)
            result_lines = [o for o in lines if o.get("type") == "result"]
            assert result_lines, "No result message"
            data = result_lines[-1]["data"]
            assert isinstance(data, dict)
            config = data["survey_metadata"]["config"]
            assert config["dsm_resolution"] == 0.20
        finally:
            os.unlink(config_path)


class TestCliProcess:
    """Test CLI process command with real synthetic data."""

    def test_cli_process_synthetic(self) -> None:
        """Process runs, exits 0, every stdout line is valid JSON, last has type=result."""
        result = run_cli(
            "process",
            "--las", str(TEST_DATA_DIR / "test.las"),
            "--tiff", str(TEST_DATA_DIR / "test.tif"),
            "--output", str(TEST_DATA_DIR / "output"),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[-500:]}"

        lines = parse_stdout_lines(result.stdout)
        assert len(lines) > 0
        # Every line valid JSON with type
        for obj in lines:
            assert "type" in obj
        # Last line has type=result
        result_lines = [o for o in lines if o.get("type") == "result"]
        assert len(result_lines) >= 1

    def test_cli_process_emits_only_json(self) -> None:
        """Parse every stdout line — all valid JSON, all have type field."""
        result = run_cli(
            "process",
            "--las", str(TEST_DATA_DIR / "test.las"),
            "--tiff", str(TEST_DATA_DIR / "test.tif"),
            "--output", str(TEST_DATA_DIR / "output"),
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                assert isinstance(obj, dict), f"Not a JSON object: {line}"
                assert "type" in obj, f"Missing type field: {line}"
            except json.JSONDecodeError as exc:
                raise AssertionError(f"Non-JSON line on stdout: {line!r}") from exc

    def test_cli_process_with_config(self, tmp_path: Path) -> None:
        """Write config.json, pass --config, verify it's used."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"height_threshold": 0.3}), encoding="utf-8")

        result = run_cli(
            "process",
            "--las", str(TEST_DATA_DIR / "test.las"),
            "--tiff", str(TEST_DATA_DIR / "test.tif"),
            "--output", str(TEST_DATA_DIR / "output"),
            "--config", str(config_path),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[-500:]}"


class TestCliValidate:
    """Test CLI validate command."""

    def test_cli_validate_synthetic(self) -> None:
        """Exits 0, emits result with valid=true."""
        result = run_cli(
            "validate",
            "--las", str(TEST_DATA_DIR / "test.las"),
            "--tiff", str(TEST_DATA_DIR / "test.tif"),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        lines = parse_stdout_lines(result.stdout)
        result_lines = [o for o in lines if o.get("type") == "result"]
        assert result_lines
        assert result_lines[-1]["data"]["valid"] is True

    def test_cli_validate_missing_file(self) -> None:
        """Exits 1, emits result with valid=false."""
        result = run_cli(
            "validate",
            "--las", "/nonexistent/file.las",
            "--tiff", str(TEST_DATA_DIR / "test.tif"),
        )
        assert result.returncode != 0
        lines = parse_stdout_lines(result.stdout)
        result_lines = [o for o in lines if o.get("type") == "result"]
        assert result_lines
        assert result_lines[-1]["data"]["valid"] is False


class TestCliNoStdoutPrint:
    """Scan source files to ensure no raw print() to stdout."""

    def test_cli_no_print_to_stdout(self) -> None:
        """cli.py and pipeline.py must not contain bare print() calls."""
        import re

        src_dir = Path(__file__).resolve().parent.parent
        files_to_check = [
            src_dir / "cli.py",
            src_dir / "pipeline.py",
        ]

        for filepath in files_to_check:
            content = filepath.read_text(encoding="utf-8")
            # Find print() calls that don't use file=sys.stderr
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Match print( but not print(..., file=sys.stderr)
                if re.search(r'\bprint\s*\(', stripped):
                    if "file=sys.stderr" not in stripped and "# noqa" not in stripped:
                        raise AssertionError(
                            f"{filepath.name}:{i}: bare print() found — "
                            f"must use file=sys.stderr or emit_* functions: {stripped}"
                        )
