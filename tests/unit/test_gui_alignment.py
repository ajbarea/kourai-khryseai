from __future__ import annotations

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.alignment_gauges import AlignmentGaugePanel
from tests.unit.gui_test_helpers import _surf


class TestAlignmentGaugePanel:
    def test_init(self):
        p = AlignmentGaugePanel(800, 600)
        assert p.active is False
        assert p.alpha == 0.0
        assert p.sovereignty == 0
        assert p.devotion == 0

    def test_update_layout_tracks_screen_size(self):
        p = AlignmentGaugePanel(800, 600)

        p.update_layout(1280, 720)

        assert p.screen_w == 1280
        assert p.screen_h == 720

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
