"""Agent personality indicators for visual distinction."""

from dataclasses import dataclass


@dataclass
class AgentPersonality:
    """Personality indicator for an agent."""

    name: str
    color: tuple[int, int, int]
    icon: str
    animation_style: str  # "pulse", "glow", "shimmer", "none"
    description: str


class AgentPersonalityIndicators:
    """Manages personality indicators for all agents."""

    # Default agent personalities
    DEFAULT_PERSONALITIES = {
        "Hephaestus": AgentPersonality(
            name="Hephaestus",
            color=(255, 140, 0),  # Orange
            icon="⚒",
            animation_style="pulse",
            description="The Forge - Crafting and creation",
        ),
        "Metis": AgentPersonality(
            name="Metis",
            color=(100, 200, 255),  # Light blue
            icon="💡",
            animation_style="glow",
            description="Wisdom - Strategic thinking",
        ),
        "Techne": AgentPersonality(
            name="Techne",
            color=(150, 255, 150),  # Light green
            icon="⚙",
            animation_style="shimmer",
            description="Craft - Technical expertise",
        ),
        "Dokimasia": AgentPersonality(
            name="Dokimasia",
            color=(255, 200, 100),  # Gold
            icon="⚖",
            animation_style="pulse",
            description="Testing - Quality assurance",
        ),
        "Kallos": AgentPersonality(
            name="Kallos",
            color=(255, 150, 200),  # Pink
            icon="✨",
            animation_style="glow",
            description="Beauty - Aesthetics and design",
        ),
        "Mneme": AgentPersonality(
            name="Mneme",
            color=(200, 150, 255),  # Purple
            icon="📚",
            animation_style="shimmer",
            description="Memory - Knowledge and history",
        ),
    }

    def __init__(self):
        """Initialize agent personality indicators."""
        self.personalities = self.DEFAULT_PERSONALITIES.copy()

    def get_personality(self, agent_name: str) -> AgentPersonality | None:
        """Get personality indicator for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            AgentPersonality or None if not found.
        """
        return self.personalities.get(agent_name)

    def get_color(self, agent_name: str) -> tuple[int, int, int]:
        """Get color for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            RGB tuple for the agent's color.
        """
        personality = self.get_personality(agent_name)
        return personality.color if personality else (200, 200, 200)

    def get_icon(self, agent_name: str) -> str:
        """Get icon for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Icon string for the agent.
        """
        personality = self.get_personality(agent_name)
        return personality.icon if personality else "●"

    def get_animation_style(self, agent_name: str) -> str:
        """Get animation style for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Animation style string.
        """
        personality = self.get_personality(agent_name)
        return personality.animation_style if personality else "none"

    def get_description(self, agent_name: str) -> str:
        """Get description for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Description string.
        """
        personality = self.get_personality(agent_name)
        return personality.description if personality else ""

    def set_personality(self, agent_name: str, personality: AgentPersonality) -> None:
        """Set personality indicator for an agent.

        Args:
            agent_name: Name of the agent.
            personality: AgentPersonality instance.
        """
        self.personalities[agent_name] = personality

    def get_all_personalities(self) -> dict[str, AgentPersonality]:
        """Get all personality indicators.

        Returns:
            Dictionary of agent names to AgentPersonality instances.
        """
        return self.personalities.copy()

    def reset_to_defaults(self) -> None:
        """Reset all personalities to defaults."""
        self.personalities = self.DEFAULT_PERSONALITIES.copy()
