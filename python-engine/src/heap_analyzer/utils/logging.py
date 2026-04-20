"""Logging utilities — all debug output goes to stderr, NEVER stdout.

Two distinct channels live here:

* **JSON Lines emit helpers** (``emit_progress`` et al.) — write structured
  messages to **stdout** consumed by the Electron parent process.
* **stderr logger + rotating file handler** (``setup_logging``) — human-readable
  logs for debugging, never on stdout.
"""

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
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


_SETUP_DONE = False


def _default_log_dir() -> Path:
    """Resolve the log directory.

    Order:
      1. ``HEAP_ANALYZER_LOG_DIR`` env var (set by Electron to userData/logs)
      2. ``~/.cache/heap-analyzer/logs`` (Windows resolves ``~`` via USERPROFILE)
    """
    env = os.environ.get("HEAP_ANALYZER_LOG_DIR")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "heap-analyzer" / "logs"


def setup_logging(verbose: bool = False) -> None:
    """Configure root logging once per process.

    Writes to **stderr** (never stdout — that's reserved for JSON Lines IPC)
    and to a rotating file handler at ``<userData>/logs/heap-analyzer.log``
    (5 MB × 3 backups).

    Idempotent: safe to call multiple times from CLI entry points.

    Args:
        verbose: If True, set root level to DEBUG; else INFO.
    """
    global _SETUP_DONE  # noqa: PLW0603
    if _SETUP_DONE:
        return

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Purge any handlers a library might have attached (e.g. bare basicConfig)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    root.addHandler(stderr_handler)

    try:
        log_dir = _default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "heap-analyzer.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # Disk / permission issue — keep stderr logging alive
        pass

    _SETUP_DONE = True


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
