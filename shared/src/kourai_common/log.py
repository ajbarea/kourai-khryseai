"""Shared logging setup for all Kourai Khryseai agents and hosts.

Configures both console output and per-agent file logging to logs/<name>.log.
File logs use RotatingFileHandler to prevent unbounded growth.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

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
    resolved_level = level or os.getenv("KOURAI_LOG_LEVEL", "INFO")

    # Root logger — console handler (only if none exist yet)
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(resolved_level)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_CONSOLE_FMT))
        root.addHandler(console)

    # Per-agent file handler
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _LOGS_DIR / f"{name}.log"

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_FILE_FMT))
    file_handler.setLevel(resolved_level)
    root.addHandler(file_handler)

    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    return logger
