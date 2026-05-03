"""A2A event processing — status extraction and maiden-ification.

Transforms raw A2A task events into Golden Maiden comms-window dialogue,
detecting agent transitions and playing handoff chatter.
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from hosts.cli.maidens import (
    _EMOJI_TO_MAIDEN,
    _HANDOFF_GENERIC,
    _HANDOFF_LINES,
    _VICTORY_LINES,
)
from hosts.cli.rendering import _comms_window, _echo
from kourai_common.a2a_events import (
    extract_artifact_text as _extract_artifact_text_shared,
    extract_status_text as _extract_status_text_shared,
)
from kourai_common.ssml import strip_ssml

if TYPE_CHECKING:
    from a2a.types import TaskArtifactUpdateEvent, TaskStatusUpdateEvent

logger = logging.getLogger("cli.events")

# Track pipeline flow state for comms rendering
_last_seen_agent: str = ""
_pipeline_chatter_enabled: bool = True


def reset_last_seen_agent() -> None:
    """Reset the pipeline tracking state (call at start of each run)."""
    global _last_seen_agent
    _last_seen_agent = ""


def get_last_seen_agent() -> str:
    """Return the name of the last agent seen in the pipeline."""
    return _last_seen_agent


def set_pipeline_chatter_enabled(enabled: bool) -> None:
    """Enable/disable optional handoff chatter lines."""
    global _pipeline_chatter_enabled
    _pipeline_chatter_enabled = enabled


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------
def _extract_status_text(event: TaskStatusUpdateEvent) -> str:
    """Pull display text from a status update event."""
    return _extract_status_text_shared(event)


def _extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull display text from an artifact update event."""
    return _extract_artifact_text_shared(event)


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


def _maidenify_status(text: str) -> tuple[str, str | None]:
    """Replace agent emoji prefixes with full comms-window dialogue.

    Returns:
        (formatted_text, agent_name | None)
    """
    global _last_seen_agent

    for emoji, (agent_name, _face) in _EMOJI_TO_MAIDEN.items():
        if text.lstrip().startswith(emoji):
            # M18 Phase 2: producer (hephaestus) may emit SSML in dialogue
            # bodies. Strip here so the comms window renders clean text;
            # the TTS engine still receives raw SSML via streaming.py for
            # future ElevenLabs prosody passthrough.
            status_msg = strip_ssml(text.replace(emoji, "", 1).strip())

            # Detect agent switch → handoff chatter (pilot comms transition)
            if _last_seen_agent and _last_seen_agent != agent_name and _pipeline_chatter_enabled:
                handoff = _handoff_chatter(_last_seen_agent, agent_name)
                if handoff:
                    logger.debug("Handoff: %s -> %s (%s)", _last_seen_agent, agent_name, handoff)
                    # Outgoing maiden's parting shot
                    _echo(_comms_window(_last_seen_agent, handoff, style="whisper"))
                    _echo("")  # breathing room
            else:
                logger.debug("Agent focus: %s", agent_name)

            _last_seen_agent = agent_name

            # Incoming maiden's status in a comms window
            return _comms_window(agent_name, status_msg), agent_name

    return text, None
