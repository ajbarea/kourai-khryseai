"""Memory moments — probabilistic nostalgia and callback system.

Agents occasionally reference memorable past interactions during dialogue.
This module selects which memories to surface and generates context for
the LLM to weave callbacks naturally into conversation.

Romance-aware: romanced agents get exclusive intimate callback types.
"""

from __future__ import annotations

import logging
import random
import secrets
from dataclasses import dataclass

from kourai_common.player import (
    PlayerProfile,
    get_affinity,
    get_affinity_tier,
    get_player_memories,
)

log = logging.getLogger(__name__)

# Probability of a memory moment per interaction, by affinity tier.
# Higher affinity = more frequent callbacks.
MOMENT_PROBABILITY: dict[int, float] = {
    0: 0.02,  # Stranger: 2% — very rare
    1: 0.08,  # Acquaintance: 8%
    2: 0.15,  # Companion: 15%
    3: 0.25,  # Bonded: 25%
}

# Romance stage bonus probability (added to tier probability).
ROMANCE_MOMENT_BONUS: dict[str, float] = {
    "spark": 0.05,
    "kindling": 0.10,
    "flame": 0.15,
    "bonfire": 0.20,
}


@dataclass
class MemoryMoment:
    """A memory callback to inject into agent dialogue."""

    memory_id: str
    memory_content: str
    category: str
    moment_type: str  # "callback", "nostalgia", "growth", "tease", "intimate"
    prompt_hint: str  # Instruction for the LLM on how to reference this memory
    agent_name: str


# ── Moment type templates ──────────────────────────────────────────────

MOMENT_TEMPLATES: dict[str, list[str]] = {
    "callback": [
        "Reference this past moment naturally: '{content}'. "
        "Weave it into your current response as a brief aside or comparison.",
        "You recall: '{content}'. Mention it casually as a callback — "
        "don't make it the focus, just a natural reference.",
    ],
    "nostalgia": [
        "You feel nostalgic about: '{content}'. Express a brief, warm memory "
        "before continuing with your work. Something like 'Remember when...'",
        "A fond memory surfaces: '{content}'. Share it with genuine warmth — "
        "this was a meaningful moment for you.",
    ],
    "growth": [
        "You've noticed the player has grown since: '{content}'. "
        "Express subtle pride in how far they've come. Don't be patronizing.",
        "Looking at the player's work, you think of: '{content}'. "
        "Acknowledge their progress with a proud smile or remark.",
    ],
    "tease": [
        "You remember: '{content}'. Tease the player about it lovingly — "
        "playful, not mean. A shared joke between friends.",
        "Recall: '{content}'. Use it as gentle ammunition for banter. "
        "The player should laugh, not feel embarrassed.",
    ],
    "intimate": [
        "A deeply personal memory surfaces: '{content}'. "
        "Reference it with tenderness — this is between you and them. "
        "Other agents wouldn't understand. Use a pet name if appropriate.",
        "You treasure this memory: '{content}'. Let it colour your words "
        "with quiet intensity. A look, a soft aside, a moment of vulnerability.",
    ],
}


def _select_moment_type(
    tier: int,
    romance_stage: str,
    category: str,
) -> str:
    """Select what type of memory moment to generate."""
    # Romance-exclusive types
    if romance_stage in ("flame", "bonfire"):
        options = ["callback", "nostalgia", "intimate", "tease"]
        weights = [1, 2, 3, 1]
    elif romance_stage in ("spark", "kindling"):
        options = ["callback", "nostalgia", "tease"]
        weights = [2, 2, 1]
    elif tier >= 2:
        options = ["callback", "nostalgia", "growth", "tease"]
        weights = [2, 2, 1, 2]
    else:
        options = ["callback"]
        weights = [1]

    # Achievements are always "growth" type
    if category == "achievement":
        return "growth"

    return random.choices(options, weights=weights, k=1)[0]  # noqa: S311


def should_trigger_moment(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
) -> bool:
    """Roll the dice to determine if a memory moment should trigger.

    Returns True if this interaction should include a nostalgia callback.
    """
    if profile is None:
        profile = PlayerProfile.load()
    if not profile:
        return False

    aff = get_affinity(player_id, agent_name)
    tier = get_affinity_tier(aff["affinity_score"])
    base_prob = MOMENT_PROBABILITY.get(tier, 0.02)

    romance_stage = aff.get("romance_stage", "none")
    romance_bonus = ROMANCE_MOMENT_BONUS.get(romance_stage, 0.0)

    total_prob = min(base_prob + romance_bonus, 0.5)  # Cap at 50%
    return random.random() < total_prob  # noqa: S311


def select_memory_for_moment(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
) -> MemoryMoment | None:
    """Select a memory to surface as a moment and build the prompt hint.

    Picks from the agent's private memories + shared memories, weighted by
    importance. Returns None if no suitable memories exist.

    Args:
        player_id: Player UUID.
        agent_name: Agent who will deliver the moment.
        profile: Player profile.

    Returns:
        MemoryMoment with prompt hint, or None.
    """
    if profile is None:
        profile = PlayerProfile.load()
    if not profile:
        return None

    # Get this agent's visible memories
    memories = get_player_memories(player_id, agent_name=agent_name, limit=50)
    shared = get_player_memories(player_id, category="achievement", limit=20)

    all_candidates = memories + shared
    if not all_candidates:
        return None

    # Filter out very low-importance memories
    candidates = [m for m in all_candidates if m.get("importance", 0) >= 0.3]
    if not candidates:
        candidates = all_candidates[:5]  # Fallback: just take some

    # Weight by importance
    weights = [m.get("importance", 0.5) for m in candidates]
    selected = random.choices(candidates, weights=weights, k=1)[0]  # noqa: S311

    aff = get_affinity(player_id, agent_name)
    tier = get_affinity_tier(aff["affinity_score"])
    romance_stage = aff.get("romance_stage", "none")
    category = selected.get("category", "moment")

    moment_type = _select_moment_type(tier, romance_stage, category)

    # Pick a template
    templates = MOMENT_TEMPLATES.get(moment_type, MOMENT_TEMPLATES["callback"])
    template = secrets.choice(templates)
    prompt_hint = template.format(content=selected["content"])

    return MemoryMoment(
        memory_id=selected["memory_id"],
        memory_content=selected["content"],
        category=category,
        moment_type=moment_type,
        prompt_hint=prompt_hint,
        agent_name=agent_name,
    )


def generate_moment_context(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
) -> str | None:
    """Main entry point: check if a moment should trigger and build context.

    Call this before constructing the LLM message list. If it returns a
    string, append it to the system prompt as additional context.

    Returns:
        Prompt context string, or None if no moment triggers.
    """
    if not should_trigger_moment(player_id, agent_name, profile):
        return None

    moment = select_memory_for_moment(player_id, agent_name, profile)
    if not moment:
        return None

    log.debug(
        "Memory moment triggered for %s via %s: %s",
        agent_name,
        moment.moment_type,
        moment.memory_content[:60],
    )

    return (
        f"\n=== MEMORY MOMENT ({moment.moment_type.upper()}) ===\n"
        f"{moment.prompt_hint}\n"
        "Work this into your response ONCE, briefly and naturally. "
        "Don't force it if it doesn't fit the current context."
    )
