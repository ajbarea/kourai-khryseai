"""Romance dialogue system — stage-based instructions, pet names, jealousy triggers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kourai_common.player_constants import (
    JEALOUSY_TRAITS,
    ROMANCE_AGENT_PERSONALITY,
    ROMANCE_PET_NAMES,
    ROMANCE_STAGE_INSTRUCTIONS,
    ROMANCE_STAGES,
)

if TYPE_CHECKING:
    from kourai_common.player_profile import PlayerProfile


# ── Romance Dialogue System ────────────────────────────────────────────


def get_romance_dialogue_instructions(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
) -> str:
    """Generate romance-specific dialogue instructions for agent system prompts.

    Builds stage-appropriate instructions with pet names, personality flavour,
    and optional jealousy context when the player romances multiple agents.

    Args:
        player_id: Player UUID.
        agent_name: The agent to generate instructions for.
        profile: Player profile (loaded if not provided).

    Returns:
        Instruction text (empty string if no active romance).
    """
    # Lazy imports to avoid circular dependency
    from kourai_common.player_affinity import get_affinity
    from kourai_common.player_profile import PlayerProfile

    if profile is None:
        profile = PlayerProfile.load()
    if not profile or profile.romance_opted_out:
        return ""

    aff = get_affinity(player_id, agent_name)
    stage = aff.get("romance_stage", "none")
    if stage == "none" or stage not in ROMANCE_STAGE_INSTRUCTIONS:
        return ""

    name = profile.display_name or "the player"

    # Get pet names for this stage
    agent_pets = ROMANCE_PET_NAMES.get(agent_name, {})
    pet_list = agent_pets.get(stage, [])
    pet_names_str = ", ".join(f'"{p}"' for p in pet_list) if pet_list else "gentle endearments"

    # Build stage instruction
    stage_text = ROMANCE_STAGE_INSTRUCTIONS[stage].format(name=name, pet_names=pet_names_str)

    # Add agent personality flavour
    personality = ROMANCE_AGENT_PERSONALITY.get(agent_name, "")
    if personality:
        personality = personality.format(name=name)

    lines = [f"=== ROMANCE: {stage.upper()} ==="]
    lines.append(stage_text)
    if personality:
        lines.append(personality)

    # Check for jealousy triggers
    jealousy_ctx = _build_jealousy_context(player_id, agent_name, profile)
    if jealousy_ctx:
        lines.append(jealousy_ctx)

    return "\n".join(lines)


def _build_jealousy_context(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile,
) -> str:
    """Build jealousy context when the player romances multiple agents.

    Only triggers at kindling+ stage. Agent's jealousy personality trait
    determines how they express it in dialogue.

    Returns:
        Jealousy instruction text, or empty string if not applicable.
    """
    # Lazy import to avoid circular dependency
    from kourai_common.player_affinity import get_affinity

    if not profile.romance_targets:
        return ""

    # Find other agents the player is romancing
    rivals = [t for t in profile.romance_targets if t != agent_name]
    if not rivals:
        return ""

    # Check if this agent is also being romanced
    aff = get_affinity(player_id, agent_name)
    my_stage = aff.get("romance_stage", "none")
    if my_stage == "none":
        return ""

    # Only trigger jealousy at kindling+ stage
    my_idx = ROMANCE_STAGES.index(my_stage) if my_stage in ROMANCE_STAGES else 0
    if my_idx < 2:  # spark doesn't trigger jealousy
        return ""

    # Get this agent's jealousy trait
    trait = JEALOUSY_TRAITS.get(agent_name)
    if not trait:
        return ""

    rival_names = ", ".join(r.title() for r in rivals)
    return (
        f"\n=== JEALOUSY CONTEXT ===\n"
        f"{profile.display_name} is also romantically involved with: {rival_names}.\n"
        f"{trait['description']}\n"
        "Express jealousy SUBTLY — weave it into your work dialogue naturally. "
        "Don't break immersion or refuse to work. Let it colour your interactions."
    )
