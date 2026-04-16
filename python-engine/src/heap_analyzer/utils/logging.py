"""Logging utilities — all debug output goes to stderr, NEVER stdout."""

import json
import logging
import sys
from typing import Any


def emit_json(obj: dict[str, Any]) -> None:
    """Write a JSON Lines message to stdout.

    Args:
        obj: Dictionary with at least a 'type' key.
             type must be one of: 'progress', 'result', 'error', 'warning'.
    """
    print(json.dumps(obj, ensure_ascii=False), flush=True)  # noqa: T201 — intentional stdout


def emit_progress(phase: str, percent: float, message: str) -> None:
    """Emit a progress JSON Lines message.

    Args:
        phase: Processing phase name (e.g. 'dsm', 'dtm').
        percent: Completion percentage 0.0–100.0.
        message: Human-readable status message.
    """
    emit_json({"type": "progress", "phase": phase, "percent": percent, "message": message})


def emit_result(data: dict[str, Any]) -> None:
    """Emit a result JSON Lines message.

    Args:
        data: Result payload dictionary.
    """
    emit_json({"type": "result", "data": data})


def emit_error(code: str, message: str) -> None:
    """Emit an error JSON Lines message.

    Args:
        code: Machine-readable error code (e.g. 'CRS_MISMATCH').
        message: Human-readable error description.
    """
    emit_json({"type": "error", "code": code, "message": message})


def emit_warning(message: str) -> None:
    """Emit a warning JSON Lines message.

    Args:
        message: Human-readable warning.
    """
    emit_json({"type": "warning", "message": message})


def get_stderr_logger(name: str) -> logging.Logger:
    """Return a logger that writes to stderr only.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger writing exclusively to stderr.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
