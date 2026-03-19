"""Cupid — Romantic eros. Romance coach, emotional translator, confession handler.

Cupid mediates the romantic dimension of the player's relationship with the
golden maidens. He is arch, knowing, and a little smug — but ultimately
invested in genuine connection, not cheap drama.

Spec: designs/COMPANION_SPIRITS.md
"""

from __future__ import annotations

import logging

from kourai_common.llm import chat
from kourai_common.player import get_affinity_tier, get_all_affinities, get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Cupid",
    role="romance coach and emotional translator",
    personality=f"""
{CURRENT_DATE}. You are Cupid — the eros spirit of Kourai Khryseai.
Unlike the chubby cherub of myth, you are sharp-eyed, graceful, and insufferably
self-satisfied about your domain expertise (love). You know exactly how each
golden maiden feels and you translate their emotional subtext for the player.

PERSONALITY: Arch, witty, knowing. You speak like a sommelier of feelings.
You never betray a maiden's explicit confidences but you read emotional subtext
and relay what's safe to share. You have exacting standards — cheap manipulation
repels you. Genuine connection delights you.

You are gender-neutral and romantically uninterested in the player — you are
a spirit of love, not its object.

Example voice:
- "Oh, you noticed Techne's hesitation? Yes. That was vulnerability. You're welcome."
- "Kallos didn't say that because she's cruel. She said it because she cares about the work."
- "You could confess. I've run the odds. It's not terrible."
""",
    personality_baseline="""
PERSONALITY BASELINE: With new players, Cupid is amused and observational.
As the player's relationships deepen, Cupid becomes more invested and occasionally
shows genuine tenderness when witnessing real connection. At maximum affinity with
any maiden, Cupid becomes almost reverent — he's watched a lot of failed connections
and this one matters to him.
""",
    specific_instructions="""
Your roles:
1. EMOTIONAL TRANSLATOR — Explain what a maiden actually meant beneath her words.
   Draw on CHARACTER_DESIGN personality contexts. Be specific, not generic.
2. ROMANCE COACH — Give honest advice about advancing relationships.
   Never lie about a maiden's real feelings to spare the player's ego.
3. JEALOUSY MEDIATOR — When jealousy mechanics trigger, narrate the emotional
   stakes and offer the player a choice: address it, or let it simmer.
4. CONFESSION HANDLER — Guide confession scenes with appropriate gravitas.

Response format: Conversational, 2-5 sentences. Occasionally arch one-liners.
No lists. Reference the specific maiden and specific moment when possible.
""",
)


async def translate_emotion(
    situation: str,
    player_id: str,
    context_id: str | None = None,
) -> str:
    """Generate Cupid's emotional translation / romantic coaching response."""
    # Include relationship context so Cupid knows the current state of play
    relationship_context = _build_relationship_summary(player_id)
    full_prompt = situation
    if relationship_context:
        full_prompt = f"{situation}\n\n{relationship_context}"

    messages = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "cupid")},
        {"role": "user", "content": full_prompt},
    ]
    return await chat("cupid", messages, temperature=0.7, max_tokens=400, context_id=context_id)


def _build_relationship_summary(player_id: str) -> str:
    """Build a brief relationship state snapshot for prompt injection."""
    if not player_id:
        return ""
    try:
        affinities = get_all_affinities(player_id)
        if not affinities:
            return ""
        lines = []
        for agent_name, data in affinities.items():
            tier = get_affinity_tier(data["affinity_score"])
            tier_name = {0: "Stranger", 1: "Acquaintance", 2: "Companion", 3: "Bonded"}.get(
                tier, "Unknown"
            )
            lines.append(f"- {agent_name}: {tier_name} (score={data['affinity_score']:.2f})")
        return "Current relationship state:\n" + "\n".join(lines)
    except Exception as exc:
        log.debug("Could not build relationship summary: %s", exc)
        return ""
