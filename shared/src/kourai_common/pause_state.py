"""Cross-turn stash for HOTL pause classification (M17 Phase 1).

When a specialist agent pauses on a one-time-per-project preference
question (e.g. ``coverage_target``, ``python_version``), the LLM emits
a ``PAUSE: <kind> "<question>"`` token the executor parses out. This
module holds the ``(preference_kind, source_agent)`` pair keyed by
``context_id`` so the resumed turn — after the player answers — can
recover it and call ``synthesise_fact_from_pause`` to store a project-
scoped fact attributed to the right specialist.

Scope is in-process only. If the agent restarts between pause and
resume, the classification is lost; the player's answer still lands in
the per-session Memoir as labeled FL training data, so the loop fails
soft rather than silent. Cross-process persistence is a follow-on
concern (Phase 2 / M17 confidence-decay milestone).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingPause:
    """A stashed pause awaiting resolution on the next turn."""

    preference_kind: str
    source_agent: str


_pending: dict[str, PendingPause] = {}


def stash_preference_kind(
    context_id: str, preference_kind: str, source_agent: str = "metis"
) -> None:
    """Record the pause classification keyed by ``context_id``."""
    _pending[context_id] = PendingPause(preference_kind=preference_kind, source_agent=source_agent)


def pop_preference_kind(context_id: str) -> PendingPause | None:
    """Pop and return the stashed pause, or ``None`` when absent."""
    return _pending.pop(context_id, None)


def peek_preference_kind(context_id: str) -> PendingPause | None:
    """Return the stashed pause without removing it (debug / test helper)."""
    return _pending.get(context_id)


def clear() -> None:
    """Drop every pending entry — used by test fixtures for isolation."""
    _pending.clear()
