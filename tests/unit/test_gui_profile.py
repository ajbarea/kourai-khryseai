from __future__ import annotations

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

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
from tests.unit.gui_test_helpers import _font, _surf


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
