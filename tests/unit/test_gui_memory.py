from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.memory_viewer import ROMANCE_COLORS, TIER_COLORS, MemoryViewerPanel
from tests.unit.gui_test_helpers import _surf


class TestMemoryViewerPanel:
    def test_init(self):
        mv = MemoryViewerPanel(800, 600)
        assert mv.active is False
        assert mv.alpha == 0.0
        assert mv._profile_data is None

    def test_update_layout_repositions_panel(self):
        mv = MemoryViewerPanel(800, 600)

        mv.update_layout(1280, 720)

        assert mv.panel_rect.center == (640, 360)

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
            "pygame.mouse.get_pos",
            return_value=(mv.panel_rect.centerx, mv.panel_rect.centery),
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
            {
                "content": "Discussed the forge project",
                "agent_name": "metis",
                "category": "plan",
            },
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
