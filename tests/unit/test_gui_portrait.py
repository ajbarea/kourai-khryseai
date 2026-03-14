# ruff: noqa: E402
from __future__ import annotations

from unittest.mock import patch

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.portrait import PortraitPanel, load_avatar
from hosts.gui.portrait_flash_integration import PortraitFlashIntegration
from tests.unit.gui_test_helpers import _surf


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
