"""Structured JSONL emitter for tool-call audit events.

Writes one JSON object per line to ``logs/tool_events.jsonl``. Records are
also forwarded to the module logger at DEBUG so they hit stdout → Docker →
Dozzle alongside the regular agent output.

Smoke recipes grep this file directly:
``grep write_file logs/tool_events.jsonl``
— no more ``docker logs`` workaround (M15 shipping rationale).
"""

from __future__ import annotations

import json
import logging
import time
from logging.handlers import RotatingFileHandler
from typing import Any

from kourai_common.paths import logs_dir as _logs_dir

log = logging.getLogger(__name__)

# Dedicated logger for JSONL records — isolated from the root logger's
# formatters so records land as raw JSON lines, not wrapped in the
# human-readable format.
_jsonl_logger: logging.Logger | None = None

# 5 MB per file, keep 3 rotations — matches log.py's agent file handler.
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3
_MAX_ARGS_LEN = 120
_MAX_RESULT_LEN = 200


def _get_jsonl_logger() -> logging.Logger:
    """Lazy-init the JSONL file handler on first call."""
    global _jsonl_logger
    if _jsonl_logger is not None:
        return _jsonl_logger

    logger = logging.getLogger("kourai.tool_events")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # don't duplicate into root handler

    logs = _logs_dir()
    logs.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        logs / "tool_events.jsonl",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    # Raw formatter — the JSON serialization IS the format.
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    _jsonl_logger = logger
    return logger


def _summarize_args(args: dict[str, Any]) -> str:
    """One-line summary of tool arguments, truncated to ``_MAX_ARGS_LEN``."""
    parts: list[str] = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={v_str}")
    summary = " ".join(parts)
    if len(summary) > _MAX_ARGS_LEN:
        return summary[: _MAX_ARGS_LEN - 3] + "..."
    return summary


def log_tool_event(
    agent: str,
    tool: str,
    args: dict[str, Any],
    elapsed_ms: int,
    result: str,
) -> None:
    """Emit one structured JSONL record for a tool call.

    Args:
        agent: Agent name (e.g. ``"techne"``).
        tool: Tool function name (e.g. ``"write_file"``).
        args: Tool arguments dict.
        elapsed_ms: Wall-clock milliseconds the handler took.
        result: Result string — ``"ok"`` prefix or ``"ERROR: ..."`` on failure.
    """
    # Read session from the contextvar managed by log.py.
    # Import here to avoid circular import at module level.
    from kourai_common.log import get_session_id

    session = get_session_id()

    is_error = result.startswith("ERROR")
    result_summary = result[:_MAX_RESULT_LEN] if is_error else "ok"

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": session,
        "agent": agent,
        "tool": tool,
        "args": _summarize_args(args),
        "ms": elapsed_ms,
        "result": result_summary,
    }

    jsonl_logger = _get_jsonl_logger()
    jsonl_logger.info(json.dumps(record, separators=(",", ":")))

    # Mirror to the module logger for stdout/Dozzle visibility.
    log.debug(
        "tool_event session=%s agent=%s tool=%s args=%s ms=%d result=%s",
        session,
        agent,
        tool,
        _summarize_args(args),
        elapsed_ms,
        result_summary,
    )
