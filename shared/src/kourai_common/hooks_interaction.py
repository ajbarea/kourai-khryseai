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


# M17 Phase 1: closed vocabulary of HOTL pause kinds Metis is allowed to tag.
# Broadened in Phase 2 once the integration has miles on it; today an unknown
# kind logs a warning and skips synthesis rather than storing a malformed fact.
VALID_PREFERENCE_KINDS = frozenset(
    {
        "coverage_target",
        "python_version",
        "style_rules",
        "commit_style",
        "test_framework",
    }
)

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


def synthesise_fact_from_pause(
    player_id: str,
    project_id: str | None,
    preference_kind: str,
    player_response: str,
    source_agent: str,
) -> bool:
    """Synthesise a project-scoped preference fact from a resolved HOTL pause.

    M17 Phase 1: when an agent's clarifying question has been answered by the
    player, the answer is stored as a high-confidence ``preference`` fact tagged
    with the active ``project_id``. On subsequent sessions for the same project,
    ``build_fact_context`` injects the stored answer into the agent's system
    prompt so the same question is not re-asked.

    Args:
        player_id: Player UUID.
        project_id: Active project scope. ``None`` = global / cross-project.
        preference_kind: One of ``VALID_PREFERENCE_KINDS``. Unknown kinds log a
            warning and skip synthesis rather than poisoning the fact graph.
        player_response: Player's answer to the agent's clarifying question.
            Empty / whitespace-only responses are not synthesised.
        source_agent: Name of the agent that asked the question.

    Returns:
        ``True`` if a fact was stored, ``False`` if the input was rejected
        (unknown kind, empty response, or empty player_id).
    """
    if not player_id or not player_response or not player_response.strip():
        return False
    if preference_kind not in VALID_PREFERENCE_KINDS:
        log.warning(
            "synthesise_fact_from_pause: unknown preference_kind %r — skipping",
            preference_kind,
        )
        return False

    from kourai_common.facts import PlayerFact, store_facts

    fact = PlayerFact(
        body=f"{preference_kind}: {player_response.strip()}",
        category="preference",
        confidence="high",
        source_agent=source_agent,
        project_id=project_id,
    )
    store_facts(player_id, [fact])
    log.info(
        "Synthesised %s fact from %s pause for player %s (project=%s)",
        preference_kind,
        source_agent,
        player_id[:8],
        project_id or "global",
    )
    return True
