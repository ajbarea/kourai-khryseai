"""Unit tests for kourai_common.log module.

Tests the setup_logging function, focusing on handler initialization and
the console handler guard logic.
"""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from unittest.mock import patch

import pytest

from kourai_common.log import setup_logging


@pytest.fixture(autouse=True)
def _cleanup_handlers():
    """Clean up logging handlers after each test."""
    yield
    # Clean up root logger
    root = logging.getLogger()
    for handler in root.handlers[:]:
        with suppress(Exception):
            handler.close()
        with suppress(Exception):
            root.removeHandler(handler)

    # Clean up any named loggers created during tests
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            with suppress(Exception):
                handler.close()
            with suppress(Exception):
                logger.removeHandler(handler)


class TestSetupLoggingBasic:
    """Test basic setup_logging functionality."""

    def test_returns_logger(self):
        """Test that setup_logging returns a configured logger."""
        logger = setup_logging("test_agent")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_agent"
        # File handler lives on root so records from third-party loggers
        # (httpx, a2a.*, kourai_common.audio) also land in logs/<name>.log.
        root = logging.getLogger()
        assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    def test_respects_explicit_level(self):
        """Explicit level is applied to the console handler (not the named logger,
        which stays at DEBUG so records reach the file handler)."""
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        setup_logging("test_debug", level="DEBUG")
        console = _first_console(root)
        assert console.level == logging.DEBUG

        for h in root.handlers[:]:
            root.removeHandler(h)
        setup_logging("test_warning", level="WARNING")
        console = _first_console(root)
        assert console.level == logging.WARNING


class TestSetupLoggingHandlerGuards:
    """Ensure handlers aren't duplicated across repeated setup_logging calls."""

    def test_console_handler_not_duplicated(self):
        """Console handler is added once regardless of how many times called."""
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        setup_logging("test_once")
        setup_logging("test_twice")

        stream_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert len(stream_handlers) == 1

    def test_file_handler_not_duplicated(self):
        """File handler is added once even on repeated setup."""
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        setup_logging("test_once")
        setup_logging("test_twice")

        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_setup_on_empty_root_adds_both_handlers(self):
        """Fresh root gets both console and file handlers."""
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        setup_logging("test_empty")

        assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)
        assert any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            for h in root.handlers
        )


def _first_console(root: logging.Logger) -> logging.StreamHandler:
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
            return h
    raise AssertionError("No console handler on root")


class TestSetupLoggingLevel:
    """Console handler level is the user-visible one; file handler stays at DEBUG."""

    def _reset_root(self) -> logging.Logger:
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        return root

    def test_default_level_info(self):
        with patch.dict(os.environ, {}, clear=True):
            root = self._reset_root()
            setup_logging("test_default")
            assert _first_console(root).level == logging.INFO

    def test_env_var_respected(self):
        with patch.dict(os.environ, {"KOURAI_LOG_LEVEL": "DEBUG"}):
            root = self._reset_root()
            setup_logging("test_env")
            assert _first_console(root).level == logging.DEBUG

    def test_explicit_overrides_env(self):
        with patch.dict(os.environ, {"KOURAI_LOG_LEVEL": "DEBUG"}):
            root = self._reset_root()
            setup_logging("test_override", level="ERROR")
            assert _first_console(root).level == logging.ERROR

    def test_noisy_libs_filtered_from_console_at_info(self):
        """httpx INFO records should be blocked from console but reach the file."""
        root = self._reset_root()
        setup_logging("test_filter", level="INFO")
        console = _first_console(root)
        noisy_record = logging.LogRecord(
            name="httpx",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="GET http://x",
            args=(),
            exc_info=None,
        )
        assert not all(f.filter(noisy_record) for f in console.filters)
        app_record = logging.LogRecord(
            name="hosts.cli",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="loaded",
            args=(),
            exc_info=None,
        )
        assert all(f.filter(app_record) for f in console.filters)
