# ruff: noqa: E402
"""Comprehensive tests for pygame-dependent GUI panels and overlays.

Covers:
- hosts/gui/dialogue.py (DialogueEntry, DialogueHistory, draw_banner)
- hosts/gui/gossip_panel.py (GossipMessage, GossipResponseButton, GossipPanel)
- hosts/gui/memory_viewer.py (MemoryViewerPanel)
- hosts/gui/alignment_gauges.py (AlignmentGaugePanel)
- hosts/gui/onboarding_ui.py (OnboardingOverlay)
- hosts/gui/portrait.py (PortraitPanel, load_avatar)
- hosts/gui/portrait_flash_integration.py (PortraitFlashIntegration)
- hosts/gui/typewriter_flash_integration.py (TypewriterFlashIntegration)
- hosts/gui/gui_components_integration.py (GUIComponentsIntegration)
- hosts/gui/high_contrast_gui_integration.py (HighContrastGUIIntegration)
- hosts/gui/pipeline_status_gui_integration.py (PipelineStatusGUIIntegration)
- hosts/gui/scratchpad_gui_integration.py (ScratchpadGUIIntegration)
- hosts/gui/status_bubbles_gui_integration.py (StatusBubblesGUIIntegration)
- hosts/gui/loading_screen.py (_LoadingEmber, _draw_text_card, helpers)
- hosts/gui/profile_select.py (_card_rect, _new_game_rect, helpers)
- hosts/gui/audio_manager.py (AudioManager)
- hosts/gui/tts_engine.py (VoiceConfig, VOICE_ROSTER, AGENT_VOICES)
- hosts/gui/dialogue_history_integration.py (DialogueHistoryWithAutoScroll)

Target: bring overall hosts/gui coverage to 90%+.
"""

from __future__ import annotations

import pygame

pygame.init()

import time
from unittest.mock import Mock, patch

import pygame.freetype


def _surf(w: int = 800, h: int = 600) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _font() -> pygame.freetype.Font:
    return pygame.freetype.SysFont("arial", 14)


# ===================================================================
# 1. dialogue.py
# ===================================================================
from hosts.gui.dialogue import DialogueEntry, DialogueHistory, draw_banner


class TestDialogueEntry:
    def test_init_defaults(self):
        e = DialogueEntry("hephaestus", "Hello world")
        assert e.agent == "hephaestus"
        assert e.text == "Hello world"
        assert e.is_user is False
        assert e.is_result is False
        assert e.is_error is False
        assert e.is_system is False
        assert e.processing_time is None
        assert e.agent_count is None
        assert e.metadata_visible is True
        assert isinstance(e.timestamp, float)

    def test_init_user(self):
        e = DialogueEntry("user", "hi", is_user=True)
        assert e.is_user is True

    def test_init_result(self):
        e = DialogueEntry("metis", "plan", is_result=True, processing_time=1.5, agent_count=3)
        assert e.is_result is True
        assert e.processing_time == 1.5
        assert e.agent_count == 3

    def test_init_error(self):
        e = DialogueEntry("system", "err", is_error=True)
        assert e.is_error is True

    def test_init_system(self):
        e = DialogueEntry("system", "connected", is_system=True)
        assert e.is_system is True


class TestDialogueHistory:
    def test_init(self):
        h = DialogueHistory()
        assert len(h._entries) == 0
        assert h._scroll_y == 0
        assert h.show_timestamps is True
        assert h.show_metadata is True

    def test_add(self):
        h = DialogueHistory()
        e = DialogueEntry("metis", "hello")
        h.add(e)
        assert len(h._entries) == 1
        assert h._dirty is True

    def test_update_last_text(self):
        h = DialogueHistory()
        h.add(DialogueEntry("metis", "hel"))
        h.update_last_text("hello world")
        assert h._entries[-1].text == "hello world"
        assert h._dirty is True

    def test_update_last_text_empty(self):
        h = DialogueHistory()
        h.update_last_text("no entries")  # should not raise

    def test_scroll(self):
        h = DialogueHistory()
        h._content_h = 2000
        h.scroll(100)
        assert h._scroll_y == 100
        h.scroll(-200)
        assert h._scroll_y == 0  # clamped

    def test_scroll_to_bottom(self):
        h = DialogueHistory()
        h._content_h = 2000
        h.scroll_to_bottom()
        assert h._scroll_y > 0

    def test_wrap_text(self):
        h = DialogueHistory()
        lines = h._wrap_text("Hello world this is a test", 200)
        assert isinstance(lines, list)
        assert len(lines) >= 1

    def test_wrap_text_multiline(self):
        h = DialogueHistory()
        lines = h._wrap_text("Line 1\nLine 2\nLine 3", 500)
        assert len(lines) >= 3

    def test_wrap_text_empty(self):
        h = DialogueHistory()
        lines = h._wrap_text("", 200)
        assert len(lines) >= 1

    def test_entry_height_user(self):
        h = DialogueHistory()
        e = DialogueEntry("user", "short", is_user=True)
        height = h._entry_height(e, 500)
        assert height > 0

    def test_entry_height_agent(self):
        h = DialogueHistory()
        e = DialogueEntry("metis", "text")
        height = h._entry_height(e, 500)
        assert height > 0

    def test_entry_height_system(self):
        h = DialogueHistory()
        e = DialogueEntry("system", "info", is_system=True)
        height = h._entry_height(e, 500)
        assert height == 24  # compact

    def test_entry_height_system_faded(self):
        h = DialogueHistory()
        e = DialogueEntry("system", "old", is_system=True)
        e.timestamp = time.time() - 20  # well past fade
        height = h._entry_height(e, 500)
        assert height == 0

    def test_system_alpha_fresh(self):
        h = DialogueHistory()
        e = DialogueEntry("system", "hi", is_system=True)
        assert h._system_alpha(e) == 1.0

    def test_system_alpha_fading(self):
        h = DialogueHistory()
        e = DialogueEntry("system", "hi", is_system=True)
        e.timestamp = time.time() - 5.0
        alpha = h._system_alpha(e)
        assert 0.0 < alpha < 1.0

    def test_system_alpha_gone(self):
        h = DialogueHistory()
        e = DialogueEntry("system", "hi", is_system=True)
        e.timestamp = time.time() - 20.0
        assert h._system_alpha(e) == 0.0

    def test_toggle_timestamps(self):
        h = DialogueHistory()
        assert h.show_timestamps is True
        h.toggle_timestamps()
        assert h.show_timestamps is False
        h.toggle_timestamps()
        assert h.show_timestamps is True

    def test_toggle_metadata(self):
        h = DialogueHistory()
        assert h.show_metadata is True
        h.toggle_metadata()
        assert h.show_metadata is False

    def test_set_timestamp_format(self):
        h = DialogueHistory()
        h.set_timestamp_format("12h")
        assert h.timestamp_format == "12h"

    def test_get_timestamp_text_24h(self):
        h = DialogueHistory()
        e = DialogueEntry("metis", "test")
        ts = h.get_timestamp_text(e, "24h")
        assert ":" in ts

    def test_get_timestamp_text_12h(self):
        h = DialogueHistory()
        e = DialogueEntry("metis", "test")
        ts = h.get_timestamp_text(e, "12h")
        assert "AM" in ts or "PM" in ts

    def test_get_metadata_text_with_data(self):
        h = DialogueHistory()
        e = DialogueEntry("metis", "test", processing_time=2.5, agent_count=4)
        meta = h.get_metadata_text(e)
        assert "2.50s" in meta
        assert "4" in meta

    def test_get_metadata_text_empty(self):
        h = DialogueHistory()
        e = DialogueEntry("metis", "test")
        assert h.get_metadata_text(e) == ""

    def test_handle_click_outside(self):
        h = DialogueHistory()
        dest = pygame.Rect(100, 100, 400, 300)
        result = h.handle_click((0, 0), dest)
        assert result is None

    def test_handle_click_no_entries(self):
        h = DialogueHistory()
        dest = pygame.Rect(100, 100, 400, 300)
        result = h.handle_click((200, 200), dest)
        assert result is None

    def test_handle_right_click_outside(self):
        h = DialogueHistory()
        dest = pygame.Rect(100, 100, 400, 300)
        result = h.handle_right_click((0, 0), dest)
        assert result is None

    def test_draw_empty(self):
        h = DialogueHistory()
        s = _surf()
        dest = pygame.Rect(0, 0, 400, 300)
        h.draw(s, dest)  # should not raise

    def test_draw_with_entries(self):
        h = DialogueHistory()
        h.add(DialogueEntry("user", "hi there", is_user=True))
        h.add(DialogueEntry("hephaestus", "hello *nods*"))
        h.add(DialogueEntry("metis", "plan result", is_result=True, processing_time=1.0))
        h.add(DialogueEntry("system", "error!", is_error=True))
        h.add(DialogueEntry("system", "connected", is_system=True))
        s = _surf()
        dest = pygame.Rect(0, 0, 600, 400)
        h.draw(s, dest)

    def test_draw_with_scrollbar(self):
        h = DialogueHistory()
        for i in range(30):
            h.add(DialogueEntry("metis", f"Long message number {i} " * 5))
        s = _surf()
        dest = pygame.Rect(0, 0, 600, 200)
        h.draw(s, dest)

    def test_render_creates_entry_rects(self):
        h = DialogueHistory()
        h.add(DialogueEntry("hephaestus", "hello"))
        h.add(DialogueEntry("user", "hi", is_user=True))
        dest = pygame.Rect(0, 0, 600, 400)
        h._render(dest)
        assert len(h._entry_rects) >= 1

    def test_handle_click_inside_entry(self):
        h = DialogueHistory()
        h.add(DialogueEntry("hephaestus", "hello"))
        dest = pygame.Rect(0, 0, 600, 400)
        h._render(dest)
        if h._entry_rects:
            e, rect = h._entry_rects[0]
            result = h.handle_click((dest.x + rect.centerx, dest.y + rect.centery), dest)
            assert result == "hephaestus"

    def test_handle_right_click_returns_text(self):
        h = DialogueHistory()
        h.add(DialogueEntry("metis", "plan text"))
        dest = pygame.Rect(0, 0, 600, 400)
        h._render(dest)
        if h._entry_rects:
            e, rect = h._entry_rects[0]
            result = h.handle_right_click((dest.x + rect.centerx, dest.y + rect.centery), dest)
            assert result == "plan text"


class TestDrawBanner:
    def test_draw_banner_connected(self):
        s = _surf()
        draw_banner(s, True, "http://localhost:10000")

    def test_draw_banner_disconnected(self):
        s = _surf()
        draw_banner(s, False, "")


# ===================================================================
# 2. gossip_panel.py
# ===================================================================
from hosts.gui.gossip_panel import GossipMessage, GossipPanel, GossipResponseButton


class TestGossipMessage:
    def test_init(self):
        m = GossipMessage("metis", "Hey there")
        assert m.agent_name == "metis"
        assert m.text == "Hey there"
        assert m.is_player is False
        assert m.alpha == 0.0

    def test_init_player(self):
        m = GossipMessage("player", "Respond", is_player=True)
        assert m.is_player is True


class TestGossipResponseButton:
    def test_init(self):
        b = GossipResponseButton(0, "💬", "Respond", "Say something nice")
        assert b.index == 0
        assert b.emoji == "💬"
        assert b.label == "Respond"
        assert b.preview == "Say something nice"
        assert b.hovered is False


