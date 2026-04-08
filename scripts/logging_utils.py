"""Shared logging utilities for Kourai scripts.

Provides consistent logging across all scripts with file and console output.
"""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """Set up a logger with both console and file handlers.

    Args:
        name: Logger name (typically __name__).
        log_file: Optional log file name (without path). If provided,
            logs will be written to logs/{log_file}.

    Returns:
        Configured logger instance.
    """
    # When called as __main__, use the log file stem as the logger name
    if name == "__main__" and log_file:
        name = Path(log_file).stem

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # File handler (DEBUG level) if log file specified
    if log_file:
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_path = Path("logs") / log_path.name

        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger
