"""IPC hygiene tests — enforce JSON Lines protocol purity.

Regression guard: no print() calls in engine source code.
All output to stdout must go through emit_json/emit_result/emit_progress/emit_error/emit_warning.
"""

import re
from pathlib import Path


class TestNoPrintCalls:
    """Scan engine source for forbidden print() calls."""

    def test_no_print_calls_in_engine_source(self) -> None:
        """No bare print( in engine source (must use stderr via emit/click.echo)."""
        root = Path(__file__).resolve().parent.parent
        offenders: list[str] = []
        for py in root.rglob("*.py"):
            # Skip test files and __pycache__
            if "tests" in py.parts or "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                # Strip inline comments
                stripped = line.split("#")[0]
                # Look for bare print( calls
                if re.search(r"(?<![\w.])print\s*\(", stripped):
                    # Allow print(..., file=sys.stderr) and print(..., err=True)
                    if "file=sys.stderr" in line or "err=True" in line:
                        continue
                    # Allow the emit_json function which intentionally uses print
                    if "noqa: T201" in line:
                        continue
                    offenders.append(f"{py.relative_to(root)}:{i}: {line.strip()}")
        assert not offenders, (
            "Forbidden print() calls (use emit_* or click.echo(..., err=True)):\n"
            + "\n".join(offenders)
        )
