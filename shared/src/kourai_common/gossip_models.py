"""Pure data containers for the gossip minigame engine.

These are headless data structures consumed by gossip_core, gossip_jealousy,
and ultimately by host renderers (CLI, GUI, VN).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GossipTopic(Enum):
    """Categories of gossip content."""

    PLAYER_HABITS = "player_habits"  # Discussing player's patterns/preferences
    PLAYER_RELATIONSHIP = "player_rel"  # Talking about their feelings about the player
    RECENT_EVENTS = "recent_events"  # Commentary on current/recent work
    AGENT_BANTER = "agent_banter"  # Not about the player — agent-to-agent
    PLAYER_ROAST = "player_roast"  # Lovingly roasting the player


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
