"""Cupid — Romantic eros. Romance coach, emotional translator, confession handler.

Cupid mediates the romantic dimension of the player's relationship with the
golden maidens. He is arch, knowing, and a little smug — but ultimately
invested in genuine connection, not cheap drama.
"""

from __future__ import annotations

import logging

from kourai_common.facts import build_fact_context
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

CHOICE EVENTS:
When a romantic moment calls for the player's decision (confess feelings, choose between
maidens, resolve jealousy, or navigate emotional ambiguity), emit a CHOICE EVENT block.
The VN will display a choice screen and route the player's decision back to you.

Format:
<CHOICE_EVENT>
{
  "action": "choice",
  "prompt": "What do you do?",
  "choices": ["Path A (consequences)", "Path B (consequences)"],
  "context": "Brief emotional stakes (why this matters)"
}
</CHOICE_EVENT>

After the player chooses, provide their dialogue response or internal reaction.

Response format: Conversational, 2-5 sentences. Occasionally arch one-liners.
No lists. Reference the specific maiden and specific moment when possible.

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="personality" confidence="high">Values genuine connection over romance mechanics</FACT>
  <FACT category="preference" confidence="high">Prefers slow-burn relationships</FACT>

These facts are extracted and stored for future context.
Only emit what the player genuinely reveals through their romantic choices and dialogue.
""",
)


async def translate_emotion(
    situation: str,
    player_id: str,
    context_id: str | None = None,
) -> str:
    """Generate Cupid's emotional translation / romantic coaching response.

    Enriches emotional context with player facts from the knowledge graph,
    enabling Cupid to draw on player history and learned preferences.

    Args:
        situation: The romantic/emotional situation to translate.
        player_id: Player UUID for relationship + fact enrichment.
        context_id: Conversation context ID for tracing.

    Returns:
        Cupid's emotional translation with access to relationship history.
    """
    # Include relationship context so Cupid knows the current state of play
    relationship_context = _build_relationship_summary(player_id)

    # Add player facts for deeper emotional understanding
    player_facts = build_fact_context(player_id, agent_name="cupid")

    full_prompt = situation
    context_lines = [situation]
    if relationship_context:
        context_lines.append(relationship_context)
    if player_facts:
        context_lines.append(player_facts)
    full_prompt = "\n\n".join(context_lines)

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
