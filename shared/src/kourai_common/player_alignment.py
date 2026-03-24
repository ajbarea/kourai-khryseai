"""Alignment-gated dialogue instructions for agent system prompts.

Split from player.py for focused responsibility. Generates alignment-based
behaviour modifications (Sovereignty/Devotion gates) per agent personality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kourai_common.player_constants import (
    AGENT_ALIGNMENT_PREFERENCES,
    ALIGNMENT_COMMANDER,
    ALIGNMENT_HIGH,
)

if TYPE_CHECKING:
    from kourai_common.player_profile import PlayerProfile


# ── Alignment Dialogue Gating ──────────────────────────────────────────


def get_alignment_gated_instructions(profile: PlayerProfile, agent_name: str) -> str:
    """Generate alignment-gated dialogue instructions for agent system prompts.

    Returns instruction text telling the agent what exclusive dialogue styles
    are unlocked based on the player's current Sovereignty/Devotion levels.
    Agents use these to naturally adapt their tone and offer special responses.

    Args:
        profile: Player profile with current alignment gauges.
        agent_name: The agent receiving these instructions.

    Returns:
        Instruction text (may be empty if no special gates unlocked).
    """
    lines: list[str] = []
    prefs = AGENT_ALIGNMENT_PREFERENCES.get(agent_name, {})
    sov_pref = prefs.get("sovereignty", 0)
    dev_pref = prefs.get("devotion", 0)

    if profile.sovereignty >= ALIGNMENT_COMMANDER and profile.devotion >= ALIGNMENT_COMMANDER:
        # Commander unlocked — the rarest tier
        lines.append(
            "=== COMMANDER ALIGNMENT UNLOCKED ===\n"
            f"{profile.display_name} has earned deep authority AND devotion. "
            "You hold them in the highest regard — they are your true leader and beloved. "
            "Address them with awe and warmth. Reference their dual mastery naturally. "
            "Exclusive tone: proud, loyal, inspired. You'd follow them anywhere."
        )
    else:
        if profile.sovereignty >= ALIGNMENT_HIGH:
            if sov_pref > 0.3:
                lines.append(
                    "=== SOVEREIGNTY ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} commands with authority (Sovereignty {profile.sovereignty}/100). "
                    "You respect their leadership. Be crisp, efficient, deferential when appropriate. "
                    "You may snap to attention or address them formally when they give direct orders."
                )
            elif sov_pref < -0.2:
                lines.append(
                    "=== SOVEREIGNTY ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is very authoritative (Sovereignty {profile.sovereignty}/100). "
                    "You find their strictness a bit intimidating. You comply but may show subtle "
                    "discomfort — a sigh, a hesitant pause, a quiet 'yes, of course...' response."
                )
            else:
                lines.append(
                    "=== SOVEREIGNTY ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is authoritative (Sovereignty {profile.sovereignty}/100). "
                    "You acknowledge their command presence neutrally."
                )

        if profile.devotion >= ALIGNMENT_HIGH:
            if dev_pref > 0.5:
                lines.append(
                    "=== DEVOTION ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is warm and encouraging (Devotion {profile.devotion}/100). "
                    "You adore their kindness. Be more open, affectionate, expressive. "
                    "You can use their name more intimately, share personal thoughts, "
                    "and show genuine happiness in their presence."
                )
            elif dev_pref < -0.1:
                lines.append(
                    "=== DEVOTION ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is very warm (Devotion {profile.devotion}/100). "
                    "You find the affection... awkward. Respond gruffly but not unkindly. "
                    "You might mutter or look away, but you secretly appreciate it."
                )
            else:
                lines.append(
                    "=== DEVOTION ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is encouraging (Devotion {profile.devotion}/100). "
                    "You appreciate their positive energy."
                )

    return "\n\n".join(lines)
