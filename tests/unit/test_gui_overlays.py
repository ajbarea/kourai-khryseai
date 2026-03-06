"""Tests for GUI overlay components — alignment gauges, gossip panel, onboarding, memory viewer.

Tests focus on logic and state transitions, not Pygame rendering.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Alignment theme (pure logic, no pygame needed)
# ---------------------------------------------------------------------------


class TestAlignmentTheme:
    """Tests for alignment palette computation."""

    def test_neutral_palette_at_zero(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(0, 0)
        assert "background" in palette
        assert "gold" in palette
        assert "text" in palette
        # At (0,0), should be close to neutral defaults
        assert palette["background"] == (12, 10, 8)

    def test_high_sovereignty_shifts_red(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        neutral = compute_alignment_palette(0, 0)
        sov_high = compute_alignment_palette(100, 0)
        # Background should be redder (higher R relative to G,B)
        assert sov_high["background"][0] > neutral["background"][0]

    def test_high_devotion_shifts_blue(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        neutral = compute_alignment_palette(0, 0)
        dev_high = compute_alignment_palette(0, 100)
        # Background should be bluer (higher B relative to R)
        assert dev_high["background"][2] > neutral["background"][2]

    def test_commander_palette_purple(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(100, 100)
        # Commander palette has purple tones — background B > baseline
        assert palette["background"][2] > 10

    def test_palette_returns_all_keys(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(50, 50)
        expected_keys = {
            "background",
            "bubble_bg",
            "gold",
            "gold_dim",
            "text",
            "scrollbar",
            "error_red",
        }
        assert set(palette.keys()) == expected_keys

    def test_palette_values_are_rgb_tuples(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(70, 30)
        for key, value in palette.items():
            assert isinstance(value, tuple), f"{key} should be a tuple"
            assert len(value) == 3, f"{key} should have 3 channels"
            for ch in value:
                assert 0 <= ch <= 255, f"{key} channel {ch} out of range"

    def test_lerp_color_boundaries(self):
        from hosts.gui.alignment_theme import _lerp_color

        assert _lerp_color((0, 0, 0), (255, 255, 255), 0.0) == (0, 0, 0)
        assert _lerp_color((0, 0, 0), (255, 255, 255), 1.0) == (255, 255, 255)
        assert _lerp_color((0, 0, 0), (100, 200, 50), 0.5) == (50, 100, 25)

    def test_lerp_color_clamps(self):
        from hosts.gui.alignment_theme import _lerp_color

        # t < 0 should clamp to 0
        assert _lerp_color((0, 0, 0), (255, 255, 255), -1.0) == (0, 0, 0)
        # t > 1 should clamp to 1
        assert _lerp_color((0, 0, 0), (255, 255, 255), 2.0) == (255, 255, 255)


# ---------------------------------------------------------------------------
# Gossip panel data model (logic only)
# ---------------------------------------------------------------------------


class TestGossipPanelModel:
    """Test gossip panel data model — messages, responses, session lifecycle."""

    @pytest.fixture(autouse=True)
    def _init_pygame(self):
        """Initialize pygame for surface-dependent components."""
        import pygame

        pygame.init()
        pygame.freetype.init()
        yield
        pygame.quit()

    def test_start_session_clears_state(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.add_message("metis", "Hello~")
        panel.start_session("metis", "kallos")

        assert panel.active is True
        assert panel.agent_a == "metis"
        assert panel.agent_b == "kallos"
        assert len(panel.messages) == 0

    def test_add_message(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.start_session("metis", "kallos")
        panel.add_message("metis", "Did you know...")
        panel.add_message("kallos", "Tell me more~")

        assert len(panel.messages) == 2
        assert panel.messages[0].agent_name == "metis"
        assert panel.messages[1].text == "Tell me more~"

    def test_set_response_options(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.set_response_options(
            [
                {"emoji": "💬", "label": "Flirt", "preview": "Hey there~"},
                {"emoji": "😤", "label": "Scold", "preview": "Back to work!"},
            ]
        )

        assert len(panel.response_buttons) == 2
        assert panel.response_buttons[0].label == "Flirt"
        assert panel.response_buttons[1].emoji == "😤"

    def test_get_selected_response_clears(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.selected_response = 1
        result = panel.get_selected_response()
        assert result == 1
        assert panel.get_selected_response() is None

    def test_end_session(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.start_session("techne", "dokimasia")
        panel.set_response_options([{"emoji": "👀", "label": "Watch", "preview": "..."}])
        panel.end_session()

        assert panel.is_complete is True
        assert len(panel.response_buttons) == 0

    def test_dismiss(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.start_session("metis", "kallos")
        panel.dismiss()
        assert panel.active is False

    def test_player_message_flag(self):
        from hosts.gui.gossip_panel import GossipPanel

        panel = GossipPanel(1280, 720)
        panel.add_message("player", "Hey!", is_player=True)
        assert panel.messages[0].is_player is True


# ---------------------------------------------------------------------------
# Onboarding overlay state machine
# ---------------------------------------------------------------------------


class TestOnboardingOverlay:
    """Test onboarding step transitions and result generation."""

    @pytest.fixture(autouse=True)
    def _init_pygame(self):
        import pygame

        pygame.init()
        pygame.freetype.init()
        yield
        pygame.quit()

    def test_initial_state(self):
        from hosts.gui.onboarding_ui import STEP_NAME, OnboardingOverlay

        ob = OnboardingOverlay(1280, 720)
        assert ob.active is False
        ob.start()
        assert ob.active is True
        assert ob.step == STEP_NAME

    def test_finalize_produces_result(self):
        from hosts.gui.onboarding_ui import OnboardingOverlay

        ob = OnboardingOverlay(1280, 720)
        ob.start()
        ob.name_text = "AJ"
        ob.tts_text = "ay jay"
        ob.selected_title = "The Architect"
        ob.selected_role = "divine"
        ob.selected_pronouns = "he/him"
        ob._finalize()

        result = ob.get_result()
        assert result is not None
        assert result["display_name"] == "AJ"
        assert result["tts_name"] == "ay jay"
        assert result["role"] == "divine"
        assert result["pronouns"] == "he/him"
        assert ob.active is False

    def test_finalize_defaults_tts_to_display_name(self):
        from hosts.gui.onboarding_ui import OnboardingOverlay

        ob = OnboardingOverlay(1280, 720)
        ob.start()
        ob.name_text = "AJ"
        ob.tts_text = ""
        ob.selected_role = "mortal"
        ob._finalize()

        result = ob.get_result()
        assert result["tts_name"] == "AJ"

    def test_finalize_defaults_role(self):
        from hosts.gui.onboarding_ui import OnboardingOverlay

        ob = OnboardingOverlay(1280, 720)
        ob.start()
        ob.name_text = "Test"
        ob.tts_text = "Test"
        ob.selected_role = ""
        ob._finalize()

        result = ob.get_result()
        assert result["role"] == "mortal"


# ---------------------------------------------------------------------------
# Alignment gauge panel
# ---------------------------------------------------------------------------


class TestAlignmentGaugePanel:
    @pytest.fixture(autouse=True)
    def _init_pygame(self):
        import pygame

        pygame.init()
        pygame.freetype.init()
        yield
        pygame.quit()

    def test_toggle(self):
        from hosts.gui.alignment_gauges import AlignmentGaugePanel

        panel = AlignmentGaugePanel(1280, 720)
        assert panel.active is False
        panel.toggle()
        assert panel.active is True
        panel.toggle()
        assert panel.active is False

    def test_update_values(self):
        from hosts.gui.alignment_gauges import AlignmentGaugePanel

        panel = AlignmentGaugePanel(1280, 720)
        panel.update_values(75, 40, "commander")
        assert panel.sovereignty == 75
        assert panel.devotion == 40
        assert panel.archetype == "commander"

    def test_smooth_animation(self):
        from hosts.gui.alignment_gauges import AlignmentGaugePanel

        panel = AlignmentGaugePanel(1280, 720)
        panel.update_values(100, 50, "commander")
        # Initially the display values should be 0
        assert panel._sov_display == 0.0

        # After a small dt update, display should start moving but not reach target
        panel.update(0.016)  # ~1 frame at 60fps
        assert panel._sov_display > 0.0
        assert panel._sov_display < 100.0


# ---------------------------------------------------------------------------
# Memory viewer data
# ---------------------------------------------------------------------------


class TestMemoryViewerPanel:
    @pytest.fixture(autouse=True)
    def _init_pygame(self):
        import pygame

        pygame.init()
        pygame.freetype.init()
        yield
        pygame.quit()

    def test_toggle(self):
        from hosts.gui.memory_viewer import MemoryViewerPanel

        panel = MemoryViewerPanel(1280, 720)
        assert panel.active is False
        panel.toggle()
        assert panel.active is True
        panel.toggle()
        assert panel.active is False

    def test_score_to_tier(self):
        from hosts.gui.memory_viewer import MemoryViewerPanel

        assert MemoryViewerPanel._score_to_tier(0.0) == "stranger"
        assert MemoryViewerPanel._score_to_tier(0.1) == "stranger"
        assert MemoryViewerPanel._score_to_tier(0.15) == "acquaintance"
        assert MemoryViewerPanel._score_to_tier(0.4) == "companion"
        assert MemoryViewerPanel._score_to_tier(0.7) == "bonded"
        assert MemoryViewerPanel._score_to_tier(1.0) == "bonded"
