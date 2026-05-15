"""Pipeline state tracking — who's speaking right now in a turn.

Wraps a mutable `current_agent` reference behind a typed surface so handoff
detection, portrait routing, payload assembly, and log enrichment all read
from one canonical source instead of passing a bare string around inside a
streaming closure.

vn_bridge is the first caller (replaces the local `current_agent` variable
in `stream_response`). GUI integration — refactoring `GUIState`'s agent
fields — is intentionally deferred until a concrete pain point lands; the
ROADMAP entry calls that out as Phase 2.

Handoff hooks are NOT in this initial slice. The `on_handoff(callback)`
API is straightforward to add later when a caller appears (e.g. portrait
flash trigger on agent change). Shipping it now without a caller would be
anticipatory infra; the contract that hooks land alongside their first
consumer is more defensible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PipelineState:
    """Immutable snapshot of which agent is speaking right now."""

    current_agent: str


class PipelineTracker:
    """Mutable tracker for the current speaker in a pipeline turn.

    Each call to `handoff` replaces `state` with a NEW frozen instance
    rather than mutating in place — so callers that captured a reference
    to `state` at an earlier point keep seeing their snapshot.
    """

    __slots__ = ("_state",)

    def __init__(self, *, initial_agent: str) -> None:
        if not initial_agent:
            raise ValueError("initial_agent must be a non-empty string")
        self._state = PipelineState(current_agent=initial_agent)

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def current_agent(self) -> str:
        return self._state.current_agent

    def handoff(self, new_agent: str) -> None:
        """Switch to `new_agent`. No-op if it's already the current agent."""
        if not new_agent:
            raise ValueError("new_agent must be a non-empty string")
        if new_agent == self._state.current_agent:
            return
        self._state = PipelineState(current_agent=new_agent)
