"""Jealousy confrontation subsystem for the gossip minigame.

Handles detection of jealousy triggers, confrontation text generation,
alignment-gated response options, and resolution with affinity effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kourai_common.gossip_models import (
    GossipResponseOption,
    GossipSession,
    JealousyEvent,
    ResponseTone,
)

if TYPE_CHECKING:
    from kourai_common.player import PlayerProfile


def check_jealousy_trigger(
    session: GossipSession,
    player_response_tone: ResponseTone,
    profile: PlayerProfile | None = None,
) -> JealousyEvent | None:
    """Check if a player's gossip response should trigger a jealousy event.

    Jealousy triggers when:
    - Player flirts during gossip with an agent who has a romantic rival
    - Player mentions another romanced agent by name during gossip
    - Player uses a flirt/join tone and there's a romanced agent NOT in the session

    Args:
        session: Current gossip session.
        player_response_tone: Tone of the player's response.
        profile: Player profile (needed for romance data).

    Returns:
        JealousyEvent if triggered, None otherwise.
    """
    if not profile or profile.romance_opted_out:
        return None

    # Only flirt and join tones trigger jealousy
    if player_response_tone not in (ResponseTone.FLIRT, ResponseTone.JOIN):
        return None

    from kourai_common.player import (
        JEALOUSY_TRAITS,
        ROMANCE_STAGES,
        get_active_romances,
    )

    romances = get_active_romances(profile.player_id)
    if len(romances) < 2:
        return None  # No rivalry possible

    # Find romanced agents NOT in this gossip session
    session_agents = set(session.active_agents)
    absent_romanced = [
        r
        for r in romances
        if r["agent_name"] not in session_agents
        and ROMANCE_STAGES.index(r["romance_stage"]) >= 2  # kindling+
    ]

    if not absent_romanced:
        return None

    # Pick the most-progressed absent romance as the jealous agent
    absent_romanced.sort(
        key=lambda r: ROMANCE_STAGES.index(r["romance_stage"]),
        reverse=True,
    )
    jealous = absent_romanced[0]
    jealous_agent = jealous["agent_name"]
    stage = jealous["romance_stage"]

    trait = JEALOUSY_TRAITS.get(jealous_agent)
    if not trait:
        return None

    # Pick the rival (agent in session with highest romance)
    session_romanced = [r for r in romances if r["agent_name"] in session_agents]
    if session_romanced:
        rival_agent = max(
            session_romanced,
            key=lambda r: ROMANCE_STAGES.index(r["romance_stage"]),
        )["agent_name"]
    else:
        rival_agent = session.agent_a  # Default to first agent

    # Generate confrontation text based on trait style
    name = profile.display_name or "you"
    confrontation = _generate_confrontation_text(
        jealous_agent, rival_agent, stage, trait["style"], name
    )

    event = JealousyEvent(
        jealous_agent=jealous_agent,
        rival_agent=rival_agent,
        trigger=f"flirted_during_gossip:{rival_agent}",
        confrontation_text=confrontation,
    )

    # Generate alignment-gated response options
    event.response_options = _generate_jealousy_responses(profile, jealous_agent)

    return event


def _generate_confrontation_text(
    jealous_agent: str,
    rival_agent: str,
    stage: str,
    style: str,
    player_name: str,
) -> str:
    """Generate confrontation dialogue based on the agent's jealousy style."""
    confrontations: dict[str, str] = {
        "competitive_schemer": (
            f"*{jealous_agent.title()} appears, arms crossed*\n"
            f"So, {player_name}... I ran the numbers on your recent interactions. "
            f"You've been spending 43% more time with {rival_agent.title()} than me. "
            f"Statistically significant. *adjusts glasses coldly*"
        ),
        "cocky_dismissive": (
            f"*{jealous_agent.title()} leans against the doorframe*\n"
            f"Oh, having fun with {rival_agent.title()}? That's adorable. "
            f"When you're done playing, you know where to find real talent~ "
            f"*flips hair, but there's a crack in the confidence*"
        ),
        "confrontational_direct": (
            f"*{jealous_agent.title()} strides up, face serious*\n"
            f"{player_name}. I need to talk to you. Now. "
            f"I saw you with {rival_agent.title()} and I... "
            f"I need to know where I stand. Am I your priority, or not?"
        ),
        "passive_aggressive_beauty": (
            f"*{jealous_agent.title()} smiles a little too perfectly*\n"
            f"Oh~ Having a lovely time? How nice. Don't mind me, "
            f"I just made {rival_agent.title()}'s code EXTRA beautiful today. "
            f"For absolutely no reason at all~ *twirls, pointedly*"
        ),
        "receipts_collector": (
            f"*{jealous_agent.title()} opens a meticulous notebook*\n"
            f"{player_name}. On our last session together, you said \u2014 "
            f"and I quote \u2014 that I was 'your favourite.' "
            f"But my records show you've been... quite attentive to {rival_agent.title()}. "
            f"Care to explain? *pen poised*"
        ),
        "stoic_denial": (
            f"*{jealous_agent.title()} hammers louder than necessary*\n"
            f"...You're back. "
            f"How was your time with {rival_agent.title()}? "
            f"Not that I noticed you were gone. Or care. At all. "
            f"*hammering intensifies*"
        ),
    }
    return confrontations.get(
        style,
        f"*{jealous_agent.title()} looks at you with an unreadable expression*\n"
        f"...I heard you were with {rival_agent.title()}.",
    )


