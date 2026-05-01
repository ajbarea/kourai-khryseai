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


def _apply_filter(f, record: logging.LogRecord) -> bool | logging.LogRecord:
    """Handler.filters items may be Filter instances or plain callables; dispatch accordingly."""
    if isinstance(f, logging.Filter):
        return f.filter(record)
    return f(record)


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
        assert not all(_apply_filter(f, noisy_record) for f in console.filters)
        app_record = logging.LogRecord(
            name="hosts.cli",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="loaded",
            args=(),
            exc_info=None,
        )
        assert all(_apply_filter(f, app_record) for f in console.filters)


class TestUvicornAccessPathFilter:
    """Healthcheck access logs (Docker GET /.well-known/agent-card.json every
    15s) are pure noise; the filter drops INFO records for those paths but
    keeps WARN+ so a failed healthcheck still surfaces."""

    def _reset_root(self) -> logging.Logger:
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        # uvicorn.access filters persist across tests too — clear them.
        access = logging.getLogger("uvicorn.access")
        for f in list(access.filters):
            access.removeFilter(f)
        return root

    def _uvicorn_access_record(self, path: str, level: int = logging.INFO) -> logging.LogRecord:
        # Mirror uvicorn's emission: access_logger.info('%s - "%s %s HTTP/%s" %d', ...)
        return logging.LogRecord(
            name="uvicorn.access",
            level=level,
            pathname=__file__,
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1:1234", "GET", path, "1.1", 200),
            exc_info=None,
        )

    def test_filter_drops_healthcheck_info(self):
        from kourai_common.log import _UvicornAccessPathFilter

        flt = _UvicornAccessPathFilter(("/.well-known/agent-card.json",))
        record = self._uvicorn_access_record("/.well-known/agent-card.json")
        assert flt.filter(record) is False

    def test_filter_keeps_warning_on_healthcheck_path(self):
        """A 5xx healthcheck still surfaces — WARN+ bypass the path drop."""
        from kourai_common.log import _UvicornAccessPathFilter

        flt = _UvicornAccessPathFilter(("/.well-known/agent-card.json",))
        record = self._uvicorn_access_record("/.well-known/agent-card.json", level=logging.WARNING)
        assert flt.filter(record) is True

    def test_filter_keeps_non_healthcheck_path(self):
        from kourai_common.log import _UvicornAccessPathFilter

        flt = _UvicornAccessPathFilter(("/.well-known/agent-card.json",))
        record = self._uvicorn_access_record("/")
        assert flt.filter(record) is True

    def test_filter_keeps_other_loggers(self):
        """Records from other loggers pass through unchanged."""
        from kourai_common.log import _UvicornAccessPathFilter

        flt = _UvicornAccessPathFilter(("/.well-known/agent-card.json",))
        record = logging.LogRecord(
            name="hosts.cli",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="GET /.well-known/agent-card.json",  # same path in message text
            args=(),
            exc_info=None,
        )
        assert flt.filter(record) is True

    def test_filter_keeps_path_with_query_string(self):
        """uvicorn emits path-with-query; we match the path prefix so cache-bust
        params don't accidentally bypass the filter."""
        from kourai_common.log import _UvicornAccessPathFilter

        flt = _UvicornAccessPathFilter(("/.well-known/agent-card.json",))
        record = self._uvicorn_access_record("/.well-known/agent-card.json?ts=12345")
        assert flt.filter(record) is False

    def test_setup_logging_installs_filter_on_uvicorn_access_logger(self):
        from kourai_common.log import _UvicornAccessPathFilter

        self._reset_root()
        setup_logging("test_uvicorn_filter")

        access = logging.getLogger("uvicorn.access")
        assert any(isinstance(f, _UvicornAccessPathFilter) for f in access.filters), (
            "uvicorn.access logger missing _UvicornAccessPathFilter"
        )

    def test_setup_logging_filter_not_duplicated(self):
        """Repeated setup_logging() calls must not stack filters."""
        from kourai_common.log import _UvicornAccessPathFilter

        self._reset_root()
        setup_logging("test_one")
        setup_logging("test_two")

        access = logging.getLogger("uvicorn.access")
        installed = [f for f in access.filters if isinstance(f, _UvicornAccessPathFilter)]
        assert len(installed) == 1


class TestOtelTraceInjection:
    """Trace IDs from the active OTel span flow into formatted log lines.

    The contract is: a dev who copies a trace ID from Jaeger can grep Dozzle
    for `trace=<id>` and get the matching log lines back. Lines emitted
    outside any span context render with the bare format (no zero-padded
    trace block).
    """

    def _reset_root(self) -> logging.Logger:
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        return root

    def test_no_span_context_renders_bare_format(self, caplog):
        from io import StringIO

        from kourai_common.log import _CONSOLE_FMT, _CONSOLE_FMT_WITH_TRACE, _TraceAwareFormatter

        formatter = _TraceAwareFormatter(_CONSOLE_FMT, _CONSOLE_FMT_WITH_TRACE)
        record = logging.LogRecord(
            name="agent",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="bare line",
            args=(),
            exc_info=None,
        )
        record.otelTraceID = "0"
        out = formatter.format(record)
        assert "trace=" not in out
        assert "bare line" in out
        # Force the writer side too
        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(formatter)
        handler.emit(record)
        assert "trace=" not in buf.getvalue()

    def test_span_context_renders_trace_id(self):
        from kourai_common.log import _CONSOLE_FMT, _CONSOLE_FMT_WITH_TRACE, _TraceAwareFormatter

        formatter = _TraceAwareFormatter(_CONSOLE_FMT, _CONSOLE_FMT_WITH_TRACE)
        record = logging.LogRecord(
            name="agent",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="traced line",
            args=(),
            exc_info=None,
        )
        record.otelTraceID = "abc123def456abc123def456abc123de"
        out = formatter.format(record)
        assert "trace=abc123def456abc123def456abc123de" in out
        assert "traced line" in out

    def test_filter_injects_trace_id_when_span_active(self):
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        from kourai_common.log import _OtelTraceFilter

        # Idempotent provider set — repeated tests share the same provider.
        if not isinstance(trace.get_tracer_provider(), TracerProvider):
            trace.set_tracer_provider(TracerProvider())

        flt = _OtelTraceFilter()
        tracer = trace.get_tracer("test")

        record = logging.LogRecord(
            name="agent",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="m",
            args=(),
            exc_info=None,
        )
        flt.filter(record)
        assert getattr(record, "otelTraceID", None) == "0"

        with tracer.start_as_current_span("demo"):
            record_in = logging.LogRecord(
                name="agent",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="m",
                args=(),
                exc_info=None,
            )
            flt.filter(record_in)
            trace_id = getattr(record_in, "otelTraceID", "0")
            assert trace_id != "0"
            assert len(trace_id) == 32  # 32-char hex
            assert all(c in "0123456789abcdef" for c in trace_id)

    def test_handlers_carry_trace_filter(self):
        """Both console and file handlers must have the trace filter so
        every log line — wherever it's headed — gets `otelTraceID` populated.
        """
        from kourai_common.log import _OtelTraceFilter

        root = self._reset_root()
        setup_logging("test_handlers")

        for h in root.handlers:
            assert any(isinstance(f, _OtelTraceFilter) for f in h.filters), (
                f"handler {h!r} missing _OtelTraceFilter"
            )
