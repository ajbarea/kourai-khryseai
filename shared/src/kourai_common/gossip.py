"""Gossip minigame engine for Kourai Khryseai.

When one agent is actively working, idle agents can gossip about the player,
each other, or recent events. The gossip system:

- Runs as a parallel LLM conversation using the cheap model tier
- Surfaces private memories between agents (gossip transfer)
- Generates clickable player response options (flirt/tease/scold/join/ignore)
- Awards alignment points and affinity changes based on player responses

The engine is headless — it produces GossipSession data that the GUI or CLI
renders. It does NOT own any display logic.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kourai_common.player import (
    PlayerProfile,
    retrieve_relevant_memories,
    transfer_gossip_memories,
)

log = logging.getLogger(__name__)

# ── Gossip pair chemistry ───────────────────────────────────────────────

# Pre-defined pair dynamics: (agent_a, agent_b) → description
# Used to flavor the gossip system prompt.
GOSSIP_PAIRS: dict[tuple[str, str], str] = {
    ("metis", "kallos"): (
        "Strategist and aesthete — intellectual tea-spilling, respectful but competitive. "
        "Metis is analytical; Kallos is expressive. They admire each other but love to one-up."
    ),
    ("metis", "mneme"): (
        "Planner and scribe — the record-keepers. They bond over thoroughness but argue "
        "over whose documentation is better. Fond, bookish energy."
    ),
    ("kallos", "dokimasia"): (
        "Beauty and strength — opposites-attract banter. Kallos teases Dokimasia's "
        "bluntness; Dokimasia calls Kallos vain. Underneath, mutual respect."
    ),
    ("dokimasia", "mneme"): (
        "Guardian and historian — the serious pair. Wholesome: they worry about the player "
        "together and compare notes on what went well or poorly."
    ),
    ("techne", "kallos"): (
        "Builder and stylist — creative rivalry. 'My code is art!' 'Your code NEEDS art.' "
        "Playful competition over who makes things more beautiful."
    ),
    ("techne", "dokimasia"): (
        "Builder and tester — sibling rivalry. 'I bet my code passes first try!' "
        "'It never does~' Competitive but deeply familiar with each other."
    ),
    ("metis", "techne"): (
        "Planner and builder — the design-vs-implementation debate. Metis plans, "
        "Techne improvises. They argue but make a lethal combo."
    ),
    ("kallos", "mneme"): (
        "Aesthete and archivist — they bond over appreciation of fine details. "
        "Kallos loves beauty; Mneme loves precision. Quiet, warm friendship."
    ),
    ("metis", "dokimasia"): (
        "Strategist and guardian — both protective of quality. Metis plans defense; "
        "Dokimasia enforces it. Respect-based, slightly formal."
    ),
    ("techne", "mneme"): (
        "Builder and scribe — Techne creates, Mneme documents. Techne finds docs boring; "
        "Mneme finds undocumented code criminal. Bickering partners."
    ),
}


def _normalize_pair(a: str, b: str) -> tuple[str, str]:
    """Normalize agent pair to canonical order for lookup."""
    return (min(a, b), max(a, b))


def get_pair_chemistry(agent_a: str, agent_b: str) -> str:
    """Get the chemistry description for a gossip pair."""
    pair = _normalize_pair(agent_a, agent_b)
    return GOSSIP_PAIRS.get(pair, f"{pair[0].title()} and {pair[1].title()} chat casually.")


# ── Gossip topic selection ──────────────────────────────────────────────


class GossipTopic(Enum):
    """Categories of gossip content."""

    PLAYER_HABITS = "player_habits"  # Discussing player's patterns/preferences
    PLAYER_RELATIONSHIP = "player_rel"  # Talking about their feelings about the player
    RECENT_EVENTS = "recent_events"  # Commentary on current/recent work
    AGENT_BANTER = "agent_banter"  # Not about the player — agent-to-agent
    PLAYER_ROAST = "player_roast"  # Lovingly roasting the player


def select_gossip_topic(
    profile: PlayerProfile | None,
    agent_a: str,
    agent_b: str,
) -> GossipTopic:
    """Select a gossip topic weighted by available data.

    Prefers player-related topics when there are memories to draw from.
    Falls back to agent banter when there's not much to discuss.
    """
    weights: dict[GossipTopic, float] = {
        GossipTopic.PLAYER_HABITS: 3.0,
        GossipTopic.PLAYER_RELATIONSHIP: 3.0,
        GossipTopic.RECENT_EVENTS: 2.0,
        GossipTopic.AGENT_BANTER: 2.0,
        GossipTopic.PLAYER_ROAST: 1.0,
    }

    if not profile or not profile.display_name:
        # No player data — heavily favor agent banter
        weights[GossipTopic.PLAYER_HABITS] = 0.5
        weights[GossipTopic.PLAYER_RELATIONSHIP] = 0.5
        weights[GossipTopic.PLAYER_ROAST] = 0.2
        weights[GossipTopic.AGENT_BANTER] = 5.0

    topics = list(weights.keys())
    w = [weights[t] for t in topics]
    return random.choices(topics, weights=w, k=1)[0]  # noqa: S311


# ── Gossip session data ─────────────────────────────────────────────────


@dataclass
class GossipMessage:
    """A single message in a gossip conversation."""

    agent_name: str  # Which agent said this (or "player" for player responses)
    text: str  # The dialogue text
    is_player: bool = False  # True if this is a player response
    memory_ids_surfaced: list[str] = field(default_factory=list)  # Memories referenced


class ResponseTone(Enum):
    """Player response tone categories."""

    FLIRT = "flirt"
    TEASE = "tease"
    SCOLD = "scold"
    JOIN = "join"
    IGNORE = "ignore"
    CUSTOM = "custom"


@dataclass
class GossipResponseOption:
    """A clickable response option for the player."""

    tone: ResponseTone
    emoji: str
    label: str  # Short button label
    preview_text: str  # What the player would "say"


@dataclass
class GossipSession:
    """State for a single gossip conversation.

    Created by start_gossip_session(), updated by generate_gossip_round()
    and process_player_response(). The GUI/CLI reads this to render.
    """

    agent_a: str
    agent_b: str
    topic: GossipTopic
    messages: list[GossipMessage] = field(default_factory=list)
    response_options: list[GossipResponseOption] = field(default_factory=list)
    memory_ids_shared: list[str] = field(default_factory=list)
    round_count: int = 0
    max_rounds: int = 3
    is_complete: bool = False
    player_joined: bool = False

    @property
    def active_agents(self) -> list[str]:
        return [self.agent_a, self.agent_b]


# ── Gossip system prompt builder ────────────────────────────────────────


def _build_gossip_system_prompt(
    session: GossipSession,
    speaking_agent: str,
    profile: PlayerProfile | None,
    memories: list[dict[str, Any]],
) -> str:
    """Build the system prompt for a gossip LLM call."""
    other = session.agent_b if speaking_agent == session.agent_a else session.agent_a
    chemistry = get_pair_chemistry(speaking_agent, other)

    player_name = profile.display_name if profile else "the player"
    player_title = profile.title if profile and profile.title else ""
    archetype = profile.archetype if profile else "professional"

    # Build memory context
    mem_lines: list[str] = []
    for m in memories[:5]:
        source_note = ""
        src = m.get("source", "")
        if src.startswith("gossip:"):
            source_note = f" (heard via {src.split(':', 1)[1]})"
        elif src == "player_stated":
            source_note = " (they told you directly)"
        mem_lines.append(f"- {m['content']}{source_note}")
    memory_block = "\n".join(mem_lines) if mem_lines else "You don't have many memories yet."

    topic_prompts = {
        GossipTopic.PLAYER_HABITS: (
            f"You're gossiping about {player_name}'s habits and patterns. "
            "Share observations, compare notes on what you've noticed."
        ),
        GossipTopic.PLAYER_RELATIONSHIP: (
            f"You're discussing your feelings about {player_name}. "
            "Be honest — do you like working with them? How do they treat you?"
        ),
        GossipTopic.RECENT_EVENTS: (
            "You're chatting about recent work — what went well, what was funny, "
            "what was frustrating. Riff off each other's observations."
        ),
        GossipTopic.AGENT_BANTER: (
            "You're just chatting with each other — not about the player. "
            "Talk about work, each other, the forge, whatever feels natural."
        ),
        GossipTopic.PLAYER_ROAST: (
            f"You're lovingly roasting {player_name}. Be playful, not mean. "
            "Reference specific things you know about them. Keep it fun."
        ),
    }

    prompt = f"""You are {speaking_agent.title()}, a golden maiden of Kourai Khryseai.