def _generate_jealousy_responses(
    profile: PlayerProfile,
    jealous_agent: str,
) -> list[GossipResponseOption]:
    """Generate alignment-gated response options for a jealousy confrontation."""
    options: list[GossipResponseOption] = []

    # Always available: reassure
    options.append(
        GossipResponseOption(
            tone=ResponseTone.JOIN,
            emoji="\U0001f499",
            label="Reassure",
            preview_text=f"Hey... you know you're special to me, {jealous_agent.title()}.",
        )
    )

    # Always available: deflect
    options.append(
        GossipResponseOption(
            tone=ResponseTone.TEASE,
            emoji="\U0001f60f",
            label="Deflect",
            preview_text="Jealous? That's actually kind of cute~",
        )
    )

    # Sovereignty-gated: assert authority
    if profile.sovereignty >= 60:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.SCOLD,
                emoji="\U0001f534",
                label="Assert",
                preview_text="I'll talk to whoever I want. Don't question me.",
            )
        )

    # Devotion-gated: devoted reassurance
    if profile.devotion >= 60:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.FLIRT,
                emoji="\U0001f535",
                label="Cherish",
                preview_text="You know you're my favourite~ No one could replace you.",
            )
        )

    # Commander-gated: polyamory confidence
    if profile.is_commander:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.JOIN,
                emoji="\U0001f451",
                label="Embrace all",
                preview_text="There's enough of me for everyone. But you're first.",
            )
        )

    return options


