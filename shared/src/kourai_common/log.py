"""Shared logging setup for all Kourai Khryseai agents and hosts.

Configures both console output and per-agent file logging to logs/<name>.log.
File logs use RotatingFileHandler to prevent unbounded growth.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from opentelemetry import trace

# Libs whose INFO records are noise to an end-user — they still write to the
# file log, just not the console. Covers httpx request logs and the a2a
# resolver dumping its full agent-card JSON on every connect.
_CONSOLE_SILENCED_LIBS = (
    "httpx",
    "httpcore",
    "urllib3",
    "a2a.client.card_resolver",
)

# 2xx access logs from these paths are pure healthcheck noise.
_HEALTHCHECK_PATHS = ("/.well-known/agent-card.json",)


class _ConsoleSilenceFilter(logging.Filter):
    """Drop low-severity records from chatty third-party loggers."""

    __slots__ = ("_prefixes",)

    def __init__(self, prefixes: tuple[str, ...]) -> None:
        super().__init__()
        self._prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        return not any(record.name == p or record.name.startswith(p + ".") for p in self._prefixes)


class _UvicornAccessPathFilter(logging.Filter):
    """Drop ``uvicorn.access`` INFO records whose path is in ``paths``.

    WARNING+ always passes (5xx healthchecks still surface). Matches
    uvicorn's emission shape — ``record.args[2]`` is path-with-query.
    """

    __slots__ = ("_paths",)

    def __init__(self, paths: tuple[str, ...]) -> None:
        super().__init__()
        self._paths = paths

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        if record.name != "uvicorn.access":
            return True
        if not record.args or len(record.args) < 3:
            return True
        path = record.args[2]
        if not isinstance(path, str):
            return True
        path_only = path.split("?", 1)[0]
        return path_only not in self._paths


# Project root — two levels up from shared/src/kourai_common/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOGS_DIR = _PROJECT_ROOT / "logs"

# Shared format across all agents. The `_WITH_TRACE` variant is used by
# `_TraceAwareFormatter` when an OTel span context is active on the record;
# otherwise the plain variant is used to avoid 32 zeros of noise on
# non-traced lines. Trace IDs are emitted as full 32-char hex so a dev can
# copy a trace ID from Jaeger and grep Dozzle for the matching log lines.
_CONSOLE_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_CONSOLE_FMT_WITH_TRACE = (
    "%(asctime)s [%(name)s] %(levelname)s [trace=%(otelTraceID)s]: %(message)s"
)
_FILE_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_FILE_FMT_WITH_TRACE = "%(asctime)s [%(name)s] %(levelname)s [trace=%(otelTraceID)s]: %(message)s"


class _OtelTraceFilter(logging.Filter):
    """Inject `otelTraceID` / `otelSpanID` from the current OTel span.

    Reads `trace.get_current_span()` directly rather than going through
    `opentelemetry-instrumentation-logging`, whose factory only injects
    these attrs when `set_logging_format=True` (which would also call
    `logging.basicConfig` and clash with this module's explicit handler
    setup). Always returns True; `_TraceAwareFormatter` decides whether
    to render the values.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.trace_id:
            record.otelTraceID = format(ctx.trace_id, "032x")
            record.otelSpanID = format(ctx.span_id, "016x")
        else:
            record.otelTraceID = "0"
            record.otelSpanID = "0"
        return True


class _TraceAwareFormatter(logging.Formatter):
    """Switch between two format strings per-record based on trace presence.

    `_OtelTraceFilter` sets `record.otelTraceID` to a 32-char hex string
    when a span is active and to "0" otherwise. Embedding the trace block
    on every non-traced line is visually noisy; we keep it only when it
    carries signal.
    """

    def __init__(self, fmt_no_trace: str, fmt_with_trace: str) -> None:
        super().__init__(fmt_no_trace)
        self._fmt_no_trace = fmt_no_trace
        self._fmt_with_trace = fmt_with_trace

    def format(self, record: logging.LogRecord) -> str:
        trace_id = getattr(record, "otelTraceID", "0")
        if trace_id and trace_id != "0":
            self._style._fmt = self._fmt_with_trace
        else:
            self._style._fmt = self._fmt_no_trace
        return super().format(record)


# 5 MB per file, keep 3 rotations
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3


def setup_logging(name: str, *, level: str | None = None) -> logging.Logger:
    """Configure console + file logging for an agent or host.

    Args:
        name: Agent or host name (e.g. "hephaestus", "gui"). Used for
              the log filename and as the root logger name.
        level: Override log level. Falls back to KOURAI_LOG_LEVEL env var,
               then INFO.

    Returns:
        A configured logger for the caller.
    """
    resolved_level = level if level is not None else os.getenv("KOURAI_LOG_LEVEL", "INFO")

    # Attach handlers to the root logger so records from every module
    # (httpx, a2a.*, kourai_common.*, etc.) land in logs/<name>.log — not just
    # records emitted through the `name` logger.
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything at root; handlers filter.

    trace_filter = _OtelTraceFilter()

    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root.handlers
    ):
        console = logging.StreamHandler()
        console.setFormatter(_TraceAwareFormatter(_CONSOLE_FMT, _CONSOLE_FMT_WITH_TRACE))
        console.setLevel(resolved_level)
        console.addFilter(trace_filter)
        # Verbose mode (-v / KOURAI_LOG_LEVEL=DEBUG) keeps everything; otherwise
        # drop 3rd-party INFO chatter from the terminal (still logged to file).
        if console.level > logging.DEBUG:
            console.addFilter(_ConsoleSilenceFilter(_CONSOLE_SILENCED_LIBS))
        root.addHandler(console)

    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOGS_DIR / f"{name}.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(_TraceAwareFormatter(_FILE_FMT, _FILE_FMT_WITH_TRACE))
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(trace_filter)
        root.addHandler(file_handler)

    # Logger-level install (not handler) so it applies regardless of which
    # handler emits — uvicorn configures its own StreamHandler outside root.
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _UvicornAccessPathFilter) for f in access_logger.filters):
        access_logger.addFilter(_UvicornAccessPathFilter(_HEALTHCHECK_PATHS))

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger
