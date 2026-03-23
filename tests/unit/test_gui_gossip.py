from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.dialogue import draw_banner
from hosts.gui.gossip_panel import GossipMessage, GossipPanel, GossipResponseButton
from tests.unit.gui_test_helpers import _surf


class TestDrawBanner:
    def test_draw_banner_connected(self):
        s = _surf()
        draw_banner(s, True, "http://localhost:10000")

    def test_draw_banner_disconnected(self):
        s = _surf()
        draw_banner(s, False, "")


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

    def test_update_layout_reanchors_panel(self):
        p = GossipPanel(800, 600)

        p.update_layout(1280, 720)

        assert p.panel_rect.right == 1280
        assert p.panel_rect.height == 600

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
            "pygame.mouse.get_pos",
            return_value=(p.panel_rect.centerx, p.panel_rect.centery),
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
