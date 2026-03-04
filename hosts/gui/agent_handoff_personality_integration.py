"""Integration of agent personality indicators with agent handoff."""

from agent_personality_indicators import AgentPersonalityIndicators


class AgentHandoffPersonalityIntegration:
    """Manages agent personality display during handoffs."""

    def __init__(self, gui_instance, personality_indicators: AgentPersonalityIndicators):
        """Initialize agent handoff personality integration.

        Args:
            gui_instance: The main GUI instance.
            personality_indicators: The personality indicators instance.
        """
        self.gui = gui_instance
        self.indicators = personality_indicators
        self.current_agent = ""
        self.previous_agent = ""

    def handle_agent_handoff(self, new_agent: str) -> None:
        """Handle agent handoff with personality display.

        Args:
            new_agent: Name of the new agent.
        """
        self.previous_agent = self.current_agent
        self.current_agent = new_agent
        self._update_personality_display()

    def get_current_agent_personality(self):
        """Get personality of current agent.

        Returns:
            AgentPersonality instance or None.
        """
        return self.indicators.get_personality(self.current_agent)

    def get_current_agent_color(self) -> tuple[int, int, int]:
        """Get color of current agent.

        Returns:
            RGB tuple for the agent's color.
        """
        return self.indicators.get_color(self.current_agent)

    def get_current_agent_icon(self) -> str:
        """Get icon of current agent.

        Returns:
            Icon string for the agent.
        """
        return self.indicators.get_icon(self.current_agent)

    def get_current_agent_animation(self) -> str:
        """Get animation style of current agent.

        Returns:
            Animation style string.
        """
        return self.indicators.get_animation_style(self.current_agent)

    def get_current_agent_description(self) -> str:
        """Get description of current agent.

        Returns:
            Description string.
        """
        return self.indicators.get_description(self.current_agent)

    def get_handoff_info(self) -> dict:
        """Get information about the current handoff.

        Returns:
            Dictionary with handoff information.
        """
        return {
            "current_agent": self.current_agent,
            "previous_agent": self.previous_agent,
            "color": self.get_current_agent_color(),
            "icon": self.get_current_agent_icon(),
            "animation": self.get_current_agent_animation(),
            "description": self.get_current_agent_description(),
        }

    def _update_personality_display(self) -> None:
        """Update personality display in GUI."""
        # This would be called to update the GUI with new personality
        # Implementation depends on GUI architecture
        pass