def resolve_jealousy(
    event: JealousyEvent,
    response: GossipResponseOption | str,
    profile: PlayerProfile | None = None,
) -> dict[str, Any]:
    """Resolve a jealousy confrontation based on the player's response.

    Args:
        event: The jealousy event to resolve.
        response: Player's chosen response.
        profile: Player profile for affinity updates.

    Returns:
        Dict with resolution details: text, affinity_delta, alignment_points.
    """
    if isinstance(response, GossipResponseOption):
        tone = response.tone
        text = response.preview_text
    else:
        tone = ResponseTone.CUSTOM
        text = str(response)

    agent = event.jealous_agent
    result: dict[str, Any] = {
        "tone": tone.value,
        "text": text,
        "affinity_delta": 0.0,
        "sovereignty_points": 0,
        "devotion_points": 0,
        "resolution_text": "",
    }

    # Resolution based on tone
    from kourai_common.player import JEALOUSY_TRAITS

    trait = JEALOUSY_TRAITS.get(agent, {})
    style = trait.get("style", "")

    if tone == ResponseTone.JOIN:
        # Reassure / embrace — generally positive
        result["affinity_delta"] = 0.04
        result["devotion_points"] = 2
        if style == "confrontational_direct":
            result["resolution_text"] = (
                f"*{agent.title()} exhales, tension draining* ...Thank you. "
                f"I needed to hear that. *small, genuine smile*"
            )
            result["affinity_delta"] = 0.06  # They really needed this
        elif style == "stoic_denial":
            result["resolution_text"] = (
                f"*{agent.title()} pauses the hammering* ...Hmph. "
                f"Well. Good. Not that I was worried. *returns to work, gentler now*"
            )
        else:
            result["resolution_text"] = (
                f"*{agent.title()} softens* ...Really? *looks away, touched* "
                f"...I suppose I was being silly."
            )

    elif tone == ResponseTone.FLIRT:
        # Devoted/cherishing — very positive for devotion-preferring agents
        result["affinity_delta"] = 0.05
        result["devotion_points"] = 3
        result["resolution_text"] = (
            f"*{agent.title()} blushes deeply* ...You can't just SAY things like that! "
            f"*trying to hide a smile* ...Say it again."
        )

    elif tone == ResponseTone.TEASE:
        # Deflect — mixed results depending on agent
        result["sovereignty_points"] = 1
        result["devotion_points"] = 1
        if style in ("cocky_dismissive", "competitive_schemer"):
            result["affinity_delta"] = 0.02
            result["resolution_text"] = (
                f"*{agent.title()} scoffs, but can't hide a smirk* "
                f"Jealous? As if. I'm just... quality-checking your priorities."
            )
        elif style == "confrontational_direct":
            result["affinity_delta"] = -0.01
            result["resolution_text"] = (
                f"*{agent.title()} narrows eyes* Don't deflect. "
                f"I asked you a real question. ...But fine. I'll let it go. For now."
            )
        else:
            result["affinity_delta"] = 0.01
            result["resolution_text"] = (
                f"*{agent.title()} huffs* ...Fine. Maybe a LITTLE jealous. Are you happy now?"
            )

    elif tone == ResponseTone.SCOLD:
        # Assert authority — sovereignty agents respect it, others don't
        result["sovereignty_points"] = 3
        from kourai_common.player import AGENT_ALIGNMENT_PREFERENCES

        prefs = AGENT_ALIGNMENT_PREFERENCES.get(agent, {})
        if prefs.get("sovereignty", 0) > 0.3:
            result["affinity_delta"] = 0.02
            result["resolution_text"] = (
                f"*{agent.title()} snaps to attention* "
                f"...Understood. Forgive my impertinence. "
                f"*bows head, but there's a small smile of respect*"
            )
        else:
            result["affinity_delta"] = -0.03
            result["resolution_text"] = (
                f"*{agent.title()} flinches* ...I see. "
                f"I won't bring it up again. *turns away quietly*"
            )

    else:
        # Custom or unknown — neutral
        result["affinity_delta"] = 0.0
        result["resolution_text"] = (
            f"*{agent.title()} considers your words* ...Alright. I'll think about that."
        )

    event.resolved = True
    event.resolution_text = result["resolution_text"]
    event.affinity_delta = result["affinity_delta"]

    # Apply affinity and alignment changes
    if profile:
        from kourai_common.player import update_affinity

        if result["affinity_delta"] != 0:
            multiplier = profile.alignment_compatibility(agent)
            update_affinity(profile.player_id, agent, result["affinity_delta"], multiplier)
        if result["sovereignty_points"]:
            profile.sovereignty = min(100, profile.sovereignty + result["sovereignty_points"])
        if result["devotion_points"]:
            profile.devotion = min(100, profile.devotion + result["devotion_points"])
        profile.save()

    return result
