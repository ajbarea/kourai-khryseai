"""Comprehensive tests for pygame-dependent GUI widget modules.

Covers:
- hosts/gui/settings_widgets.py + hosts/gui/settings_overlay.py
  (TabButton, VolumeSlider, ToggleSwitch, Button, CycleButton, SettingsOverlay)
- hosts/gui/input_bar.py    (InputBar)
- hosts/gui/scratchpad.py   (Scratchpad)
- hosts/gui/quick_actions.py (QuickAction, QuickActionBar)
- hosts/gui/particles.py    (Ember, ParticleSystem)

"""

from __future__ import annotations

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()

from unittest.mock import Mock, patch

import pygame.freetype

pygame.freetype.init()

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_surface(w: int = 200, h: int = 200) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _make_font() -> pygame.freetype.Font:
    return pygame.freetype.SysFont("arial", 14)


def _make_palette() -> dict:
    return {
        "gold": (218, 165, 32),
        "text": (255, 255, 255),
        "bubble_bg": (30, 22, 10),
        "scrollbar": (160, 155, 145),
        "bubble_border": (218, 165, 32),
    }


def _make_gui_integration() -> Mock:
    """Build a Mock that satisfies SettingsOverlay's constructor expectations."""
    gui = Mock()
    gui.settings = Mock()
    gui.settings.get = Mock(side_effect=lambda key, default=None: default)
    gui.settings.set = Mock()
    gui.high_contrast = Mock()
    gui.high_contrast.get_color_palette = Mock(return_value=_make_palette())
    gui.high_contrast.enable_high_contrast = Mock()
    gui.high_contrast.disable_high_contrast = Mock()
    gui.save_all_settings = Mock()
    return gui


# ===================================================================
# 1. settings widgets + overlay
# ===================================================================
from hosts.gui.settings_overlay import SettingsOverlay
from hosts.gui.settings_widgets import (
    Button,
    CycleButton,
    TabButton,
    ToggleSwitch,
    VolumeSlider,
)


class TestTabButton:
    def test_init(self):
        cb = Mock()
        tb = TabButton(10, 20, 100, 30, "Display", "display", cb)
        assert tb.rect == pygame.Rect(10, 20, 100, 30)
        assert tb.label == "Display"
        assert tb.tab_id == "display"
        assert tb.hovered is False
        assert tb.active is False

    def test_update_hover_inside(self):
        tb = TabButton(0, 0, 100, 30, "X", "x", Mock())
        tb.update((50, 15))
        assert tb.hovered is True

    def test_update_hover_outside(self):
        tb = TabButton(0, 0, 100, 30, "X", "x", Mock())
        tb.update((200, 200))
        assert tb.hovered is False

    def test_handle_click_hit(self):
        cb = Mock()
        tb = TabButton(0, 0, 100, 30, "X", "x", cb)
        result = tb.handle_click((50, 15))
        assert result is True
        cb.assert_called_once_with("x")

    def test_handle_click_miss(self):
        cb = Mock()
        tb = TabButton(0, 0, 100, 30, "X", "x", cb)
        result = tb.handle_click((200, 200))
        assert result is False
        cb.assert_not_called()

    def test_draw_active(self):
        tb = TabButton(0, 0, 80, 24, "Tab", "t", Mock())
        tb.active = True
        surf = _make_surface()
        font = _make_font()
        tb.draw(surf, font, _make_palette())  # should not raise

    def test_draw_hovered(self):
        tb = TabButton(0, 0, 80, 24, "Tab", "t", Mock())
        tb.hovered = True
        surf = _make_surface()
        font = _make_font()
        tb.draw(surf, font, _make_palette())

    def test_draw_default(self):
        tb = TabButton(0, 0, 80, 24, "Tab", "t", Mock())
        surf = _make_surface()
        font = _make_font()
        tb.draw(surf, font, _make_palette())


class TestVolumeSlider:
    def test_init_clamps_value(self):
        vs = VolumeSlider(0, 0, 200, 20, 1.5, Mock())
        assert vs.value == 1.0
        vs2 = VolumeSlider(0, 0, 200, 20, -0.5, Mock())
        assert vs2.value == 0.0

    def test_init_normal_value(self):
        vs = VolumeSlider(0, 0, 200, 20, 0.5, Mock())
        assert vs.value == pytest.approx(0.5)
        assert vs.dragging is False

    def test_handle_mousedown_hit(self):
        cb = Mock()
        vs = VolumeSlider(0, 10, 200, 20, 0.5, cb)
        result = vs.handle_mousedown((100, 20))
        assert result is True
        assert vs.dragging is True
        cb.assert_called_once()

    def test_handle_mousedown_miss(self):
        cb = Mock()
        vs = VolumeSlider(0, 10, 200, 20, 0.5, cb)
        result = vs.handle_mousedown((300, 300))
        assert result is False
        assert vs.dragging is False
        cb.assert_not_called()

    def test_handle_mousemotion_while_dragging(self):
        cb = Mock()
        vs = VolumeSlider(0, 10, 200, 20, 0.5, cb)
        vs.dragging = True
        result = vs.handle_mousemotion((150, 20))
        assert result is True
        cb.assert_called_once()

    def test_handle_mousemotion_not_dragging(self):
        cb = Mock()
        vs = VolumeSlider(0, 10, 200, 20, 0.5, cb)
        result = vs.handle_mousemotion((150, 20))
        assert result is False
        cb.assert_not_called()

    def test_handle_mouseup(self):
        vs = VolumeSlider(0, 10, 200, 20, 0.5, Mock())
        vs.dragging = True
        vs.handle_mouseup()
        assert vs.dragging is False

    def test_draw(self):
        vs = VolumeSlider(10, 10, 180, 20, 0.7, Mock())
        surf = _make_surface()
        vs.draw(surf, _make_palette())  # should not raise

    def test_knob_x_at_zero(self):
        vs = VolumeSlider(0, 0, 200, 20, 0.0, Mock())
        kx = vs._knob_x()
        assert kx == vs.rect.x + vs._knob_radius

    def test_knob_x_at_one(self):
        vs = VolumeSlider(0, 0, 200, 20, 1.0, Mock())
        kx = vs._knob_x()
        expected = vs.rect.x + vs._knob_radius + (vs.rect.width - vs._knob_radius * 2)
        assert kx == pytest.approx(expected)

    def test_value_from_x_clamps(self):
        vs = VolumeSlider(0, 0, 200, 20, 0.5, Mock())
        assert vs._value_from_x(-100) == 0.0
        assert vs._value_from_x(9999) == 1.0


class TestToggleSwitch:
    def test_init_off(self):
        ts = ToggleSwitch(0, 0, 40, 24, False, Mock())
        assert ts.state is False
        assert ts.anim_t == 0.0

    def test_init_on(self):
        ts = ToggleSwitch(0, 0, 40, 24, True, Mock())
        assert ts.state is True
        assert ts.anim_t == 1.0

    def test_update_animation_towards_on(self):
        ts = ToggleSwitch(0, 0, 40, 24, True, Mock())
        ts.anim_t = 0.0  # force mismatch
        ts.update(0.1)
        assert ts.anim_t > 0.0  # moved toward 1.0

    def test_update_animation_towards_off(self):
        ts = ToggleSwitch(0, 0, 40, 24, False, Mock())
        ts.anim_t = 1.0  # force mismatch
        ts.update(0.1)
        assert ts.anim_t < 1.0  # moved toward 0.0

    def test_handle_click_toggles(self):
        cb = Mock()
        ts = ToggleSwitch(0, 0, 40, 24, False, cb)
        result = ts.handle_click((20, 12))
        assert result is True
        assert ts.state is True
        cb.assert_called_once_with(True)

    def test_handle_click_miss(self):
        cb = Mock()
        ts = ToggleSwitch(0, 0, 40, 24, False, cb)
        result = ts.handle_click((200, 200))
        assert result is False
        assert ts.state is False
        cb.assert_not_called()

    def test_draw_on(self):
        ts = ToggleSwitch(0, 0, 40, 24, True, Mock())
        surf = _make_surface()
        ts.draw(surf, _make_palette())

    def test_draw_off(self):
        ts = ToggleSwitch(0, 0, 40, 24, False, Mock())
        surf = _make_surface()
        ts.draw(surf, _make_palette())


class TestButton:
    def test_init(self):
        cb = Mock()
        btn = Button(10, 20, 100, 40, "Click", cb)
        assert btn.rect == pygame.Rect(10, 20, 100, 40)
        assert btn.label == "Click"
        assert btn.hovered is False

    def test_update_hover_inside(self):
        btn = Button(0, 0, 100, 40, "B", Mock())
        btn.update((50, 20))
        assert btn.hovered is True

    def test_update_hover_outside(self):
        btn = Button(0, 0, 100, 40, "B", Mock())
        btn.update((200, 200))
        assert btn.hovered is False

    def test_handle_click_hit(self):
        cb = Mock()
        btn = Button(0, 0, 100, 40, "B", cb)
        result = btn.handle_click((50, 20))
        assert result is True
        cb.assert_called_once()

    def test_handle_click_miss(self):
        cb = Mock()
        btn = Button(0, 0, 100, 40, "B", cb)
        result = btn.handle_click((200, 200))
        assert result is False
        cb.assert_not_called()

    def test_draw_hovered(self):
        btn = Button(0, 0, 100, 40, "B", Mock())
        btn.hovered = True
        surf = _make_surface()
        font = _make_font()
        btn.draw(surf, font, _make_palette())

    def test_draw_default(self):
        btn = Button(0, 0, 100, 40, "B", Mock())
        surf = _make_surface()
        font = _make_font()
        btn.draw(surf, font, _make_palette())


class TestCycleButton:
    def test_init_valid_initial(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B", "C"], "B", Mock())
        assert cb.value == "B"
        assert cb.index == 1

    def test_init_invalid_initial(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B", "C"], "Z", Mock())
        assert cb.value == "A"
        assert cb.index == 0

    def test_handle_click_cycles(self):
        callback = Mock()
        cb = CycleButton(0, 0, 110, 24, ["A", "B", "C"], "A", callback)
        assert cb.value == "A"

        cb.handle_click((55, 12))
        assert cb.value == "B"
        callback.assert_called_with("B")

        cb.handle_click((55, 12))
        assert cb.value == "C"

        cb.handle_click((55, 12))
        assert cb.value == "A"  # wraps around

    def test_handle_click_miss(self):
        callback = Mock()
        cb = CycleButton(0, 0, 110, 24, ["A", "B"], "A", callback)
        result = cb.handle_click((300, 300))
        assert result is False
        callback.assert_not_called()

    def test_value_setter_valid(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B", "C"], "A", Mock())
        cb.value = "C"
        assert cb.index == 2
        assert cb.value == "C"

    def test_value_setter_invalid(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B", "C"], "A", Mock())
        cb.value = "Z"
        assert cb.index == 0  # unchanged

    def test_update_hover(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B"], "A", Mock())
        cb.update((55, 12))
        assert cb.hovered is True
        cb.update((300, 300))
        assert cb.hovered is False

    def test_draw_default(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B"], "A", Mock())
        surf = _make_surface()
        font = _make_font()
        cb.draw(surf, font, _make_palette())

    def test_draw_hovered(self):
        cb = CycleButton(0, 0, 110, 24, ["A", "B"], "A", Mock())
        cb.hovered = True
        surf = _make_surface()
        font = _make_font()
        cb.draw(surf, font, _make_palette())


class TestSettingsOverlay:
    def _make_overlay(self) -> SettingsOverlay:
        gui = _make_gui_integration()
        return SettingsOverlay(800, 600, gui)

    def test_init(self):
        overlay = self._make_overlay()
        assert overlay.active is False
        assert overlay.alpha == 0.0
        assert overlay.active_tab == "display"
        assert overlay.panel_rect.width == 420
        assert overlay.panel_rect.height == 520

    def test_toggle_opens_and_closes(self):
        overlay = self._make_overlay()
        assert overlay.active is False
        overlay.toggle()
        assert overlay.active is True
        overlay.toggle()
        assert overlay.active is False

    def test_update_alpha_increases_when_active(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.alpha = 10.0  # above 1.0 threshold for controls
        with patch("pygame.mouse.get_pos", return_value=(0, 0)):
            overlay.update(0.016)
        assert overlay.alpha > 10.0

    def test_update_alpha_decreases_when_inactive(self):
        overlay = self._make_overlay()
        overlay.alpha = 200.0
        overlay.active = False
        with patch("pygame.mouse.get_pos", return_value=(0, 0)):
            overlay.update(0.016)
        assert overlay.alpha < 200.0

    def test_handle_event_esc_closes(self):
        overlay = self._make_overlay()
        overlay.active = True
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        consumed = overlay.handle_event(event)
        assert consumed is True
        assert overlay.active is False

    def test_handle_event_click_outside_closes(self):
        overlay = self._make_overlay()
        overlay.active = True
        # Click far outside the panel
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(1, 1))
        consumed = overlay.handle_event(event)
        assert consumed is True
        assert overlay.active is False

    def test_handle_event_click_inside_consumed(self):
        overlay = self._make_overlay()
        overlay.active = True
        # Click inside the panel rect (center)
        cx = overlay.panel_rect.centerx
        cy = overlay.panel_rect.centery
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))
        consumed = overlay.handle_event(event)
        assert consumed is True
        # Still active — clicking inside shouldn't close
        assert overlay.active is True

    def test_handle_event_inactive_returns_false(self):
        overlay = self._make_overlay()
        overlay.active = False
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        assert overlay.handle_event(event) is False

    def test_keymap_has_12_entries(self):
        overlay = self._make_overlay()
        assert hasattr(overlay, "_keymap")
        assert len(overlay._keymap) == 12

    def test_active_tab_switching(self):
        overlay = self._make_overlay()
        overlay.active = True
        assert overlay.active_tab == "display"

        # Simulate clicking on the "audio" tab by calling the tab callback directly
        overlay.tabs["audio"].callback("audio")
        assert overlay.active_tab == "audio"
        assert overlay.tabs["audio"].active is True
        assert overlay.tabs["display"].active is False

    def test_draw_when_alpha_low(self):
        overlay = self._make_overlay()
        overlay.alpha = 0.5  # below threshold
        surf = _make_surface(800, 600)
        overlay.draw(surf)  # should return early, no crash

    def test_draw_when_alpha_high(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.alpha = 200.0
        surf = _make_surface(800, 600)
        overlay.draw(surf)  # should render without error

    def test_draw_display_tab(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.active_tab = "display"
        overlay.alpha = 200.0
        surf = _make_surface(800, 600)
        overlay.draw(surf)

    def test_draw_audio_tab(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.active_tab = "audio"
        overlay.alpha = 200.0
        surf = _make_surface(800, 600)
        overlay.draw(surf)

    def test_draw_controls_tab(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.active_tab = "controls"
        overlay.alpha = 200.0
        surf = _make_surface(800, 600)
        overlay.draw(surf)

    def test_handle_event_mousemotion(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.active_tab = "audio"
        # Simulate dragging a slider
        for s in overlay.sliders["audio"].values():
            s["slider"].dragging = True
            break
        event = pygame.event.Event(
            pygame.MOUSEMOTION,
            pos=(overlay.panel_rect.centerx, overlay.panel_rect.centery),
        )
        result = overlay.handle_event(event)
        assert result is True

    def test_handle_event_mouseup(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.active_tab = "audio"
        for s in overlay.sliders["audio"].values():
            s["slider"].dragging = True
            break
        event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1)
        overlay.handle_event(event)
        # All sliders should have dragging=False
        for s in overlay.sliders["audio"].values():
            assert s["slider"].dragging is False

    def test_quit_button_callback(self):
        overlay = self._make_overlay()
        quit_cb = Mock()
        overlay.set_quit_callback(quit_cb)
        overlay._on_quit_clicked()
        quit_cb.assert_called_once()

    def test_quit_button_no_callback(self):
        overlay = self._make_overlay()
        overlay.on_quit_callback = None
        overlay._on_quit_clicked()  # should not raise

    def test_reset_button(self):
        gui = _make_gui_integration()
        gui.settings.reset_to_defaults = Mock()
        overlay = SettingsOverlay(800, 600, gui)
        overlay._on_reset_clicked()
        gui.settings.reset_to_defaults.assert_called_once()

    def test_update_layout(self):
        overlay = self._make_overlay()
        old_tab = "gameplay"
        overlay.active_tab = old_tab
        for t in overlay.tabs.values():
            t.active = t.tab_id == old_tab
        overlay.update_layout(1024, 768)
        assert overlay.screen_w == 1024
        assert overlay.screen_h == 768
        assert overlay.active_tab == old_tab

    def test_set_display_mode_callback(self):
        overlay = self._make_overlay()
        cb = Mock()
        overlay.set_display_mode_callback(cb)
        assert overlay.on_display_mode_toggle is cb

    def test_toggle_resyncs_settings(self):
        gui = _make_gui_integration()
        gui.settings.get = Mock(
            side_effect=lambda key, default=None: True if key == "high_contrast" else default
        )
        overlay = SettingsOverlay(800, 600, gui)
        overlay.toggle()  # open
        # Toggle switches should be re-synced
        assert overlay.active is True

    def test_handle_event_tab_click(self):
        overlay = self._make_overlay()
        overlay.active = True
        # Find the gameplay tab rect and click on it
        gameplay_tab = overlay.tabs["gameplay"]
        cx = gameplay_tab.rect.centerx
        cy = gameplay_tab.rect.centery
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))
        consumed = overlay.handle_event(event)
        assert consumed is True
        assert overlay.active_tab == "gameplay"

    def test_handle_event_display_cycle_button(self):
        overlay = self._make_overlay()
        overlay.active = True
        overlay.active_tab = "display"
        cx = overlay.display_mode_btn.rect.centerx
        cy = overlay.display_mode_btn.rect.centery
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))
        consumed = overlay.handle_event(event)
        assert consumed is True


# ===================================================================
# 2. input_bar.py
# ===================================================================
from hosts.gui.input_bar import InputBar


class TestInputBar:
    def test_init_defaults(self):
        ib = InputBar()
        assert ib.text == ""
        assert ib._cursor_on is True
        assert ib.processing is False
        assert ib.waiting_for_agent is None

    def test_update_cursor_blink(self):
        ib = InputBar()
        assert ib._cursor_on is True
        # Accumulate enough time to trigger blink
        ib.update(0.6)
        assert ib._cursor_on is False
        ib.update(0.6)
        assert ib._cursor_on is True

    def test_handle_key_return_submits(self):
        ib = InputBar()
        ib.text = "hello world"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r")
        result = ib.handle_key(event)
        assert result == "hello world"
        assert ib.text == ""

    def test_handle_key_return_empty(self):
        ib = InputBar()
        ib.text = ""
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r")
        result = ib.handle_key(event)
        assert result is None

    def test_handle_key_return_while_processing(self):
        ib = InputBar()
        ib.text = "some text"
        ib.processing = True
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r")
        result = ib.handle_key(event)
        assert result is None  # blocked by processing

    def test_handle_key_backspace(self):
        ib = InputBar()
        ib.text = "abc"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0, unicode="\b")
        ib.handle_key(event)
        assert ib.text == "ab"

    def test_handle_key_ctrl_backspace(self):
        ib = InputBar()
        ib.text = "hello world"
        event = pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=pygame.KMOD_CTRL, unicode="\b"
        )
        ib.handle_key(event)
        assert ib.text == "hello "

    def test_handle_key_ctrl_backspace_single_word(self):
        ib = InputBar()
        ib.text = "hello"
        event = pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=pygame.KMOD_CTRL, unicode="\b"
        )
        ib.handle_key(event)
        assert ib.text == ""

    def test_handle_textinput(self):
        ib = InputBar()
        ib.text = "ab"
        event = pygame.event.Event(pygame.TEXTINPUT, text="c")
        ib.handle_textinput(event)
        assert ib.text == "abc"

    def test_draw_no_crash(self):
        ib = InputBar()
        surf = _make_surface(800, 600)
        ib.draw(surf)

    def test_draw_with_text(self):
        ib = InputBar()
        ib.text = "Hello"
        surf = _make_surface(800, 600)
        ib.draw(surf)

    def test_draw_while_processing(self):
        ib = InputBar()
        ib.processing = True
        surf = _make_surface(800, 600)
        ib.draw(surf)

    def test_draw_waiting_for_agent(self):
        ib = InputBar()
        ib.waiting_for_agent = "hephaestus"
        surf = _make_surface(800, 600)
        ib.draw(surf)

    def test_draw_waiting_for_agent_with_empty_text(self):
        ib = InputBar()
        ib.waiting_for_agent = "metis"
        ib.text = ""
        surf = _make_surface(800, 600)
        ib.draw(surf)


# ===================================================================
# 3. scratchpad.py
# ===================================================================
from hosts.gui.scratchpad import Scratchpad


class TestScratchpad:
    def test_init(self):
        sp = Scratchpad()
        assert sp.is_open is False
        assert sp._active_agent == "hephaestus"
        assert sp._scroll_y == 0

    def test_toggle(self):
        sp = Scratchpad()
        assert sp.is_open is False
        sp.toggle()
        assert sp.is_open is True
        sp.toggle()
        assert sp.is_open is False

    def test_set_agent_changes(self):
        sp = Scratchpad()
        sp._scroll_y = 100
        sp.set_agent("metis")
        assert sp._active_agent == "metis"
        assert sp._scroll_y == 0  # reset on agent change

    def test_set_agent_same_noop(self):
        sp = Scratchpad()
        sp._scroll_y = 50
        sp.set_agent("hephaestus")  # same agent
        assert sp._scroll_y == 50  # not reset

    def test_append(self):
        sp = Scratchpad()
        sp.append("metis", "Plan step 1")
        assert "metis" in sp._content_by_agent
        assert sp._content_by_agent["metis"] == ["Plan step 1"]

    def test_append_multiple(self):
        sp = Scratchpad()
        sp.append("metis", "A")
        sp.append("metis", "B")
        assert sp._content_by_agent["metis"] == ["A", "B"]

    def test_append_auto_scrolls_current_agent(self):
        sp = Scratchpad()
        sp._active_agent = "metis"
        sp.rect = pygame.Rect(0, 0, 300, 400)  # non-zero height
        sp._rendered_h = 500
        sp.append("metis", "New content")
        # scroll_to_bottom should have been called
        assert sp._scroll_y >= 0

    def test_clear(self):
        sp = Scratchpad()
        sp.append("metis", "stuff")
        sp._scroll_y = 50
        sp.clear("metis")
        assert sp._content_by_agent["metis"] == []
        assert sp._scroll_y == 0

    def test_clear_nonexistent_agent(self):
        sp = Scratchpad()
        sp.clear("nonexistent")  # should not raise

    def test_scroll(self):
        sp = Scratchpad()
        sp.rect = pygame.Rect(0, 0, 300, 200)
        sp._rendered_h = 500
        sp.scroll(100)
        assert sp._scroll_y > 0

    def test_scroll_clamps_negative(self):
        sp = Scratchpad()
        sp.rect = pygame.Rect(0, 0, 300, 200)
        sp._rendered_h = 500
        sp._scroll_y = 10
        sp.scroll(-100)
        assert sp._scroll_y == 0

    def test_scroll_to_bottom(self):
        sp = Scratchpad()
        sp.rect = pygame.Rect(0, 0, 300, 200)
        sp._rendered_h = 500
        sp.scroll_to_bottom()
        expected = max(0, 500 - (200 - sp.PAD * 2 - 40))
        assert sp._scroll_y == expected

    def test_handle_event_when_closed(self):
        sp = Scratchpad()
        sp.is_open = False
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 50))
        assert sp.handle_event(event) is False

    def test_handle_event_mousewheel_inside(self):
        sp = Scratchpad()
        sp.is_open = True
        sp.rect = pygame.Rect(0, 0, 300, 400)
        sp._rendered_h = 800
        with patch("pygame.mouse.get_pos", return_value=(150, 200)):
            event = pygame.event.Event(pygame.MOUSEWHEEL, y=-1)
            result = sp.handle_event(event)
        assert result is True

    def test_handle_event_click_inside_consumed(self):
        sp = Scratchpad()
        sp.is_open = True
        sp.rect = pygame.Rect(0, 0, 300, 400)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(150, 200))
        result = sp.handle_event(event)
        assert result is True

    def test_handle_event_click_outside_not_consumed(self):
        sp = Scratchpad()
        sp.is_open = True
        sp.rect = pygame.Rect(0, 0, 300, 400)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(500, 500))
        result = sp.handle_event(event)
        assert result is False

    def test_draw_when_closed(self):
        sp = Scratchpad()
        sp.is_open = False
        surf = _make_surface(800, 600)
        rect = pygame.Rect(0, 0, 300, 400)
        sp.draw(surf, rect)  # returns early, no crash

    def test_draw_with_no_content(self):
        sp = Scratchpad()
        sp.is_open = True
        surf = _make_surface(800, 600)
        rect = pygame.Rect(0, 0, 300, 400)
        sp.draw(surf, rect)

    def test_draw_with_content(self):
        sp = Scratchpad()
        sp.is_open = True
        sp.append("hephaestus", "- Step 1: Build the forge")
        sp.append("hephaestus", "- Step 2: Test the metal\n[x] TODO item")
        surf = _make_surface(800, 600)
        rect = pygame.Rect(0, 0, 300, 400)
        sp.draw(surf, rect)

    def test_draw_with_scrollbar(self):
        sp = Scratchpad()
        sp.is_open = True
        # Add enough content to exceed clip height
        for i in range(50):
            sp.append("hephaestus", f"Line {i}: lots of detail here to fill space")
        surf = _make_surface(800, 600)
        rect = pygame.Rect(0, 0, 300, 200)
        sp.draw(surf, rect)


# ===================================================================
# 4. quick_actions.py
# ===================================================================
from hosts.gui.quick_actions import QuickAction, QuickActionBar


class TestQuickAction:
    def test_init(self):
        qa = QuickAction(
            label="Commit",
            agent="mneme",
            display_text="Do commit",
            hidden_prompt="[run commits]",
        )
        assert qa.label == "Commit"
        assert qa.agent == "mneme"
        assert qa.display_text == "Do commit"
        assert qa.hidden_prompt == "[run commits]"
        assert qa.hovered is False
        assert qa.rect == pygame.Rect(0, 0, 0, 0)


class TestQuickActionBar:
    def test_init_has_three_actions(self):
        bar = QuickActionBar()
        assert len(bar.actions) == 3
        labels = [a.label for a in bar.actions]
        assert "Commit" in labels
        assert "Lint" in labels
        assert "Test" in labels

    def test_update_hover(self):
        bar = QuickActionBar()
        # First draw to set rects
        surf = _make_surface(800, 600)
        bar.draw(surf)
        # Now update hover with a point inside the first action's rect
        first_action = bar.actions[0]
        cx = first_action.rect.centerx
        cy = first_action.rect.centery
        bar.update((cx, cy))
        assert first_action.hovered is True

    def test_update_hover_miss(self):
        bar = QuickActionBar()
        surf = _make_surface(800, 600)
        bar.draw(surf)
        bar.update((0, 0))
        for action in bar.actions:
            assert action.hovered is False

    def test_handle_click_hit(self):
        bar = QuickActionBar()
        surf = _make_surface(800, 600)
        bar.draw(surf)  # populate rects
        first = bar.actions[0]
        cx = first.rect.centerx
        cy = first.rect.centery
        result = bar.handle_click((cx, cy))
        assert result is first

    def test_handle_click_miss(self):
        bar = QuickActionBar()
        surf = _make_surface(800, 600)
        bar.draw(surf)
        result = bar.handle_click((0, 0))
        assert result is None

    def test_draw_no_crash(self):
        bar = QuickActionBar()
        surf = _make_surface(800, 600)
        bar.draw(surf)

    def test_draw_disabled(self):
        bar = QuickActionBar()
        surf = _make_surface(800, 600)
        bar.draw(surf, disabled=True)

    def test_draw_hovered(self):
        bar = QuickActionBar()
        surf = _make_surface(800, 600)
        bar.draw(surf)
        # Set one as hovered
        bar.actions[1].hovered = True
        bar.draw(surf)


# ===================================================================
# 5. particles.py
# ===================================================================
from hosts.gui.particles import Ember, ParticleSystem


class TestEmber:
    def test_init(self):
        ember = Ember()
        # After __init__ + _reset, ember should have positive alpha
        assert ember.alpha > 0

    def test_update_alive(self):
        ember = Ember()
        ember.alpha = 100.0
        ember.decay = 0.1
        result = ember.update(0.016)
        assert result is True

    def test_update_dead(self):
        ember = Ember()
        ember.alpha = 1.0
        ember.decay = 100.0  # high decay -> dies quickly
        result = ember.update(1.0)
        assert result is False

    def test_draw_alive(self):
        ember = Ember()
        ember.alpha = 100.0
        ember.radius = 2.0
        surf = _make_surface(100, 100)
        ember.draw(surf)  # should not raise

    def test_draw_dead(self):
        ember = Ember()
        ember.alpha = 0.0
        surf = _make_surface(100, 100)
        ember.draw(surf)  # returns early, no crash

    def test_draw_negative_alpha(self):
        ember = Ember()
        ember.alpha = -5.0
        surf = _make_surface(100, 100)
        ember.draw(surf)  # returns early

    def test_reset(self):
        ember = Ember()
        ember.alpha = 0.0
        ember._reset(800, 600)
        assert ember.alpha > 0
        assert 0 <= ember.x <= 800
        assert 0 <= ember.y <= 600

    def test_update_changes_position(self):
        ember = Ember()
        ember.x = 100.0
        ember.y = 100.0
        ember.vx = 0.1
        ember.vy = -0.3
        ember.alpha = 180.0
        ember.decay = 0.2
        old_x, old_y = ember.x, ember.y
        ember.update(0.5)
        # Position should change since vx and vy are non-zero
        assert ember.x != old_x or ember.y != old_y


class TestParticleSystem:
    def test_init_120_embers(self):
        ps = ParticleSystem()
        assert len(ps._embers) == 120

    def test_update(self):
        ps = ParticleSystem()
        # Should not raise
        ps.update(0.016, 800, 600)

    def test_update_resets_dead_embers(self):
        ps = ParticleSystem()
        # Kill all embers
        for e in ps._embers:
            e.alpha = 0.0
            e.decay = 1000.0
        ps.update(1.0, 800, 600)
        # After update, dead embers should have been reset
        for e in ps._embers:
            assert e.alpha > 0

    def test_draw(self):
        ps = ParticleSystem()
        surf = _make_surface(200, 200)
        ps.draw(surf)  # should not raise
