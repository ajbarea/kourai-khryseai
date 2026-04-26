"""Per-session token usage accumulator across LLM calls.

Surfaces what every ``chat()`` / ``chat_with_tools()`` call costs
without forcing each agent to bring its own counter. The CLI's
``/usage`` slash command formats this into a per-agent / per-model
breakdown plus an estimated dollar total via
:mod:`kourai_common.pricing`.

Buckets are keyed on ``(agent_name, model)`` — one row per distinct
agent/model combination seen in the session. This matters because
M14's cheap-tier override means Metis's discussion runs on Haiku
while her spec generation runs on whatever the pipeline tier
resolves to (Haiku/Sonnet/Opus). With agent-only keying the first
model would have masked the second; per-(agent, model) lets `/usage`
attribute the cost honestly.

Streaming responses don't expose a ``usage`` block per chunk
(only LiteLLM's final aggregate, which we don't currently capture
from inside the iterator), so ``chat_stream()`` undercounts today.
The non-streaming ``chat`` and ``chat_with_tools`` paths cover the
substantive Techne / Kallos / Dokimasia / Hephaestus traffic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class AgentUsage:
    """Token totals for one (agent, model) pair across the live session."""

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    calls: int = 0


@dataclass
class SessionUsage:
    """All usage for the live session, keyed by ``(agent_name, model)``.

    The ``agents`` field is the dict the CLI iterates. Keys are tuples
    so multi-model scenarios (e.g. Metis running Haiku for the M14
    discussion AND Opus for the spec) get separate rows in ``/usage``
    instead of the second model silently masking the first.
    """

    agents: dict[tuple[str, str], AgentUsage] = field(default_factory=dict)


_SESSION = SessionUsage()
_LOCK = Lock()


def _coerce_int(value: object) -> int:
    """Pull a real int from a usage field, ignoring MagicMock and None.

    ``isinstance(value, int)`` excludes ``bool`` here because the bool
    subclass would silently inflate counts; we keep the strict check
    even though usage fields shouldn't ever be bool, to match
    ``_log_cache_usage`` behavior added during M4 caching work.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def record_usage(agent_name: str, response: Any, model: str = "") -> None:
    """Accumulate token counts from a LiteLLM response into the session totals.

    Mirrors the field-pulling discipline ``_log_cache_usage`` uses:
    silently no-op when ``response.usage`` is missing or any individual
    field is not a real int (so MagicMock-based unit tests don't inflate
    counters with sentinel values).

    Args:
        agent_name: Identifier the CLI uses to group lines (e.g. ``"techne"``).
        response: The LiteLLM completion response with a ``usage`` attribute.
        model: Model id for pricing lookup. Buckets are keyed on
            ``(agent_name, model)``, so calls from the same agent that
            resolve to different models (M14 cheap-tier discussion vs
            smart-tier spec) each get their own row in ``/usage``.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_tokens = _coerce_int(getattr(usage, "prompt_tokens", None))
    output_tokens = _coerce_int(getattr(usage, "completion_tokens", None))
    cache_write_tokens = _coerce_int(getattr(usage, "cache_creation_input_tokens", None))

    cache_read_tokens = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cache_read_tokens = _coerce_int(getattr(details, "cached_tokens", None))

    if (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens) == (0, 0, 0, 0):
        return

    with _LOCK:
        key = (agent_name, model or "")
        bucket = _SESSION.agents.setdefault(key, AgentUsage(model=model or ""))
        bucket.input_tokens += input_tokens
        bucket.output_tokens += output_tokens
        bucket.cache_read_tokens += cache_read_tokens
        bucket.cache_write_tokens += cache_write_tokens
        bucket.calls += 1


def get_session_usage() -> SessionUsage:
    """Return the live session totals.

    Snapshot returns the live mutable dataclass — cheap to format,
    but callers shouldn't mutate it. Use :func:`reset_session_usage`
    to clear between turns or sessions.
    """
    return _SESSION


def reset_session_usage() -> None:
    """Clear the session totals (call at REPL exit or new session boundary)."""
    with _LOCK:
        _SESSION.agents.clear()
