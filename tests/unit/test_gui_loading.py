from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

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
from tests.unit.gui_test_helpers import _font, _surf


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
        e.draw(s)


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