You're having a casual gossip conversation with {other.title()} while another agent works.

Dynamic: {chemistry}

Player: {player_name}{f' — "{player_title}"' if player_title else ""}
Player archetype: {archetype}

Your memories about {player_name}:
{memory_block}

Topic: {topic_prompts.get(session.topic, "Chat naturally.")}

Rules:
- Stay in character. Be natural and conversational.
- Use *emote cues* for actions (e.g., *giggles*, *rolls eyes*, *whispers*).
- Keep responses short — 1-3 sentences max. This is casual chat, not a monologue.
- You may reference your memories naturally (don't list them mechanically).
- If the player joins the conversation, react naturally to their tone.
- Don't break character or reference being an AI.
- Don't use kaomoji or text faces."""

    return prompt


def _build_gossip_messages(
    session: GossipSession,
    speaking_agent: str,
) -> list[dict[str, str]]:
    """Convert gossip history into LLM message format for the next turn."""
    messages: list[dict[str, str]] = []

    for msg in session.messages:
        if msg.agent_name == speaking_agent:
            messages.append({"role": "assistant", "content": msg.text})
        else:
            prefix = ""
            if msg.is_player:
                prefix = f"[{msg.agent_name.title()} (the player) interjects]: "
            else:
                prefix = f"[{msg.agent_name.title()}]: "
            messages.append({"role": "user", "content": f"{prefix}{msg.text}"})

    return messages


# ── Core gossip operations ──────────────────────────────────────────────


def select_gossip_pair(
    busy_agent: str,
    all_agents: list[str] | None = None,
) -> tuple[str, str] | None:
    """Select a pair of idle agents for gossip.

    Args:
        busy_agent: The agent currently working (excluded from gossip).
        all_agents: Override agent list. Defaults to all specialist agents.

    Returns:
        (agent_a, agent_b) tuple, or None if insufficient idle agents.
    """
    if all_agents is None:
        all_agents = ["metis", "techne", "dokimasia", "kallos", "mneme"]

    idle = [a for a in all_agents if a != busy_agent]
    if len(idle) < 2:
        return None

    # Weight pairs by chemistry (known pairs get priority)
    candidates: list[tuple[str, str]] = []
    weights: list[float] = []

    for i, a in enumerate(idle):
        for b in idle[i + 1 :]:
            pair = _normalize_pair(a, b)
            candidates.append((a, b))
            weight = 2.0 if pair in GOSSIP_PAIRS else 1.0
            weights.append(weight)

    if not candidates:
        return None

    return random.choices(candidates, weights=weights, k=1)[0]  # noqa: S311


def start_gossip_session(
    agent_a: str,
    agent_b: str,
    profile: PlayerProfile | None = None,
    max_rounds: int = 3,
) -> GossipSession:
    """Initialize a new gossip session between two agents.

    Args:
        agent_a: First gossip agent.
        agent_b: Second gossip agent.
        profile: Player profile for context.
        max_rounds: Number of exchange rounds (each round = both agents speak).

    Returns:
        A new GossipSession ready for generate_gossip_round().
    """
    topic = select_gossip_topic(profile, agent_a, agent_b)
    session = GossipSession(
        agent_a=agent_a,
        agent_b=agent_b,
        topic=topic,
        max_rounds=max_rounds,
    )
    log.info(
        "Gossip session started: %s & %s, topic=%s",
        agent_a,
        agent_b,
        topic.value,
    )
    return session


async def generate_gossip_round(
    session: GossipSession,
    profile: PlayerProfile | None = None,
) -> list[GossipMessage]:
    """Generate one round of gossip (both agents speak once each).

    Uses the cheap LLM tier for fast, low-cost gossip generation.
    After generating, surfaces private memories and prepares response options.

    Returns:
        List of 2 GossipMessages (one per agent), or empty if session complete.
    """
    if session.is_complete or session.round_count >= session.max_rounds:
        session.is_complete = True
        return []

    from kourai_common.llm import chat

    new_messages: list[GossipMessage] = []

    for speaking_agent in [session.agent_a, session.agent_b]:
        # Get this agent's memories for prompt context
        memories: list[dict[str, Any]] = []
        if profile and profile.player_id:
            memories = retrieve_relevant_memories(profile.player_id, speaking_agent, top_k=5)

        sys_prompt = _build_gossip_system_prompt(session, speaking_agent, profile, memories)
        conversation = _build_gossip_messages(session, speaking_agent)

        # Add the system prompt and a nudge to respond
        llm_messages: list[dict[str, str]] = [{"role": "system", "content": sys_prompt}]
        llm_messages.extend(conversation)

        if not conversation:
            llm_messages.append(
                {
                    "role": "user",
                    "content": f"[Start the conversation. You speak first as {speaking_agent.title()}.]",
                }
            )

        try:
            response = await chat(
                speaking_agent,
                llm_messages,
                temperature=0.8,
                max_tokens=256,
            )
            response = response.strip()
        except Exception as e:
            log.warning("Gossip LLM call failed for %s: %s", speaking_agent, e)
            response = f"*{speaking_agent.title()} stays quiet for a moment*"

        # Detect which memories were referenced in the response
        surfaced_ids: list[str] = []
        for mem in memories:
            # Check if any key phrase from the memory appears in the response
            content_words = set(mem["content"].lower().split())
            response_words = set(response.lower().split())
            overlap = content_words & response_words
            if len(overlap) >= 3:
                surfaced_ids.append(mem["memory_id"])

        msg = GossipMessage(
            agent_name=speaking_agent,
            text=response,
            memory_ids_surfaced=surfaced_ids,
        )
        new_messages.append(msg)
        session.messages.append(msg)

    session.round_count += 1

    # After each round, transfer any surfaced memories between agents
    all_surfaced: list[str] = []
    for msg in new_messages:
        all_surfaced.extend(msg.memory_ids_surfaced)

    if all_surfaced and profile:
        for msg in new_messages:
            if msg.memory_ids_surfaced:
                others = [a for a in session.active_agents if a != msg.agent_name]
                count = transfer_gossip_memories(msg.agent_name, others, msg.memory_ids_surfaced)
                session.memory_ids_shared.extend(msg.memory_ids_surfaced)
                if count:
                    log.debug(
                        "Gossip transfer: %d memories from %s → %s",
                        count,
                        msg.agent_name,
                        others,
                    )

    # Check if session should end
    if session.round_count >= session.max_rounds:
        session.is_complete = True

    return new_messages


def generate_response_options(
    session: GossipSession,
    profile: PlayerProfile | None = None,
) -> list[GossipResponseOption]:
    """Generate clickable response options for the player based on current gossip.

    Options are influenced by the gossip topic, player alignment, and relationship.
    Some options are gated behind alignment thresholds.
    """
    options: list[GossipResponseOption] = []

    # Always available: ignore
    options.append(
        GossipResponseOption(
            tone=ResponseTone.IGNORE,
            emoji="👀",
            label="Keep listening",
            preview_text="",
        )
    )

    # Flirt — available if topic is player-related
    if session.topic != GossipTopic.AGENT_BANTER:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.FLIRT,
                emoji="💬",
                label="Flirt",
                preview_text="Talking about me behind my back~?",
            )
        )

    # Tease — always available
    last_msg = session.messages[-1] if session.messages else None
    tease_target = last_msg.agent_name if last_msg else session.agent_a
    options.append(
        GossipResponseOption(
            tone=ResponseTone.TEASE,
            emoji="🤭",
            label="Tease",
            preview_text=f"{tease_target.title()}, you sure about that~?",
        )
    )

    # Scold — authority response
    options.append(
        GossipResponseOption(
            tone=ResponseTone.SCOLD,
            emoji="😤",
            label="Scold",
            preview_text="Shouldn't you be working?",
        )
    )

    # Join — warm response
    options.append(
        GossipResponseOption(
            tone=ResponseTone.JOIN,
            emoji="😊",
            label="Join in",
            preview_text="Room for one more~?",
        )
    )

    # High alignment unlocks special options
    if profile:
        if profile.sovereignty >= 60:
            options.append(
                GossipResponseOption(
                    tone=ResponseTone.SCOLD,
                    emoji="🔴",
                    label="Command",
                    preview_text="I didn't give you permission to slack off.",
                )
            )
        if profile.devotion >= 60:
            options.append(
                GossipResponseOption(
                    tone=ResponseTone.FLIRT,
                    emoji="🔵",
                    label="Inspire",
                    preview_text="I love hearing what you think about me~",
                )
            )
        if profile.is_commander:
            options.append(
                GossipResponseOption(
                    tone=ResponseTone.JOIN,
                    emoji="👑",
                    label="Rally",
                    preview_text="Enjoying yourselves? Good. You've earned it.",
                )
            )

    session.response_options = options
    return options


