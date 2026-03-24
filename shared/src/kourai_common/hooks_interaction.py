"""Interaction hooks: affinity tracking and memory extraction.

Called after each agent completes a task to update player affinity scores
and extract notable memories (preferences, achievements) from the exchange.
"""

from __future__ import annotations

import logging
import re

from kourai_common.player import (
    PlayerProfile,
    add_player_memory,
    update_affinity,
)

log = logging.getLogger(__name__)

# Base affinity delta per successful interaction
BASE_AFFINITY_DELTA = 0.02
# Additional affinity for tasks that reference the player by name
NAME_BONUS = 0.005

# ── Preference / achievement extraction patterns ────────────────────────

_PREFERENCE_PATTERNS = [
    re.compile(
        r"(?:I\s+(?:prefer|like|want|love|always|hate|never))\s+(.{10,80})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:use|switch to|go with)\s+(\S+)\s+(?:instead|rather|from now)",
        re.IGNORECASE,
    ),
]
_ACHIEVEMENT_PATTERNS = [
    re.compile(r"all\s+\d+\s+tests?\s+pass", re.IGNORECASE),
    re.compile(r"build\s+succeed|all\s+clean", re.IGNORECASE),
    re.compile(r"first\s+time\s+(?:all|every)", re.IGNORECASE),
]


def track_interaction(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
    success: bool = True,
) -> None:
    """Update affinity after an agent interaction.

    Call this after each pipeline step completes. The alignment compatibility
    multiplier is applied automatically.

    Args:
        player_id: Player UUID.
        agent_name: The agent that just completed work.
        profile: Player profile (loads from disk if not provided).
        success: Whether the task completed successfully.
    """
    if not player_id:
        return

    if profile is None:
        profile = PlayerProfile.load(player_id)
    if not profile:
        return

    delta = BASE_AFFINITY_DELTA if success else BASE_AFFINITY_DELTA * 0.3
    multiplier = profile.alignment_compatibility(agent_name)

    new_score = update_affinity(player_id, agent_name, delta, alignment_multiplier=multiplier)
    log.debug(
        "Affinity update: %s %+.3f (×%.2f) → %.3f",
        agent_name,
        delta,
        multiplier,
        new_score,
    )


def extract_memories_from_interaction(
    player_id: str,
    agent_name: str,
    user_input: str,
    agent_output: str,
) -> list[str]:
    """Heuristic memory extraction from a user-agent interaction.

    Looks for stated preferences, achievements, and notable patterns
    in the conversation text. Returns list of memory IDs created.

    Args:
        player_id: Player UUID.
        agent_name: Agent that handled this interaction.
        user_input: What the user said/requested.
        agent_output: What the agent produced.

    Returns:
        List of memory_id strings for any memories created.
    """
    if not player_id or not user_input:
        return []

    created: list[str] = []

    # Check for stated preferences in user input
    for pattern in _PREFERENCE_PATTERNS:
        match = pattern.search(user_input)
        if match:
            pref_text = match.group(0).strip()
            if len(pref_text) > 15:
                mid = add_player_memory(
                    player_id,
                    pref_text,
                    category="preference",
                    agent_name=agent_name,
                    importance=0.7,
                    source="agent_observed",
                )
                created.append(mid)
                log.debug("Extracted preference memory: %s", pref_text[:60])

    # Check for achievements in agent output
    for pattern in _ACHIEVEMENT_PATTERNS:
        if pattern.search(agent_output):
            achievement_text = f"Achievement during {agent_name} task: {pattern.pattern}"
            mid = add_player_memory(
                player_id,
                achievement_text,
                category="achievement",
                agent_name=agent_name,
                importance=0.8,
                source="system_inferred",
            )
            created.append(mid)
            break  # Only one achievement per interaction

    return created
