"""Tests for logging.setup_logging — stderr hygiene + rotating file handler."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

import heap_analyzer.utils.logging as log_mod
from heap_analyzer.utils.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_setup_flag():
    """Ensure each test sees a clean setup state."""
    log_mod._SETUP_DONE = False
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    yield
    log_mod._SETUP_DONE = False
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)


def test_setup_logging_writes_to_stderr_not_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Log messages must end up on stderr with nothing on stdout."""
    os.environ["HEAP_ANALYZER_LOG_DIR"] = str(tmp_path)
    try:
        setup_logging(verbose=True)
        logging.getLogger("test").info("hello-from-test")
        # Flush all handlers
        for h in logging.getLogger().handlers:
            h.flush()
    finally:
        os.environ.pop("HEAP_ANALYZER_LOG_DIR", None)

    captured = capsys.readouterr()
    assert "hello-from-test" in captured.err
    assert captured.out == ""


def test_setup_logging_creates_rotating_file(tmp_path: Path) -> None:
    """The rotating file handler writes to <log_dir>/heap-analyzer.log."""
    os.environ["HEAP_ANALYZER_LOG_DIR"] = str(tmp_path)
    try:
        setup_logging(verbose=False)
        logging.getLogger("svc").warning("rotate-me")
        for h in logging.getLogger().handlers:
            h.flush()
    finally:
        os.environ.pop("HEAP_ANALYZER_LOG_DIR", None)

    log_file = tmp_path / "heap-analyzer.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "rotate-me" in content
    assert "WARNING" in content


def test_setup_logging_is_idempotent(tmp_path: Path) -> None:
    """Calling setup_logging() twice must not attach duplicate handlers."""
    os.environ["HEAP_ANALYZER_LOG_DIR"] = str(tmp_path)
    try:
        setup_logging()
        handlers_after_first = list(logging.getLogger().handlers)
        setup_logging()
        handlers_after_second = list(logging.getLogger().handlers)
    finally:
        os.environ.pop("HEAP_ANALYZER_LOG_DIR", None)

    assert len(handlers_after_first) == len(handlers_after_second)
