"""Tests for agent personality indicators."""

from agent_personality_indicators import (
    AgentPersonality,
    AgentPersonalityIndicators,
)


class TestAgentPersonality:
    """Test AgentPersonality dataclass."""

    def test_create_personality(self):
        """Test creating an agent personality."""
        personality = AgentPersonality(
            name="TestAgent",
            color=(255, 0, 0),
            icon="🔥",
            animation_style="pulse",
            description="Test agent",
        )
        assert personality.name == "TestAgent"
        assert personality.color == (255, 0, 0)
        assert personality.icon == "🔥"
        assert personality.animation_style == "pulse"
        assert personality.description == "Test agent"


class TestAgentPersonalityIndicators:
    """Test AgentPersonalityIndicators functionality."""

    def test_initialization(self):
        """Test initialization of indicators."""
        indicators = AgentPersonalityIndicators()
        assert len(indicators.personalities) > 0

    def test_get_personality_hephaestus(self):
        """Test getting Hephaestus personality."""
        indicators = AgentPersonalityIndicators()
        personality = indicators.get_personality("Hephaestus")
        assert personality is not None
        assert personality.name == "Hephaestus"

    def test_get_personality_nonexistent(self):
        """Test getting non-existent personality."""
        indicators = AgentPersonalityIndicators()
        personality = indicators.get_personality("NonExistent")
        assert personality is None

    def test_get_color_hephaestus(self):
        """Test getting Hephaestus color."""
        indicators = AgentPersonalityIndicators()
        color = indicators.get_color("Hephaestus")
        assert color == (255, 140, 0)

    def test_get_color_nonexistent(self):
        """Test getting color for non-existent agent."""
        indicators = AgentPersonalityIndicators()
        color = indicators.get_color("NonExistent")
        assert color == (200, 200, 200)

    def test_get_icon_hephaestus(self):
        """Test getting Hephaestus icon."""
        indicators = AgentPersonalityIndicators()
        icon = indicators.get_icon("Hephaestus")
        assert icon == "⚒"

    def test_get_icon_nonexistent(self):
        """Test getting icon for non-existent agent."""
        indicators = AgentPersonalityIndicators()
        icon = indicators.get_icon("NonExistent")
        assert icon == "●"

    def test_get_animation_style_hephaestus(self):
        """Test getting Hephaestus animation style."""
        indicators = AgentPersonalityIndicators()
        style = indicators.get_animation_style("Hephaestus")
        assert style == "pulse"

    def test_get_animation_style_nonexistent(self):
        """Test getting animation style for non-existent agent."""
        indicators = AgentPersonalityIndicators()
        style = indicators.get_animation_style("NonExistent")
        assert style == "none"

    def test_get_description_hephaestus(self):
        """Test getting Hephaestus description."""
        indicators = AgentPersonalityIndicators()
        description = indicators.get_description("Hephaestus")
        assert "Forge" in description

    def test_get_description_nonexistent(self):
        """Test getting description for non-existent agent."""
        indicators = AgentPersonalityIndicators()
        description = indicators.get_description("NonExistent")
        assert description == ""

    def test_set_personality(self):
        """Test setting a custom personality."""
        indicators = AgentPersonalityIndicators()
        custom = AgentPersonality(
            name="Custom",
            color=(100, 100, 100),
            icon="🎭",
            animation_style="glow",
            description="Custom agent",
        )
        indicators.set_personality("Custom", custom)
        assert indicators.get_personality("Custom") == custom

    def test_get_all_personalities(self):
        """Test getting all personalities."""
        indicators = AgentPersonalityIndicators()
        all_personalities = indicators.get_all_personalities()
        assert len(all_personalities) > 0
        assert "Hephaestus" in all_personalities

    def test_get_all_personalities_is_copy(self):
        """Test that get_all_personalities returns a copy."""
        indicators = AgentPersonalityIndicators()
        all_personalities = indicators.get_all_personalities()
        all_personalities["NewAgent"] = AgentPersonality(
            name="NewAgent", color=(0, 0, 0), icon="●", animation_style="none", description="New"
        )
        # Original should not be modified
        assert "NewAgent" not in indicators.personalities

    def test_reset_to_defaults(self):
        """Test resetting to default personalities."""
        indicators = AgentPersonalityIndicators()
        # Modify a personality
        custom = AgentPersonality(
            name="Hephaestus",
            color=(0, 0, 0),
            icon="●",
            animation_style="none",
            description="Modified",
        )
        indicators.set_personality("Hephaestus", custom)

        # Reset
        indicators.reset_to_defaults()

        # Should be back to original
        assert indicators.get_color("Hephaestus") == (255, 140, 0)

    def test_all_default_agents_present(self):
        """Test that all default agents are present."""
        indicators = AgentPersonalityIndicators()
        expected_agents = ["Hephaestus", "Metis", "Techne", "Dokimasia", "Kallos", "Mneme"]
        for agent in expected_agents:
            assert agent in indicators.personalities

    def test_personality_colors_are_unique(self):
        """Test that agent colors are reasonably distinct."""
        indicators = AgentPersonalityIndicators()
        colors = [indicators.get_color(agent) for agent in indicators.personalities]
        # All colors should be different
        assert len(colors) == len(set(colors))

    def test_personality_icons_are_unique(self):
        """Test that agent icons are unique."""
        indicators = AgentPersonalityIndicators()
        icons = [indicators.get_icon(agent) for agent in indicators.personalities]
        # All icons should be different
        assert len(icons) == len(set(icons))
