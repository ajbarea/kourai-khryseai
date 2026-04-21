"""Shared logging setup for all Kourai Khryseai agents and hosts.

Configures both console output and per-agent file logging to logs/<name>.log.
File logs use RotatingFileHandler to prevent unbounded growth.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Libs whose INFO records are noise to an end-user — they still write to the
# file log, just not the console. Covers httpx request logs and the a2a
# resolver dumping its full agent-card JSON on every connect.
_CONSOLE_SILENCED_LIBS = (
    "httpx",
    "httpcore",
    "urllib3",
    "a2a.client.card_resolver",
)


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


# Project root — two levels up from shared/src/kourai_common/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOGS_DIR = _PROJECT_ROOT / "logs"

# Shared format across all agents
_CONSOLE_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_FILE_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

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

    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root.handlers
    ):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_CONSOLE_FMT))
        console.setLevel(resolved_level)
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
        file_handler.setFormatter(logging.Formatter(_FILE_FMT))
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger
