from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.flash_effect import FlashEffect
from hosts.gui.gui_components_integration import GUIComponentsIntegration
from hosts.gui.high_contrast_gui_integration import HighContrastGUIIntegration
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
        assert gci.get_high_contrast() is not None


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
