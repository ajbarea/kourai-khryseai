"""Tests for agent handoff personality integration."""

from unittest.mock import Mock

from agent_handoff_personality_integration import AgentHandoffPersonalityIntegration
from agent_personality_indicators import AgentPersonalityIndicators


class TestAgentHandoffPersonalityIntegration:
    """Test agent handoff personality integration."""

    def test_initialization(self):
        """Test initialization of handoff personality integration."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()

        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)
        assert integration.gui is mock_gui
        assert integration.indicators is indicators
        assert integration.current_agent == ""
        assert integration.previous_agent == ""

    def test_handle_agent_handoff(self):
        """Test handling agent handoff."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")

        assert integration.current_agent == "Hephaestus"
        assert integration.previous_agent == ""

    def test_handle_multiple_handoffs(self):
        """Test handling multiple agent handoffs."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        integration.handle_agent_handoff("Metis")

        assert integration.current_agent == "Metis"
        assert integration.previous_agent == "Hephaestus"

    def test_get_current_agent_personality(self):
        """Test getting current agent personality."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        personality = integration.get_current_agent_personality()

        assert personality is not None
        assert personality.name == "Hephaestus"

    def test_get_current_agent_color(self):
        """Test getting current agent color."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        color = integration.get_current_agent_color()

        assert color == (255, 140, 0)

    def test_get_current_agent_icon(self):
        """Test getting current agent icon."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        icon = integration.get_current_agent_icon()

        assert icon == "⚒"

    def test_get_current_agent_animation(self):
        """Test getting current agent animation."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        animation = integration.get_current_agent_animation()

        assert animation == "pulse"

    def test_get_current_agent_description(self):
        """Test getting current agent description."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        description = integration.get_current_agent_description()

        assert "Forge" in description

    def test_get_handoff_info(self):
        """Test getting handoff information."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        info = integration.get_handoff_info()

        assert info["current_agent"] == "Hephaestus"
        assert info["previous_agent"] == ""
        assert info["color"] == (255, 140, 0)
        assert info["icon"] == "⚒"
        assert info["animation"] == "pulse"
        assert "Forge" in info["description"]

    def test_handoff_info_after_multiple_handoffs(self):
        """Test handoff info after multiple handoffs."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        integration.handle_agent_handoff("Hephaestus")
        integration.handle_agent_handoff("Metis")
        info = integration.get_handoff_info()

        assert info["current_agent"] == "Metis"
        assert info["previous_agent"] == "Hephaestus"
        assert info["color"] == (100, 200, 255)

    def test_get_personality_before_handoff(self):
        """Test getting personality before any handoff."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        personality = integration.get_current_agent_personality()
        assert personality is None

    def test_get_color_before_handoff(self):
        """Test getting color before any handoff."""
        mock_gui = Mock()
        indicators = AgentPersonalityIndicators()
        integration = AgentHandoffPersonalityIntegration(mock_gui, indicators)

        color = integration.get_current_agent_color()
        assert color == (200, 200, 200)  # Default color
