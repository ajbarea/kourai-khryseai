"""A2A event processing — status extraction and maiden-ification.

Transforms raw A2A task events into Golden Maiden comms-window dialogue,
detecting agent transitions and playing handoff chatter.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from hosts.cli.maidens import (
    _EMOJI_TO_MAIDEN,
    _HANDOFF_GENERIC,
    _HANDOFF_LINES,
    _VICTORY_LINES,
)
from hosts.cli.rendering import _comms_window, _echo

if TYPE_CHECKING:
    from a2a.types import TaskArtifactUpdateEvent, TaskStatusUpdateEvent

# Track pipeline flow state for comms rendering
_last_seen_agent: str = ""


def reset_last_seen_agent() -> None:
    """Reset the pipeline tracking state (call at start of each run)."""
    global _last_seen_agent
    _last_seen_agent = ""


def get_last_seen_agent() -> str:
    """Return the name of the last agent seen in the pipeline."""
    return _last_seen_agent


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------
def _extract_status_text(event: TaskStatusUpdateEvent) -> str:
    """Pull display text from a status update event."""
    if event.status.message and hasattr(event.status.message, "parts"):
        parts = [p.root.text for p in event.status.message.parts if hasattr(p.root, "text")]
        if parts:
            return "\n".join(parts)
    return ""


def _extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull display text from an artifact update event."""
    if event.artifact and event.artifact.parts:
        return "\n".join(p.root.text for p in event.artifact.parts if hasattr(p.root, "text"))
    return ""


def _handoff_chatter(from_agent: str, to_agent: str) -> str | None:
    """Get a random handoff line when one maiden passes to another."""
    key = (from_agent.lower(), to_agent.lower())
    lines = _HANDOFF_LINES.get(key) or _HANDOFF_GENERIC.get(from_agent.lower())
    if lines:
        return secrets.choice(lines)
    return None


def _victory_chatter(last_agent: str) -> str | None:
    """Get a random victory line from the last maiden in the pipeline.

    Victory lines already include user-directed flirty energy — the maidens
    celebrate for the user, not for Hephaestus. He's just... there.
    """
    lines = _VICTORY_LINES.get(last_agent.lower())
    if lines:
        return secrets.choice(lines)
    return None


def _maidenify_status(text: str) -> str:
    """Replace agent emoji prefixes with full comms-window dialogue.

    Detects agent transitions and plays handoff chatter — like watching
    mecha pilots banter as they tag in and out of combat.
    """
    global _last_seen_agent

    for emoji, (agent_name, _face) in _EMOJI_TO_MAIDEN.items():
        if text.lstrip().startswith(emoji):
            status_msg = text.replace(emoji, "", 1).strip()

            # Detect agent switch → handoff chatter (pilot comms transition)
            if _last_seen_agent and _last_seen_agent != agent_name:
                handoff = _handoff_chatter(_last_seen_agent, agent_name)
                if handoff:
                    # Outgoing maiden's parting shot
                    _echo(_comms_window(_last_seen_agent, handoff, style="whisper"))
                    _echo("")  # breathing room

            _last_seen_agent = agent_name

            # Incoming maiden's status in a comms window
            return _comms_window(agent_name, status_msg)

    return text