async def process_player_response(
    session: GossipSession,
    response: GossipResponseOption | str,
    profile: PlayerProfile | None = None,
) -> list[GossipMessage]:
    """Process a player's response to gossip and generate agent reactions.

    Args:
        session: Current gossip session.
        response: Either a GossipResponseOption (clicked) or a custom text string.
        profile: Player profile for alignment scoring.

    Returns:
        List of agent reaction messages.
    """
    if session.is_complete:
        return []

    from kourai_common.hooks import score_gossip_response
    from kourai_common.llm import chat

    # Determine the player's text
    if isinstance(response, GossipResponseOption):
        player_text = response.preview_text
        tone = response.tone
    else:
        player_text = str(response)
        tone = ResponseTone.CUSTOM

    if not player_text or tone == ResponseTone.IGNORE:
        return []

    # Record the player's message
    player_msg = GossipMessage(
        agent_name="player",
        text=player_text,
        is_player=True,
    )
    session.messages.append(player_msg)
    session.player_joined = True

    # Score alignment + affinity effects
    if profile:
        _sov, _dev, affinity_deltas = score_gossip_response(
            player_text, profile, session.active_agents
        )
        # Apply affinity deltas
        from kourai_common.player import update_affinity

        for agent_name, delta in affinity_deltas.items():
            if delta != 0:
                multiplier = profile.alignment_compatibility(agent_name)
                update_affinity(profile.player_id, agent_name, delta, multiplier)
        profile.save()

    # Generate agent reactions
    reactions: list[GossipMessage] = []
    for agent in session.active_agents:
        memories: list[dict[str, Any]] = []
        if profile and profile.player_id:
            memories = retrieve_relevant_memories(profile.player_id, agent, top_k=3)

        sys_prompt = _build_gossip_system_prompt(session, agent, profile, memories)
        conversation = _build_gossip_messages(session, agent)

        llm_messages: list[dict[str, str]] = [{"role": "system", "content": sys_prompt}]
        llm_messages.extend(conversation)

        try:
            reaction_text = await chat(
                agent,
                llm_messages,
                temperature=0.85,
                max_tokens=200,
            )
            reaction_text = reaction_text.strip()
        except Exception as e:
            log.warning("Gossip reaction failed for %s: %s", agent, e)
            # Fallback reactions based on tone
            fallback = {
                ResponseTone.FLIRT: f"*{agent.title()} blushes* O-oh! We weren't—",
                ResponseTone.TEASE: f"*{agent.title()} pouts* Hey!",
                ResponseTone.SCOLD: f"*{agent.title()} scrambles* Y-yes! Right away!",
                ResponseTone.JOIN: f"*{agent.title()} smiles* Welcome~",
                ResponseTone.CUSTOM: f"*{agent.title()} blinks* ...Huh?",
            }
            reaction_text = fallback.get(tone, f"*{agent.title()} looks surprised*")

        msg = GossipMessage(agent_name=agent, text=reaction_text)
        reactions.append(msg)
        session.messages.append(msg)

    # Player joining extends the session by 1 round
    session.max_rounds = min(session.max_rounds + 1, 5)

    return reactions