class TestGossipPanel:
    def test_init(self):
        p = GossipPanel(800, 600)
        assert p.active is False
        assert p.slide_x == 0.0
        assert len(p.messages) == 0

    def test_start_session(self):
        p = GossipPanel(800, 600)
        p.start_session("metis", "kallos")
        assert p.active is True
        assert p.agent_a == "metis"
        assert p.agent_b == "kallos"
        assert p.is_complete is False

    def test_add_message(self):
        p = GossipPanel(800, 600)
        p.start_session("metis", "kallos")
        p.add_message("metis", "Hello!")
        assert len(p.messages) == 1
        assert p.messages[0].agent_name == "metis"

    def test_set_response_options(self):
        p = GossipPanel(800, 600)
        p.set_response_options(
            [
                {"emoji": "👍", "label": "Agree", "preview": "I agree"},
                {"emoji": "👎", "label": "Disagree", "preview": "No way"},
            ]
        )
        assert len(p.response_buttons) == 2
        assert p.response_buttons[0].emoji == "👍"

    def test_end_session(self):
        p = GossipPanel(800, 600)
        p.start_session("a", "b")
        p.set_response_options([{"emoji": "x", "label": "y", "preview": "z"}])
        p.end_session()
        assert p.is_complete is True
        assert len(p.response_buttons) == 0

    def test_dismiss(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.dismiss()
        assert p.active is False

    def test_update_slide_animation(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.update(0.5)
        assert p.slide_x > 0.0

    def test_update_message_fade_in(self):
        p = GossipPanel(800, 600)
        p.start_session("a", "b")
        p.add_message("a", "hi")
        p.update(0.5)
        assert p.messages[0].alpha > 0.0

    def test_handle_event_hidden(self):
        p = GossipPanel(800, 600)
        p.slide_x = 0.0
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(700, 300))
        assert p.handle_event(event) is False

    def test_handle_event_click_inside(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.slide_x = 1.0
        cx = p.panel_rect.centerx
        cy = p.panel_rect.centery
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))
        assert p.handle_event(event) is True

    def test_handle_event_response_button_click(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.slide_x = 1.0
        p.set_response_options([{"emoji": "👍", "label": "Yes", "preview": "ok"}])
        p.response_buttons[0].rect = pygame.Rect(700, 400, 100, 36)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(750, 420))
        p.handle_event(event)
        assert p.selected_response == 0

    def test_handle_event_mousemotion(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.slide_x = 1.0
        p.set_response_options([{"emoji": "👍", "label": "Yes", "preview": "ok"}])
        p.response_buttons[0].rect = pygame.Rect(700, 400, 100, 36)
        event = pygame.event.Event(pygame.MOUSEMOTION, pos=(750, 420))
        p.handle_event(event)
        assert p.response_buttons[0].hovered is True

    def test_handle_event_mousewheel(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.slide_x = 1.0
        p._content_h = 1000
        with patch(
            "pygame.mouse.get_pos", return_value=(p.panel_rect.centerx, p.panel_rect.centery)
        ):
            event = pygame.event.Event(pygame.MOUSEWHEEL, y=-1)
            result = p.handle_event(event)
        assert result is True

    def test_get_selected_response(self):
        p = GossipPanel(800, 600)
        p.selected_response = 2
        idx = p.get_selected_response()
        assert idx == 2
        assert p.selected_response is None

    def test_get_selected_response_none(self):
        p = GossipPanel(800, 600)
        assert p.get_selected_response() is None

    def test_draw_hidden(self):
        p = GossipPanel(800, 600)
        p.slide_x = 0.0
        s = _surf()
        p.draw(s)  # returns early

    def test_draw_visible(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.slide_x = 1.0
        p.start_session("metis", "kallos")
        p.add_message("metis", "hello")
        p.messages[0].alpha = 255
        p.set_response_options([{"emoji": "👍", "label": "Yes", "preview": "ok"}])
        s = _surf()
        p.draw(s)

    def test_draw_complete_session(self):
        p = GossipPanel(800, 600)
        p.active = True
        p.slide_x = 1.0
        p.start_session("a", "b")
        p.add_message("a", "bye")
        p.messages[0].alpha = 255
        p.end_session()
        s = _surf()
        p.draw(s)

    def test_options_height_empty(self):
        p = GossipPanel(800, 600)
        assert p._options_height() == 0

    def test_options_height_with_buttons(self):
        p = GossipPanel(800, 600)
        p.set_response_options(
            [
                {"emoji": "a", "label": "b", "preview": "c"},
                {"emoji": "d", "label": "e", "preview": "f"},
            ]
        )
        assert p._options_height() > 0


# ===================================================================
# 3. memory_viewer.py
# ===================================================================
from hosts.gui.memory_viewer import ROMANCE_COLORS, TIER_COLORS, MemoryViewerPanel


class TestMemoryViewerPanel:
    def test_init(self):
        mv = MemoryViewerPanel(800, 600)
        assert mv.active is False
        assert mv.alpha == 0.0
        assert mv._profile_data is None

    def test_toggle_activates(self):
        mv = MemoryViewerPanel(800, 600)
        with patch.object(mv, "_refresh_data"):
            mv.toggle()
        assert mv.active is True
        assert mv._scroll_y == 0.0

    def test_toggle_deactivates(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.toggle()
        assert mv.active is False

    def test_update_alpha_increases(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.update(0.5)
        assert mv.alpha > 0

    def test_update_alpha_decreases(self):
        mv = MemoryViewerPanel(800, 600)
        mv.alpha = 200.0
        mv.active = False
        mv.update(0.5)
        assert mv.alpha < 200.0

    def test_handle_event_inactive(self):
        mv = MemoryViewerPanel(800, 600)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        assert mv.handle_event(event) is False

    def test_handle_event_click_inside(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 255
        cx = mv.panel_rect.centerx
        cy = mv.panel_rect.centery
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))
        assert mv.handle_event(event) is True
        assert mv.active is True  # click inside doesn't close

    def test_handle_event_click_outside_closes(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 255
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(1, 1))
        assert mv.handle_event(event) is True
        assert mv.active is False

    def test_handle_event_escape_closes(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 255
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        assert mv.handle_event(event) is True
        assert mv.active is False

    def test_handle_event_mousewheel(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 255
        with patch(
            "pygame.mouse.get_pos", return_value=(mv.panel_rect.centerx, mv.panel_rect.centery)
        ):
            event = pygame.event.Event(pygame.MOUSEWHEEL, y=-1)
            assert mv.handle_event(event) is True

    def test_score_to_tier(self):
        assert MemoryViewerPanel._score_to_tier(0.8) == "bonded"
        assert MemoryViewerPanel._score_to_tier(0.5) == "companion"
        assert MemoryViewerPanel._score_to_tier(0.2) == "acquaintance"
        assert MemoryViewerPanel._score_to_tier(0.1) == "stranger"

    def test_draw_hidden(self):
        mv = MemoryViewerPanel(800, 600)
        mv.alpha = 0.0
        s = _surf()
        mv.draw(s)  # returns early

    def test_draw_no_data(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 200.0
        mv._profile_data = None
        s = _surf()
        mv.draw(s)

    def test_draw_with_data(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 200.0
        mv._profile_data = {
            "display_name": "TestPlayer",
            "tts_name": "TestPlayer",
            "title": "Divine",
            "role": "divine",
            "pronouns": "they/them",
            "sovereignty": 75,
            "devotion": 50,
            "total_sessions": 10,
        }
        mv._affinities = {
            "metis": {"affinity_score": 0.6, "interaction_count": 15},
            "kallos": {"affinity_score": 0.3, "interaction_count": 5},
        }
        mv._memories = [
            {"content": "Discussed the forge project", "agent_name": "metis", "category": "plan"},
            {"content": "A" * 70, "agent_name": "kallos", "category": "style"},
        ]
        mv._romances = [
            {"agent_name": "kallos", "romance_stage": "spark"},
        ]
        mv._achievements = [
            {"name": "First Forge", "description": "Complete your first task"},
        ]
        s = _surf()
        mv.draw(s)

    def test_draw_with_different_tts_name(self):
        mv = MemoryViewerPanel(800, 600)
        mv.active = True
        mv.alpha = 200.0
        mv._profile_data = {
            "display_name": "Xiaoming",
            "tts_name": "Shao Ming",
            "title": "",
            "role": "mortal",
            "pronouns": "",
            "sovereignty": 10,
            "devotion": 90,
            "total_sessions": 1,
        }
        s = _surf()
        mv.draw(s)

    def test_refresh_data_graceful(self):
        mv = MemoryViewerPanel(800, 600)
        mv._refresh_data()  # should not raise regardless of module availability

    def test_tier_colors_dict(self):
        assert "stranger" in TIER_COLORS
        assert "bonded" in TIER_COLORS

    def test_romance_colors_dict(self):
        assert "none" in ROMANCE_COLORS
        assert "flame" in ROMANCE_COLORS


# ===================================================================
# 4. alignment_gauges.py
# ===================================================================
from hosts.gui.alignment_gauges import AlignmentGaugePanel


class TestAlignmentGaugePanel:
    def test_init(self):
        p = AlignmentGaugePanel(800, 600)
        assert p.active is False
        assert p.alpha == 0.0
        assert p.sovereignty == 0
        assert p.devotion == 0

    def test_toggle(self):
        p = AlignmentGaugePanel(800, 600)
        p.toggle()
        assert p.active is True
        p.toggle()
        assert p.active is False

    def test_update_values(self):
        p = AlignmentGaugePanel(800, 600)
        p.update_values(75, 50, "commander")
        assert p.sovereignty == 75
        assert p.devotion == 50
        assert p.archetype == "commander"

    def test_update_alpha_fades_in(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.update(0.5)
        assert p.alpha > 0

    def test_update_alpha_fades_out(self):
        p = AlignmentGaugePanel(800, 600)
        p.alpha = 200.0
        p.active = False
        p.update(0.5)
        assert p.alpha < 200.0

    def test_update_gauge_lerp(self):
        p = AlignmentGaugePanel(800, 600)
        p.sovereignty = 80
        p.devotion = 60
        p.update(0.5)
        assert p._sov_display > 0
        assert p._dev_display > 0

    def test_handle_event_inactive(self):
        p = AlignmentGaugePanel(800, 600)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 50))
        assert p.handle_event(event) is False

    def test_handle_event_click_inside(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.alpha = 255
        cx = p.panel_rect.centerx
        cy = p.panel_rect.centery
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))
        assert p.handle_event(event) is True

    def test_handle_event_click_outside(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.alpha = 255
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(700, 500))
        assert p.handle_event(event) is False

    def test_draw_hidden(self):
        p = AlignmentGaugePanel(800, 600)
        p.alpha = 0.0
        s = _surf()
        p.draw(s)

    def test_draw_visible(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.alpha = 200.0
        p.sovereignty = 50
        p.devotion = 40
        p._sov_display = 50.0
        p._dev_display = 40.0
        p.archetype = "professional"
        s = _surf()
        p.draw(s)

    def test_draw_commander_archetype(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.alpha = 200.0
        p.sovereignty = 85
        p.devotion = 85
        p._sov_display = 85.0
        p._dev_display = 85.0
        p.archetype = "commander"
        s = _surf()
        p.draw(s)

    def test_draw_high_sovereignty(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.alpha = 200.0
        p.sovereignty = 70
        p.devotion = 30
        p._sov_display = 70.0
        p._dev_display = 30.0
        p.archetype = "sovereign"
        s = _surf()
        p.draw(s)

    def test_draw_high_devotion(self):
        p = AlignmentGaugePanel(800, 600)
        p.active = True
        p.alpha = 200.0
        p.sovereignty = 30
        p.devotion = 70
        p._sov_display = 30.0
        p._dev_display = 70.0
        p.archetype = "devoted"
        s = _surf()
        p.draw(s)


# ===================================================================
# 5. onboarding_ui.py
# ===================================================================
from hosts.gui.onboarding_ui import (
    STEP_DONE,
    STEP_NAME,
    STEP_PRONOUNS,
    STEP_PRONUNCIATION,
    STEP_TITLE,
    STEP_WELCOME,
    OnboardingOverlay,
)


class TestOnboardingOverlay:
    def test_init(self):
        o = OnboardingOverlay(800, 600)
        assert o.active is False
        assert o.step == STEP_NAME
        assert o._result is None

    def test_start(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        assert o.active is True
        assert o.step == STEP_NAME

    def test_get_result_none(self):
        o = OnboardingOverlay(800, 600)
        assert o.get_result() is None

    def test_update(self):
        o = OnboardingOverlay(800, 600)
        o.active = True
        o.update(0.5)
        assert o.alpha > 0

    def test_handle_event_inactive(self):
        o = OnboardingOverlay(800, 600)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        assert o.handle_event(event) is False

    def test_name_step_typing(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="A")
        o.handle_event(event)
        assert o.name_text == "A"

    def test_name_step_backspace(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.name_text = "AB"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="\b")
        o.handle_event(event)
        assert o.name_text == "A"

    def test_name_step_enter_advances(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.name_text = "TestName"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_PRONUNCIATION
        assert o.tts_text == "TestName"

    def test_name_step_enter_empty_stays(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.name_text = ""
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_NAME

    def test_pronunciation_step_typing(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_PRONUNCIATION
        o.tts_text = "Test"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, unicode="x")
        o.handle_event(event)
        assert o.tts_text == "Testx"

    def test_pronunciation_step_enter_advances(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_PRONUNCIATION
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_TITLE

    def test_title_step_click(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_TITLE
        o.name_text = "Test"
        # Draw to populate _button_rects
        s = _surf()
        o.draw(s)
        if o._button_rects:
            rect = o._button_rects[0]
            o._handle_click((rect.centerx, rect.centery))
            assert o.step == STEP_PRONOUNS

    def test_pronouns_step_click(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_PRONOUNS
        # Draw to populate _button_rects
        s = _surf()
        o.draw(s)
        if o._button_rects:
            rect = o._button_rects[0]
            o._handle_click((rect.centerx, rect.centery))
            assert o.step == STEP_WELCOME

    def test_welcome_step_enter_finalizes(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_WELCOME
        o.name_text = "Player"
        o.tts_text = "Player"
        o.selected_role = "mortal"
        o.selected_title = "artisan"
        o.selected_pronouns = "they/them"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_DONE
        assert o.active is False
        result = o.get_result()
        assert result is not None
        assert result["display_name"] == "Player"
        assert result["role"] == "mortal"

    def test_welcome_step_click_finalizes(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_WELCOME
        o.name_text = "Player"
        o._handle_click((400, 300))
        assert o.step == STEP_DONE

    def test_finalize_defaults(self):
        o = OnboardingOverlay(800, 600)
        o.name_text = "  Test  "
        o.tts_text = ""
        o._finalize()
        result = o.get_result()
        assert result is not None
        assert result["display_name"] == "Test"
        assert result["tts_name"] == "Test"
        assert result["role"] == "mortal"

    def test_update_hover(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_TITLE
        s = _surf()
        o.draw(s)
        if o._button_rects:
            rect = o._button_rects[1]
            o._update_hover((rect.centerx, rect.centery))
            assert o._hovered_option == 1

    def test_mousemotion_consumed(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        event = pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 300))
        assert o.handle_event(event) is True

    def test_draw_all_steps(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 200.0
        o.name_text = "Test"
        o.tts_text = "Test"
        o.selected_title = "artisan"
        s = _surf()

        for step in [STEP_NAME, STEP_PRONUNCIATION, STEP_TITLE, STEP_PRONOUNS, STEP_WELCOME]:
            o.step = step
            o._button_rects.clear()
            o.draw(s)

    def test_draw_hidden(self):
        o = OnboardingOverlay(800, 600)
        o.alpha = 0.0
        s = _surf()
        o.draw(s)


# ===================================================================
# 6. portrait.py
# ===================================================================
from hosts.gui.portrait import PortraitPanel, load_avatar


class TestPortraitPanel:
    def test_init(self):
        p = PortraitPanel()
        assert p._current == "hephaestus"
        assert p._prev is None
        assert p._fading is False

    def test_switch_to_new_agent(self):
        p = PortraitPanel()
        p.switch_to("metis")
        assert p._current == "metis"
        assert p._prev == "hephaestus"
        assert p._fading is True
        assert p._fade_t == 1.0

    def test_switch_to_same_agent(self):
        p = PortraitPanel()
        p.switch_to("hephaestus")
        assert p._fading is False

    def test_switch_to_unknown_agent(self):
        p = PortraitPanel()
        p.switch_to("nonexistent")
        assert p._current == "hephaestus"
        assert p._fading is False

    def test_update_fading(self):
        p = PortraitPanel()
        p.switch_to("metis")
        p.update(0.5)
        assert p._fade_t < 1.0

    def test_update_fade_completes(self):
        p = PortraitPanel()
        p.switch_to("metis")
        p.update(10.0)  # large dt
        assert p._fade_t == 0.0
        assert p._fading is False

    def test_update_not_fading(self):
        p = PortraitPanel()
        p.update(0.5)  # should not raise

    def test_draw(self):
        p = PortraitPanel()
        s = _surf()
        with patch("hosts.gui.portrait._get_avatar", return_value=None):
            p.draw(s)

    def test_draw_with_fade(self):
        p = PortraitPanel()
        p.switch_to("metis")
        s = _surf()
        with patch("hosts.gui.portrait._get_avatar", return_value=None):
            p.draw(s)

    def test_draw_with_quote(self):
        p = PortraitPanel()
        p.current_quote = "The forge awaits your command, master."
        s = _surf()
        with patch("hosts.gui.portrait._get_avatar", return_value=None):
            p.draw(s)

    def test_load_avatar_no_path(self):
        with patch("hosts.gui.portrait.get_avatar_path", return_value=None):
            result = load_avatar("nonexistent")
        assert result is None

    def test_load_avatar_bad_file(self):
        with patch("hosts.gui.portrait.get_avatar_path", return_value="/nonexistent/path.png"):
            result = load_avatar("test")
        assert result is None


# ===================================================================
# 7. portrait_flash_integration.py
# ===================================================================
from hosts.gui.portrait_flash_integration import PortraitFlashIntegration


class TestPortraitFlashIntegration:
    def test_init(self):
        pfi = PortraitFlashIntegration()
        assert pfi.enabled is True
        assert pfi._last_agent is None

    def test_on_agent_switch(self):
        pfi = PortraitFlashIntegration()
        pfi.on_agent_switch("metis")
        assert pfi._last_agent == "metis"
        assert not pfi.flash_effect.is_complete()

    def test_on_agent_switch_disabled(self):
        pfi = PortraitFlashIntegration(enabled=False)
        pfi.on_agent_switch("metis")
        assert pfi._last_agent is None

    def test_update(self):
        pfi = PortraitFlashIntegration()
        pfi.on_agent_switch("metis")
        active, alpha = pfi.update(0.1)
        assert isinstance(active, bool)
        assert isinstance(alpha, int)

    def test_get_flash_alpha(self):
        pfi = PortraitFlashIntegration()
        pfi.on_agent_switch("metis")
        alpha = pfi.get_flash_alpha()
        assert isinstance(alpha, int)

    def test_is_active(self):
        pfi = PortraitFlashIntegration()
        assert pfi.is_active() is False
        pfi.on_agent_switch("metis")
        assert pfi.is_active() is True

    def test_set_enabled(self):
        pfi = PortraitFlashIntegration()
        pfi.on_agent_switch("metis")
        pfi.set_enabled(False)
        assert pfi.enabled is False

    def test_reset(self):
        pfi = PortraitFlashIntegration()
        pfi.on_agent_switch("metis")
        pfi.reset()
        assert pfi._last_agent is None
        assert pfi.flash_effect.is_complete()


# ===================================================================
# 8. typewriter_flash_integration.py
# ===================================================================
from hosts.gui.flash_effect import FlashEffect
from hosts.gui.typewriter import TypewriterManager
from hosts.gui.typewriter_flash_integration import TypewriterFlashIntegration


class TestTypewriterFlashIntegration:
    def _make(self) -> TypewriterFlashIntegration:
        tw = TypewriterManager()
        fe = FlashEffect()
        return TypewriterFlashIntegration(tw, fe)

    def test_init(self):
        tfi = self._make()
        assert tfi.enabled is True
        assert tfi._was_paused_before_flash is False

    def test_on_flash_start_pauses(self):
        tfi = self._make()
        tfi.typewriter.start("Hello world", speed_ms=50)
        tfi.on_flash_start()
        assert tfi.typewriter.paused is True

    def test_on_flash_start_disabled(self):
        tfi = self._make()
        tfi.enabled = False
        tfi.typewriter.start("Hello", speed_ms=50)
        tfi.on_flash_start()
        assert tfi.typewriter.paused is False

    def test_on_flash_complete_resumes(self):
        tfi = self._make()
        tfi.typewriter.start("Hello world", speed_ms=50)
        tfi.on_flash_start()
        assert tfi.typewriter.paused is True
        tfi.on_flash_complete()
        assert tfi.typewriter.paused is False

    def test_on_flash_complete_disabled(self):
        tfi = self._make()
        tfi.enabled = False
        tfi.on_flash_complete()  # should not raise

    def test_trigger_flash_with_pause(self):
        tfi = self._make()
        tfi.typewriter.start("Hello", speed_ms=50)
        tfi.trigger_flash_with_pause()
        assert tfi.typewriter.paused is True
        assert not tfi.flash_effect.is_complete()

    def test_trigger_flash_with_pause_disabled(self):
        tfi = self._make()
        tfi.enabled = False
        tfi.trigger_flash_with_pause()
        assert tfi.flash_effect.is_complete()

    def test_update_auto_resumes(self):
        tfi = self._make()
        tfi.typewriter.start("Hello", speed_ms=50)
        tfi.trigger_flash_with_pause(duration_ms=10)
        tfi.update(1.0)  # long enough to complete flash
        assert tfi.typewriter.paused is False

    def test_set_enabled(self):
        tfi = self._make()
        tfi.set_enabled(False)
        assert tfi.enabled is False

    def test_reset(self):
        tfi = self._make()
        tfi.typewriter.start("Hello", speed_ms=50)
        tfi.on_flash_start()
        tfi.reset()


# ===================================================================
# 9. gui_components_integration.py
# ===================================================================
from hosts.gui.gui_components_integration import GUIComponentsIntegration


class TestGUIComponentsIntegration:
    def test_init(self):
        gui = Mock()
        with patch("hosts.gui.gui_components_integration.SettingsManager") as MockSM:
            MockSM.return_value.get = Mock(return_value=False)
            gci = GUIComponentsIntegration(gui)
        assert gci.gui is gui

    def test_save_all_settings(self):
        gui = Mock()
        with patch("hosts.gui.gui_components_integration.SettingsManager") as MockSM:
            sm = MockSM.return_value
            sm.get = Mock(return_value=False)
            sm.set = Mock()
            sm.save = Mock()
            gci = GUIComponentsIntegration(gui)
            gci.save_all_settings()
            sm.save.assert_called_once()

    def test_getters(self):
        gui = Mock()
        with patch("hosts.gui.gui_components_integration.SettingsManager") as MockSM:
            MockSM.return_value.get = Mock(return_value=False)
            gci = GUIComponentsIntegration(gui)
        assert gci.get_settings_manager() is not None
        assert gci.get_font_scaler() is not None
        assert gci.get_status_bubbles() is not None
        assert gci.get_pipeline_status() is not None
        assert gci.get_scratchpad() is not None
        assert gci.get_high_contrast() is not None
        assert gci.get_agent_personalities() is not None
        assert gci.get_agent_handoff() is not None


# ===================================================================
# 10. high_contrast_gui_integration.py
# ===================================================================
from hosts.gui.high_contrast_gui_integration import HighContrastGUIIntegration


class TestHighContrastGUIIntegration:
    def _make(self):
        gui = Mock()
        settings = Mock()
        settings.get = Mock(return_value=False)
        settings.set = Mock()
        settings.save = Mock()
        return HighContrastGUIIntegration(gui, settings)

    def test_init(self):
        hci = self._make()
        assert hci.high_contrast_enabled is False

    def test_enable(self):
        hci = self._make()
        hci.enable_high_contrast()
        assert hci.high_contrast_enabled is True
        hci.settings.set.assert_called_with("high_contrast", True)

    def test_disable(self):
        hci = self._make()
        hci.high_contrast_enabled = True
        hci.disable_high_contrast()
        assert hci.high_contrast_enabled is False

    def test_toggle(self):
        hci = self._make()
        hci.toggle_high_contrast()
        assert hci.high_contrast_enabled is True
        hci.toggle_high_contrast()
        assert hci.high_contrast_enabled is False

    def test_is_enabled(self):
        hci = self._make()
        assert hci.is_high_contrast_enabled() is False

    def test_get_color_palette(self):
        hci = self._make()
        palette = hci.get_color_palette()
        assert isinstance(palette, dict)

    def test_get_color(self):
        hci = self._make()
        color = hci.get_color("gold")
        assert isinstance(color, tuple)

    def test_get_color_missing(self):
        hci = self._make()
        color = hci.get_color("nonexistent_color_xyz")
        assert color == (255, 255, 255)

    def test_verify_wcag(self):
        hci = self._make()
        result = hci.verify_wcag_compliance((255, 255, 255), (0, 0, 0))
        assert isinstance(result, bool)


# ===================================================================
# 11. pipeline_status_gui_integration.py
# ===================================================================
from hosts.gui.pipeline_status_gui_integration import PipelineStatusGUIIntegration


class TestPipelineStatusGUIIntegration:
    def test_init(self):
        gui = Mock()
        pi = PipelineStatusGUIIntegration(gui)
        assert pi.gui is gui

    def test_update_current_agent(self):
        pi = PipelineStatusGUIIntegration(Mock())
        pi.update_current_agent("metis")
        assert pi.get_current_agent() == "metis"

    def test_add_remove_queue(self):
        pi = PipelineStatusGUIIntegration(Mock())
        pi.add_agent_to_queue("kallos")
        assert "kallos" in pi.get_processing_queue()
        pi.remove_agent_from_queue("kallos")
        assert "kallos" not in pi.get_processing_queue()

    def test_loading_state(self):
        pi = PipelineStatusGUIIntegration(Mock())
        pi.set_loading_state(True)
        assert pi.is_loading() is True
        pi.set_loading_state(False)
        assert pi.is_loading() is False

    def test_clear_pipeline(self):
        pi = PipelineStatusGUIIntegration(Mock())
        pi.add_agent_to_queue("a")
        pi.clear_pipeline()
        assert len(pi.get_processing_queue()) == 0

    def test_get_indicator(self):
        pi = PipelineStatusGUIIntegration(Mock())
        assert pi.get_indicator() is not None


# ===================================================================
# 12. scratchpad_gui_integration.py
# ===================================================================
from hosts.gui.scratchpad_gui_integration import ScratchpadGUIIntegration


class TestScratchpadGUIIntegration:
    def test_init(self):
        si = ScratchpadGUIIntegration(Mock())
        assert si.scratchpad is not None

    def test_add_plan(self):
        si = ScratchpadGUIIntegration(Mock())
        si.add_plan("Step 1", "metis")
        assert "metis" in si.scratchpad._content_by_agent

    def test_set_active_agent(self):
        si = ScratchpadGUIIntegration(Mock())
        si.set_active_agent("kallos")
        assert si.scratchpad._active_agent == "kallos"

    def test_toggle(self):
        si = ScratchpadGUIIntegration(Mock())
        si.toggle()
        assert si.scratchpad.is_open is True

    def test_handle_event(self):
        si = ScratchpadGUIIntegration(Mock())
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))
        result = si.handle_event(event)
        assert result is False

    def test_draw(self):
        si = ScratchpadGUIIntegration(Mock())
        s = _surf()
        rect = pygame.Rect(0, 0, 300, 400)
        si.draw(s, rect)


# ===================================================================
# 13. status_bubbles_gui_integration.py
# ===================================================================
from hosts.gui.status_bubbles_gui_integration import StatusBubblesGUIIntegration


class TestStatusBubblesGUIIntegration:
    def test_init(self):
        sbi = StatusBubblesGUIIntegration(Mock())
        assert sbi.status_bubbles is not None

    def test_add_status(self):
        sbi = StatusBubblesGUIIntegration(Mock())
        sbi.add_status_message("test")

    def test_get_bubbles(self):
        sbi = StatusBubblesGUIIntegration(Mock())
        assert sbi.get_status_bubbles() is not None

    def test_clear(self):
        sbi = StatusBubblesGUIIntegration(Mock())
        sbi.add_status_message("test")
        sbi.clear_all_status()


# ===================================================================
# 14. loading_screen.py
# ===================================================================
from hosts.gui.loading_screen import (
    PHASE_CARD_1,
    PHASE_CARD_2,
    PHASE_FADE_OUT,
    PHASE_READY,
    PHASE_SPLASH,
    _draw_text_card,
    _get_vignette,
    _load_splash,
    _LoadingEmber,
)


class TestLoadingEmber:
    def test_init(self):
        e = _LoadingEmber(800, 600)
        assert e.alpha > 0
        assert 0 <= e.x <= 800
        assert 0 <= e.y <= 600

    def test_update(self):
        e = _LoadingEmber(800, 600)
        e.update(0.016, 800, 600)
        # Position should have changed
        assert isinstance(e.x, float)

    def test_update_respawns_dead(self):
        e = _LoadingEmber(800, 600)
        e.alpha = 0.0
        e.decay = 1000
        e.update(1.0, 800, 600)
        assert e.alpha > 0  # respawned

    def test_draw_alive(self):
        e = _LoadingEmber(800, 600)
        e.alpha = 100
        s = _surf()
        e.draw(s)

    def test_draw_dead(self):
        e = _LoadingEmber(800, 600)
        e.alpha = 0
        s = _surf()
        e.draw(s)  # returns early


class TestLoadingScreenHelpers:
    def test_get_vignette(self):
        v = _get_vignette(800, 600)
        assert isinstance(v, pygame.Surface)
        assert v.get_size() == (800, 600)

    def test_get_vignette_cached(self):
        v1 = _get_vignette(400, 300)
        v2 = _get_vignette(400, 300)
        assert v1 is v2

    def test_load_splash_no_file(self):
        with patch("hosts.gui.loading_screen._SPLASH_IMAGE") as mock_path:
            mock_path.exists.return_value = False
            result = _load_splash(800, 600)
        assert result is None

    def test_draw_text_card_fade_in(self):
        s = _surf()
        f = _font()
        _draw_text_card(s, 800, 600, 0.5, f, "Main Text", "Sub Text", f)

    def test_draw_text_card_hold(self):
        s = _surf()
        f = _font()
        _draw_text_card(s, 800, 600, 2.0, f, "Main Text", None, None)

    def test_draw_text_card_fade_out(self):
        s = _surf()
        f = _font()
        _draw_text_card(s, 800, 600, 3.0, f, "Main Text", "Sub", f)

    def test_draw_text_card_gone(self):
        s = _surf()
        f = _font()
        _draw_text_card(s, 800, 600, 10.0, f, "Main Text", "Sub", f)

    def test_phase_constants(self):
        assert PHASE_CARD_1 == 0
        assert PHASE_CARD_2 == 1
        assert PHASE_SPLASH == 2
        assert PHASE_READY == 3
        assert PHASE_FADE_OUT == 4


# ===================================================================
# 15. profile_select.py
# ===================================================================
from hosts.gui.profile_select import (
    CARD_H,
    CARD_W,
    MAX_VISIBLE,
    _card_rect,
    _confirm_delete_rect,
    _draw_delete_confirmation,
    _draw_new_game_button,
    _draw_profile_card,
    _new_game_rect,
)


class TestProfileSelectHelpers:
    def test_card_rect_visible(self):
        rect = _card_rect(800, 600, 0, 0, 3)
        assert rect is not None
        assert rect.width == CARD_W
        assert rect.height == CARD_H

    def test_card_rect_scrolled_out(self):
        rect = _card_rect(800, 600, 0, 5, 10)
        assert rect is None

    def test_card_rect_beyond_max(self):
        rect = _card_rect(800, 600, MAX_VISIBLE, 0, MAX_VISIBLE + 1)
        assert rect is None

    def test_new_game_rect(self):
        rect = _new_game_rect(800, 600, 3, 0)
        assert isinstance(rect, pygame.Rect)
        assert rect.width == CARD_W

    def test_confirm_delete_rect(self):
        rect = _confirm_delete_rect(800, 600)
        assert isinstance(rect, pygame.Rect)
        assert rect.width == 340

    def test_draw_profile_card(self):
        s = _surf()
        rect = pygame.Rect(100, 100, CARD_W, CARD_H)
        profile = {
            "display_name": "TestPlayer",
            "role": "divine",
            "title": "God-King",
            "pronouns": "he/him",
            "total_sessions": 42,
            "sovereignty": 80,
            "devotion": 30,
            "is_active": False,
        }
        nf = _font()
        df = _font()
        _draw_profile_card(s, rect, profile, nf, df, 255, False, False, False)

    def test_draw_profile_card_hovered(self):
        s = _surf()
        rect = pygame.Rect(100, 100, CARD_W, CARD_H)
        profile = {
            "display_name": "P",
            "role": "mortal",
            "title": "",
            "pronouns": "",
            "total_sessions": 1,
            "sovereignty": 0,
            "devotion": 0,
            "is_active": False,
        }
        nf = _font()
        df = _font()
        _draw_profile_card(s, rect, profile, nf, df, 255, True, False, False)

    def test_draw_profile_card_active(self):
        s = _surf()
        rect = pygame.Rect(100, 100, CARD_W, CARD_H)
        profile = {
            "display_name": "P",
            "role": "devoted",
            "title": "Beloved",
            "pronouns": "she/her",
            "total_sessions": 5,
            "sovereignty": 50,
            "devotion": 50,
            "is_active": True,
        }
        nf = _font()
        df = _font()
        _draw_profile_card(s, rect, profile, nf, df, 255, False, True, False)

    def test_draw_profile_card_delete_hovered(self):
        s = _surf()
        rect = pygame.Rect(100, 100, CARD_W, CARD_H)
        profile = {
            "display_name": "P",
            "role": "mortal",
            "title": "",
            "pronouns": "",
            "total_sessions": 0,
            "sovereignty": 0,
            "devotion": 0,
            "is_active": False,
        }
        nf = _font()
        df = _font()
        _draw_profile_card(s, rect, profile, nf, df, 255, False, False, True)

    def test_draw_new_game_button(self):
        s = _surf()
        rect = pygame.Rect(100, 500, CARD_W, 50)
        f = _font()
        _draw_new_game_button(s, rect, f, 255, False)

    def test_draw_new_game_button_hovered(self):
        s = _surf()
        rect = pygame.Rect(100, 500, CARD_W, 50)
        f = _font()
        _draw_new_game_button(s, rect, f, 255, True)

    def test_draw_delete_confirmation(self):
        s = _surf()
        profile = {"display_name": "TestPlayer"}
        bf = _font()
        df = _font()
        _draw_delete_confirmation(s, 800, 600, profile, bf, df)


# ===================================================================
# 16. tts_engine.py
# ===================================================================
from hosts.gui.tts_engine import AGENT_VOICES, VOICE_ROSTER, VoiceConfig


class TestVoiceConfig:
    def test_init(self):
        vc = VoiceConfig("Test", "en-US-TestNeural")
        assert vc.name == "Test"
        assert vc.edge_id == "en-US-TestNeural"
        assert vc.speed == 1.0
        assert vc.pitch == 1.0
        assert vc.emotion == "default"

    def test_custom_values(self):
        vc = VoiceConfig("Custom", "en-US-JennyNeural", speed=0.9, pitch=1.2, emotion="cheerful")
        assert vc.speed == 0.9
        assert vc.pitch == 1.2
        assert vc.emotion == "cheerful"


class TestVoiceRoster:
    def test_roster_has_voices(self):
        assert len(VOICE_ROSTER) >= 5
        assert "aria" in VOICE_ROSTER
        assert "jenny" in VOICE_ROSTER

    def test_all_agents_have_voices(self):
        for agent, voice_key in AGENT_VOICES.items():
            assert voice_key in VOICE_ROSTER, f"Agent {agent} maps to unknown voice {voice_key}"

    def test_agent_voices_complete(self):
        expected = {"hephaestus", "metis", "kallos", "mneme", "techne", "dokimasia"}
        assert expected.issubset(set(AGENT_VOICES.keys()))


# ===================================================================
# 17. audio_manager.py — generate_ambient_wave (pure logic)
# ===================================================================


class TestAudioManagerGenerateWave:
    """Test the pure-logic _generate_ambient_wave method without mixer init."""

    def test_generate_ambient_wave(self):
        from hosts.gui.audio_manager import AudioManager

        # Bypass singleton + mixer init
        am = object.__new__(AudioManager)
        wav_data = am._generate_ambient_wave()
        assert isinstance(wav_data, bytes)
        assert len(wav_data) > 44  # At least a WAV header
