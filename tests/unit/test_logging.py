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
        # File handler must be on the named logger, not root, so each agent
        # writes only its own records to logs/<name>.log.
        assert any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
        root = logging.getLogger()
        assert not any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    def test_respects_explicit_level(self):
        """Test that explicit level parameter is used."""
        logger = setup_logging("test_debug", level="DEBUG")
        assert logger.level == logging.DEBUG

        logger2 = setup_logging("test_warning", level="WARNING")
        assert logger2.level == logging.WARNING


class TestSetupLoggingConsoleGuard:
    """Test the console handler guard.

    The guard `if not root.handlers:` ensures the console handler is only
    added on the first call, preventing duplicate console output.
    """

    def test_guard_blocks_when_handlers_exist(self):
        """Test that guard prevents console setup when handlers already exist."""
        from unittest.mock import MagicMock

        with (
            patch("logging.getLogger") as mock_get,
            patch("kourai_common.log.RotatingFileHandler"),
        ):
            # Simulate: root already has handlers
            mock_root = MagicMock()
            mock_root.handlers = [MagicMock()]

            mock_named_logger = MagicMock()
            mock_named_logger.handlers = []
            mock_get.side_effect = [mock_root, mock_named_logger]

            setup_logging("agent")

            # When handlers is not empty, root.setLevel should NOT be called
            assert mock_root.setLevel.call_count == 0

            # But the named logger should have received the file handler
            assert mock_named_logger.addHandler.call_count == 1

    def test_guard_allows_setup_when_empty(self):
        """Test that guard allows console setup when handlers is empty."""
        # Clear root logger to simulate clean state
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        assert len(root.handlers) == 0

        # Setup should add console handler
        setup_logging("test_empty")

        # Should have added a StreamHandler (console)
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) > 0


class TestSetupLoggingLevel:
    """Test log level resolution."""

    def test_default_level_info(self):
        """Test default level is INFO."""
        with patch.dict(os.environ, {}, clear=True):
            logger = setup_logging("test_default")
            assert logger.level == logging.INFO

    def test_env_var_respected(self):
        """Test KOURAI_LOG_LEVEL environment variable is used."""
        with patch.dict(os.environ, {"KOURAI_LOG_LEVEL": "DEBUG"}):
            logger = setup_logging("test_env")
            assert logger.level == logging.DEBUG

    def test_explicit_overrides_env(self):
        """Test explicit level parameter overrides environment variable."""
        with patch.dict(os.environ, {"KOURAI_LOG_LEVEL": "DEBUG"}):
            logger = setup_logging("test_override", level="ERROR")
            assert logger.level == logging.ERROR