# ── Gossip session summary ──────────────────────────────────────────────


def summarize_gossip_session(session: GossipSession) -> dict[str, Any]:
    """Produce a summary of a completed gossip session.

    Used for logging, display, and potential memory storage.
    """
    return {
        "agents": session.active_agents,
        "topic": session.topic.value,
        "rounds": session.round_count,
        "messages": len(session.messages),
        "player_joined": session.player_joined,
        "memories_shared": len(session.memory_ids_shared),
        "dialogue": [
            {"agent": m.agent_name, "text": m.text, "is_player": m.is_player}
            for m in session.messages
        ],
    }


# ── Jealousy Confrontation System ──────────────────────────────────────


@dataclass
class JealousyEvent:
    """A jealousy confrontation event triggered during/after gossip."""

    jealous_agent: str
    rival_agent: str
    trigger: str  # What caused it: "flirted_with_rival", "mentioned_rival", etc.
    confrontation_text: str  # What the jealous agent says
    response_options: list[GossipResponseOption] = field(default_factory=list)
    resolved: bool = False
    resolution_text: str = ""
    affinity_delta: float = 0.0  # Net affinity change after resolution


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
            f"{player_name}. On our last session together, you said — "
            f"and I quote — that I was 'your favourite.' "
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
            emoji="💙",
            label="Reassure",
            preview_text=f"Hey... you know you're special to me, {jealous_agent.title()}.",
        )
    )

    # Always available: deflect
    options.append(
        GossipResponseOption(
            tone=ResponseTone.TEASE,
            emoji="😏",
            label="Deflect",
            preview_text="Jealous? That's actually kind of cute~",
        )
    )

    # Sovereignty-gated: assert authority
    if profile.sovereignty >= 60:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.SCOLD,
                emoji="🔴",
                label="Assert",
                preview_text="I'll talk to whoever I want. Don't question me.",
            )
        )

    # Devotion-gated: devoted reassurance
    if profile.devotion >= 60:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.FLIRT,
                emoji="🔵",
                label="Cherish",
                preview_text="You know you're my favourite~ No one could replace you.",
            )
        )

    # Commander-gated: polyamory confidence
    if profile.is_commander:
        options.append(
            GossipResponseOption(
                tone=ResponseTone.JOIN,
                emoji="👑",
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
