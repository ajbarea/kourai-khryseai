"""
Covers remaining gaps in: auto_scroll, dialogue_history_integration,
performance_profiler, alignment_theme, connection_manager, settings,
typewriter, keyboard_shortcuts, message_history, constants, font_scaler,
connection_gui_integration, client, __main__ helpers, profile_select draw
helpers, loading_screen helpers, input_bar shortcuts.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("pygame")

import pygame
import pygame.freetype

pygame.init()
pygame.freetype.init()


# ===================================================================
# 1. auto_scroll.py
# ===================================================================


class TestAutoScrollManager:
    def test_init_defaults(self):
        from hosts.gui.auto_scroll import AutoScrollManager

        asm = AutoScrollManager()
        assert asm.enabled is True
        assert asm.should_scroll() is True

    def test_toggle(self):
        from hosts.gui.auto_scroll import AutoScrollManager

        asm = AutoScrollManager()
        asm.toggle()
        assert asm.enabled is False
        assert asm.should_scroll() is False
        asm.toggle()
        assert asm.enabled is True

    def test_update_distance_at_bottom(self):
        from hosts.gui.auto_scroll import AutoScrollManager

        asm = AutoScrollManager()
        asm.update_distance(current_scroll=500, content_height=1000, view_height=500)
        assert asm.get_distance_text() == "At bottom"

    def test_update_distance_above(self):
        from hosts.gui.auto_scroll import AutoScrollManager

        asm = AutoScrollManager()
        asm.update_distance(current_scroll=0, content_height=1000, view_height=500)
        text = asm.get_distance_text()
        assert "above" in text

    def test_update_distance_no_scroll_needed(self):
        from hosts.gui.auto_scroll import AutoScrollManager

        asm = AutoScrollManager()
        asm.update_distance(current_scroll=0, content_height=100, view_height=500)
        assert asm.get_distance_text() == "At bottom"


# ===================================================================
# 2. dialogue_history_integration.py
# ===================================================================


class TestDialogueHistoryWithAutoScroll:
    def test_init(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        assert dh._entries == []
        assert dh._scroll_y == 0
        assert dh.is_auto_scroll_enabled() is True

    def test_add_entry(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        entry = Mock(is_user=True, text="Hello", timestamp=0, metadata=None)
        dh.add(entry)
        assert len(dh._entries) == 1

    def test_update_last_text(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        entry = Mock(is_user=False, text="Hi", timestamp=0, metadata=None)
        dh.add(entry)
        dh.update_last_text("Hello world")
        assert dh._entries[0].text == "Hello world"

    def test_scroll(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        dh._content_h = 2000
        dh.scroll(100)
        assert dh._scroll_y == 100

    def test_scroll_to_bottom(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        dh._content_h = 2000
        dh.scroll_to_bottom()
        assert dh._scroll_y > 0

    def test_toggle_auto_scroll(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        assert dh.is_auto_scroll_enabled() is True
        dh.toggle_auto_scroll()
        assert dh.is_auto_scroll_enabled() is False

    def test_get_distance_text(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        text = dh.get_distance_text()
        assert isinstance(text, str)

    def test_wrap_text(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        lines = dh._wrap_text("Hello world this is a test", 100)
        assert len(lines) >= 1

    def test_entry_height_user(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        entry = Mock(is_user=True, text="Hello")
        h = dh._entry_height(entry)
        assert h > 0

    def test_entry_height_agent(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        entry = Mock(is_user=False, text="Hello")
        h = dh._entry_height(entry)
        assert h > 0

    def test_render(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        entry = Mock(is_user=True, text="Test message")
        dh.add(entry)
        dh._render()
        assert dh._surf is not None
        assert dh._dirty is False

    def test_draw(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        entry = Mock(is_user=True, text="Test")
        dh.add(entry)
        surf = pygame.Surface((960, 640), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, 960, 640)
        dh.draw(surf, rect)

    def test_draw_with_scrollbar(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        for i in range(50):
            entry = Mock(is_user=(i % 2 == 0), text=f"Message {i} with some text")
            dh.add(entry)
        surf = pygame.Surface((960, 640), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, 960, 640)
        dh.draw(surf, rect)

    def test_draw_distance_indicator(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        for i in range(50):
            dh.add(Mock(is_user=True, text=f"Msg {i}"))
        dh.toggle_auto_scroll()
        surf = pygame.Surface((960, 640), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, 960, 640)
        dh.draw(surf, rect, show_distance=True)

    def test_draw_empty(self):
        from hosts.gui.dialogue_history_integration import (
            DialogueHistoryWithAutoScroll,
        )

        dh = DialogueHistoryWithAutoScroll()
        dh._dirty = False
        dh._surf = None
        surf = pygame.Surface((960, 640), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, 960, 640)
        dh.draw(surf, rect)


# ===================================================================
# 3. alignment_theme.py
# ===================================================================


class TestAlignmentTheme:
    def test_lerp_color(self):
        from hosts.gui.alignment_theme import _lerp_color

        result = _lerp_color((0, 0, 0), (255, 255, 255), 0.5)
        assert result == (127, 127, 127)

    def test_lerp_color_clamp(self):
        from hosts.gui.alignment_theme import _lerp_color

        result = _lerp_color((0, 0, 0), (255, 255, 255), 1.5)
        assert result == (255, 255, 255)
        result = _lerp_color((0, 0, 0), (255, 255, 255), -0.5)
        assert result == (0, 0, 0)

    def test_neutral_palette(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(0, 0)
        assert "background" in palette
        assert "gold" in palette
        assert "text" in palette

    def test_sovereignty_palette(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(80, 0)
        assert "background" in palette

    def test_devotion_palette(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(0, 80)
        assert "background" in palette

    def test_commander_palette(self):
        from hosts.gui.alignment_theme import compute_alignment_palette

        palette = compute_alignment_palette(80, 80)
        assert "background" in palette

    def test_all_keys_present(self):
        from hosts.gui.alignment_theme import _NEUTRAL, compute_alignment_palette

        palette = compute_alignment_palette(50, 50)
        for key in _NEUTRAL:
            assert key in palette
            assert len(palette[key]) == 3


# ===================================================================
# 5. connection_manager.py — cover all branches
# ===================================================================


class TestConnectionManager:
    def test_init_defaults(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        assert cm.connected is False
        assert cm.reconnecting is False
        assert cm.error_message == ""
        assert cm.is_connected() is False
        assert cm.is_reconnecting() is False
        assert cm.has_error() is False

    def test_handle_connected(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.handle_connected("Hephaestus")
        assert cm.connected is True
        assert cm._agent_name == "Hephaestus"
        assert cm.is_connected() is True

    def test_handle_disconnected(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.handle_connected("X")
        cm.handle_disconnected()
        assert cm.connected is False
        assert cm._agent_name == ""

    def test_attempt_reconnect_with_callback(self):
        from hosts.gui.connection_manager import ConnectionManager

        cb = Mock()
        cm = ConnectionManager(reconnect_callback=cb)
        cm.attempt_reconnect()
        assert cm.reconnecting is True
        cb.assert_called_once()

    def test_attempt_reconnect_already_reconnecting(self):
        from hosts.gui.connection_manager import ConnectionManager

        cb = Mock()
        cm = ConnectionManager(reconnect_callback=cb)
        cm.attempt_reconnect()
        cm.attempt_reconnect()  # Should be a no-op
        cb.assert_called_once()

    def test_set_error(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.attempt_reconnect()
        cm.set_error("Connection refused")
        assert cm.reconnecting is False
        assert cm.error_message == "Connection refused"
        assert cm.has_error() is True

    def test_get_status_text_reconnecting(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.reconnecting = True
        assert cm.get_status_text() == "Reconnecting..."

    def test_get_status_text_connected(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.handle_connected("Metis")
        assert "Metis" in cm.get_status_text()

    def test_get_status_text_error(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.set_error("timeout")
        assert "timeout" in cm.get_status_text()

    def test_get_status_text_disconnected(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        assert cm.get_status_text() == "Disconnected"

    def test_get_status_color_reconnecting(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.reconnecting = True
        assert cm.get_status_color() == (255, 200, 0)

    def test_get_status_color_connected(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.handle_connected("X")
        assert cm.get_status_color() == (0, 200, 0)

    def test_get_status_color_error(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.set_error("fail")
        assert cm.get_status_color() == (200, 0, 0)

    def test_get_status_color_disconnected(self):
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        assert cm.get_status_color() == (128, 128, 128)


# ===================================================================
# 6. settings.py — cover _load, save, get, set, reset
# ===================================================================


class TestSettingsManager:
    def test_init_no_file(self):
        from hosts.gui.settings import SettingsManager

        with tempfile.TemporaryDirectory() as d:
            sm = SettingsManager(Path(d) / "settings.json")
            assert sm.get("typewriter_speed_ms") == 30

    def test_get_default(self):
        from hosts.gui.settings import SettingsManager

        with tempfile.TemporaryDirectory() as d:
            sm = SettingsManager(Path(d) / "s.json")
            assert sm.get("nonexistent", "fallback") == "fallback"

    def test_set_and_get(self):
        from hosts.gui.settings import SettingsManager

        with tempfile.TemporaryDirectory() as d:
            sm = SettingsManager(Path(d) / "s.json")
            sm.set("custom_key", 42)
            assert sm.get("custom_key") == 42

    def test_save_and_load(self):
        from hosts.gui.settings import SettingsManager

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            sm = SettingsManager(path)
            sm.set("font_scale", 1.5)
            sm.save()
            sm2 = SettingsManager(path)
            assert sm2.get("font_scale") == 1.5

    def test_save_error(self):
        from hosts.gui.settings import SettingsManager

        with tempfile.TemporaryDirectory() as d:
            sm = SettingsManager(Path(d) / "s.json")
            with patch("builtins.open", side_effect=OSError("disk full")):
                sm.save()  # Should not raise

    def test_load_corrupted(self):
        from hosts.gui.settings import SettingsManager

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            path.write_text("not valid json!!!")
            sm = SettingsManager(path)
            assert sm.get("typewriter_speed_ms") == 30

    def test_reset_to_defaults(self):
        from hosts.gui.settings import DEFAULT_SETTINGS, SettingsManager

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            sm = SettingsManager(path)
            sm.set("font_scale", 2.0)
            sm.reset_to_defaults()
            assert sm.get("font_scale") == DEFAULT_SETTINGS["font_scale"]


# ===================================================================
# 7. typewriter.py — cover update, skip, pause, resume, etc.
# ===================================================================


class TestTypewriterManager:
    def test_update_not_active(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        result = tw.update(0.1)
        assert result == ""

    def test_update_active(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello")
        result = tw.update(1.0)
        assert len(result) > 0

    def test_update_completes(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hi", speed_ms=10)
        result = tw.update(10.0)  # Long enough to finish
        assert result == "Hi"
        assert tw.is_complete() is True

    def test_update_paused(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello")
        tw.pause()
        assert tw.paused is True
        result = tw.update(1.0)
        assert len(result) == 0  # No progress while paused

    def test_resume(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello")
        tw.pause()
        tw.resume()
        assert tw.paused is False

    def test_resume_not_paused(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello")
        tw.resume()  # Not paused, should be no-op

    def test_skip(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello world")
        tw.skip()
        assert tw.displayed_chars == len("Hello world")
        assert tw.is_complete() is True

    def test_skip_not_active(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.skip()  # No-op

    def test_pause_not_active(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.pause()
        assert tw.paused is False

    def test_set_motion_sensitivity(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.set_motion_sensitivity(True)
        assert tw.motion_sensitivity_enabled is True

    def test_motion_sensitivity_skips_effect(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager(motion_sensitivity_enabled=True)
        tw.start("Hello")
        assert tw.displayed_chars == 5
        assert tw.active is False

    def test_set_speed(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.set_speed(50)
        assert tw.current_speed_ms == 50

    def test_set_speed_clamps(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.set_speed(5)
        assert tw.current_speed_ms == tw.min_speed_ms
        tw.set_speed(500)
        assert tw.current_speed_ms == tw.max_speed_ms

    def test_get_displayed_text(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello")
        tw.update(0.05)
        text = tw.get_displayed_text()
        assert isinstance(text, str)

    def test_reset(self):
        from hosts.gui.typewriter import TypewriterManager

        tw = TypewriterManager()
        tw.start("Hello")
        tw.reset()
        assert tw.active is False
        assert tw.current_text == ""
        assert tw.displayed_chars == 0


# ===================================================================
# 8. keyboard_shortcuts.py
# ===================================================================


class TestKeyboardShortcuts:
    def _make_event(self, key, mod=0):
        e = Mock()
        e.key = key
        e.mod = mod
        return e

    def test_init(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        assert ks.has_focus() is False

    def test_ctrl_k_focus(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        result = ks.handle_key(self._make_event(pygame.K_k, pygame.KMOD_CTRL), "")
        assert result == {"action": "focus"}
        assert ks.has_focus() is True

    def test_ctrl_l_clear(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        result = ks.handle_key(self._make_event(pygame.K_l, pygame.KMOD_CTRL), "hello")
        assert result == {"action": "clear"}

    def test_up_arrow_empty(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        result = ks.handle_key(self._make_event(pygame.K_UP, 0), "")
        assert result is None

    def test_up_arrow_with_history(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        ks.add_message("hello")
        result = ks.handle_key(self._make_event(pygame.K_UP, 0), "")
        assert result is not None
        assert result["action"] == "navigate"
        assert result["text"] == "hello"

    def test_down_arrow_with_history(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        ks.add_message("hello")
        result = ks.handle_key(self._make_event(pygame.K_DOWN, 0), "")
        assert result is not None
        assert result["action"] == "navigate"

    def test_down_arrow_empty(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        result = ks.handle_key(self._make_event(pygame.K_DOWN, 0), "")
        assert result is None

    def test_no_shortcut(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        result = ks.handle_key(self._make_event(pygame.K_a, 0), "")
        assert result is None

    def test_focus_blur(self):
        from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

        ks = KeyboardShortcuts()
        ks.focus()
        assert ks.has_focus() is True
        ks.blur()
        assert ks.has_focus() is False


# ===================================================================
# 9. message_history.py
# ===================================================================


class TestMessageHistory:
    def test_init(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        assert len(mh) == 0

    def test_add(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("hello")
        assert len(mh) == 1

    def test_add_whitespace_only(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("   ")
        assert len(mh) == 0

    def test_navigate_empty(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        assert mh.navigate(-1) is None

    def test_navigate_up(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("first")
        mh.add("second")
        result = mh.navigate(-1)
        assert result == "second"

    def test_navigate_down_from_start(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("first")
        result = mh.navigate(1)
        assert result == "first"

    def test_navigate_wraparound_up(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("first")
        mh.add("second")
        mh.navigate(-1)  # index = 1 (second)
        mh.navigate(-1)  # index = 0 (first)
        result = mh.navigate(-1)  # wrap to index = 1 (second)
        assert result == "second"

    def test_navigate_wraparound_down(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("first")
        mh.add("second")
        mh.navigate(-1)  # index = 1 (second)
        mh.navigate(1)  # wrap to 0 if needed
        # Just ensure no crash

    def test_reset(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("hello")
        mh.navigate(-1)
        mh.reset()
        assert mh.get_current() is None

    def test_get_current_at_start(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        assert mh.get_current() is None

    def test_get_current_after_navigate(self):
        from hosts.gui.message_history import MessageHistory

        mh = MessageHistory()
        mh.add("hello")
        mh.navigate(-1)
        assert mh.get_current() == "hello"


# ===================================================================
# 10. constants.py — Theme.apply_palette and _create_font
# ===================================================================


class TestTheme:
    def test_apply_palette(self):
        from hosts.gui.constants import Theme

        t = Theme()
        palette = {
            "background": (20, 20, 20),
            "bubble_bg": (30, 30, 30),
            "gold": (200, 200, 50),
            "gold_dim": (100, 100, 25),
            "text": (250, 250, 250),
            "scrollbar": (80, 80, 80),
            "error_red": (255, 0, 0),
        }
        t.apply_palette(palette)
        assert t.dark_bg == (20, 20, 20)
        assert t.gold == (200, 200, 50)
        assert t.error_red == (255, 0, 0)

    def test_apply_palette_same_no_update(self):
        from hosts.gui.constants import Theme

        t = Theme()
        palette = {
            "background": (20, 20, 20),
            "bubble_bg": (30, 30, 30),
            "gold": (200, 200, 50),
            "gold_dim": (100, 100, 25),
            "text": (250, 250, 250),
            "scrollbar": (80, 80, 80),
            "error_red": (255, 0, 0),
        }
        t.apply_palette(palette)
        old_bg = t.dark_bg
        t.apply_palette(palette)  # Same palette, should skip
        assert t.dark_bg == old_bg

    def test_load_font_fallback(self):
        from hosts.gui.constants import _create_font

        font = _create_font(["nonexistent_font_xyz"], 16)
        assert font is not None


# ===================================================================
# 11. font_scaler.py
# ===================================================================


class TestFontScaler:
    def test_init(self):
        from hosts.gui.font_scaler import FontScaler

        fs = FontScaler()
        assert fs.scale == 1.0

    def test_set_scale(self):
        from hosts.gui.font_scaler import FontScaler

        fs = FontScaler()
        fs.set_scale(1.5)
        assert fs.scale == 1.5

    def test_set_scale_clamps(self):
        from hosts.gui.font_scaler import FontScaler

        fs = FontScaler()
        fs.set_scale(0.5)
        assert fs.scale == 0.8
        fs.set_scale(3.0)
        assert fs.scale == 2.0

    def test_scale_font(self):
        from hosts.gui.font_scaler import FontScaler

        fs = FontScaler()
        fs.set_scale(1.5)
        base_font = pygame.freetype.SysFont("arial", 16)
        scaled = fs.scale_font(base_font, 16)
        assert scaled is not None

    def test_adjust_scroll(self):
        from hosts.gui.font_scaler import FontScaler

        fs = FontScaler()
        result = fs.adjust_scroll(100, 1.0, 2.0)
        assert result == 200

    def test_adjust_scroll_zero_old(self):
        from hosts.gui.font_scaler import FontScaler

        fs = FontScaler()
        result = fs.adjust_scroll(100, 0, 2.0)
        assert result == 100


# ===================================================================
# 12. connection_gui_integration.py — deeper coverage
# ===================================================================


class TestConnectionStatusDisplayDeep:
    def test_set_font(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        font = pygame.freetype.SysFont("arial", 14)
        csd.set_font(font)
        assert csd._font is font

    def test_handle_click_hit(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.set_error("fail")  # Disconnected + error
        csd = ConnectionStatusDisplay(cm)
        csd.update_button_rect(10, 20, 100, 30)
        result = csd.handle_click((50, 35))
        assert result is True
        assert cm.reconnecting is True

    def test_draw_with_font(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.handle_connected("Test")
        csd = ConnectionStatusDisplay(cm)
        font = pygame.freetype.SysFont("arial", 14)
        csd.set_font(font)
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        csd.draw(surf, 10, 10)

    def test_draw_with_error_and_button(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.set_error("Connection refused")
        csd = ConnectionStatusDisplay(cm)
        font = pygame.freetype.SysFont("arial", 14)
        csd.set_font(font)
        csd.update_button_rect(10, 30, 80, 24)
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        csd.draw(surf, 10, 10)

    def test_draw_reconnect_button_no_width(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.set_error("fail")
        csd = ConnectionStatusDisplay(cm)
        font = pygame.freetype.SysFont("arial", 14)
        csd.set_font(font)
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        csd.draw(surf, 10, 10)  # No button rect set, should skip

    def test_is_showing_reconnect_button_true(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        cm.set_error("fail")
        csd = ConnectionStatusDisplay(cm)
        assert csd.is_showing_reconnect_button() is True


# ===================================================================
# 13. client.py — static methods and _put
# ===================================================================


class TestGuiClientHelpers:
    def test_put_strips_ansi(self):
        import queue as _queue

        from hosts.gui.client import GuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        gc = GuiClient(send_q, recv_q, "http://localhost:10000")
        gc._put({"type": "status", "text": "\x1b[32mGreen text\x1b[0m"})
        event = recv_q.get_nowait()
        assert "\x1b" not in event["text"]
        assert "Green text" in event["text"]

    def test_put_no_text(self):
        import queue as _queue

        from hosts.gui.client import GuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        gc = GuiClient(send_q, recv_q)
        gc._put({"type": "connected", "name": "Test"})
        event = recv_q.get_nowait()
        assert event["type"] == "connected"

    def test_resolve_target_url_uses_default_host(self):
        import queue as _queue

        from hosts.gui.client import GuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        gc = GuiClient(send_q, recv_q, "http://localhost:10000/")

        assert gc._resolve_target_url("kallos") == "http://localhost:10004/"

    def test_resolve_target_url_maps_all_agents_to_default_host(self):
        import queue as _queue

        from hosts.gui.client import GuiClient
        from kourai_common.config import AGENT_PORTS

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        gc = GuiClient(send_q, recv_q, "http://localhost:10000/")

        for agent_name, port in AGENT_PORTS.items():
            assert gc._resolve_target_url(agent_name) == f"http://localhost:{port}/"

    def test_resolve_target_url_unknown_agent_falls_back_default(self):
        import queue as _queue

        from hosts.gui.client import GuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        gc = GuiClient(send_q, recv_q, "http://localhost:10000/")

        assert gc._resolve_target_url("not-a-real-agent") == "http://localhost:10000/"

    def test_resolve_target_url_falls_back_to_config_resolver(self):
        import queue as _queue

        from hosts.gui.client import GuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        gc = GuiClient(send_q, recv_q, "not-a-url")

        with patch("hosts.gui.client.get_host_agent_url", return_value="http://localhost:10004/"):
            assert gc._resolve_target_url("kallos") == "http://localhost:10004/"

    def test_extract_status_empty(self):
        from hosts.gui.client import GuiClient

        event = Mock()
        event.status = Mock()
        event.status.message = None
        assert GuiClient._extract_status(event) == ""

    def test_extract_status_with_parts(self):
        from hosts.gui.client import GuiClient

        part = Mock()
        part.HasField = lambda f: f == "text"
        part.text = "Processing..."
        event = Mock()
        event.status = Mock()
        event.status.message = Mock()
        event.status.message.parts = [part]
        result = GuiClient._extract_status(event)
        assert result == "Processing..."

    def test_extract_artifact_empty(self):
        from hosts.gui.client import GuiClient

        event = Mock()
        event.artifact = None
        assert GuiClient._extract_artifact(event) == ""

    def test_extract_artifact_with_parts(self):
        from hosts.gui.client import GuiClient

        part = Mock()
        part.HasField = lambda f: f == "text"
        part.text = "Result text"
        event = Mock()
        event.artifact = Mock()
        event.artifact.parts = [part]
        result = GuiClient._extract_artifact(event)
        assert result == "Result text"

    def test_extract_artifact_no_parts(self):
        from hosts.gui.client import GuiClient

        event = Mock()
        event.artifact = Mock()
        event.artifact.parts = []
        assert GuiClient._extract_artifact(event) == ""


# ===================================================================
# 14. __main__.py — helper functions
# ===================================================================


class TestMainHelpers:
    def test_is_system_status_true(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("Analyzing code structure") is True
        assert _is_system_status("Processing request") is True
        assert _is_system_status("Running tests") is True
        assert _is_system_status("Building artifacts") is True

    def test_is_system_status_false_question(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("What should I do?") is False

    def test_is_system_status_false_long(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("A" * 100) is False

    def test_is_system_status_false_input_required(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("INPUT_REQUIRED: need info") is False

    def test_is_system_status_false_multiline_list(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        text = "Processing\n- step 1\n- step 2"
        assert _is_system_status(text) is False

    def test_is_system_status_with_emoji(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("Coding module") is True

    def test_is_system_status_empty(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("") is False

    def test_is_system_status_no_match(self):
        from hosts.gui.message_classifier import is_system_status as _is_system_status

        assert _is_system_status("Hello world") is False

    def test_is_scratchpad_content_true(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        text = "Plan:\n- step 1\n- step 2\n- step 3"
        assert _is_scratchpad_content(text) is True

    def test_is_scratchpad_content_todo(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        text = "Notes:\nTODO: fix bug\nmore stuff"
        assert _is_scratchpad_content(text) is True

    def test_is_scratchpad_content_checkbox(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        text = "Tasks:\n[ ] first\n[x] done"
        assert _is_scratchpad_content(text) is True

    def test_is_scratchpad_content_false_single_line(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        assert _is_scratchpad_content("- just one line") is False

    def test_is_scratchpad_content_false_system_status(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        assert _is_scratchpad_content("Analyzing code") is False

    def test_is_scratchpad_content_numbered_list(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        text = "Steps:\n1. first\n2. second"
        assert _is_scratchpad_content(text) is True

    def test_is_scratchpad_content_asterisk_list(self):
        from hosts.gui.message_classifier import (
            is_scratchpad_content as _is_scratchpad_content,
        )

        text = "Ideas:\n* idea one\n* idea two"
        assert _is_scratchpad_content(text) is True


# ===================================================================
# 15. profile_select.py — draw helper functions
# ===================================================================


class TestProfileSelectDrawHelpers:
    def _make_font(self):
        return pygame.freetype.SysFont("arial", 14)

    def test_draw_profile_card_default(self):
        from hosts.gui.profile_select import _draw_profile_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        rect = pygame.Rect(100, 100, 480, 80)
        profile = {
            "display_name": "AJ",
            "role": "mortal",
            "title": "Engineer",
            "pronouns": "he/him",
            "total_sessions": 5,
            "sovereignty": 30,
            "devotion": 60,
            "is_active": False,
        }
        _draw_profile_card(
            surf,
            rect,
            profile,
            self._make_font(),
            self._make_font(),
            255,
            False,
            False,
            False,
        )

    def test_draw_profile_card_hovered(self):
        from hosts.gui.profile_select import _draw_profile_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        rect = pygame.Rect(100, 100, 480, 80)
        profile = {
            "display_name": "Test",
            "role": "divine",
            "title": "",
            "pronouns": "",
            "total_sessions": 0,
            "sovereignty": 0,
            "devotion": 0,
        }
        _draw_profile_card(
            surf,
            rect,
            profile,
            self._make_font(),
            self._make_font(),
            255,
            True,
            False,
            False,
        )

    def test_draw_profile_card_active(self):
        from hosts.gui.profile_select import _draw_profile_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        rect = pygame.Rect(100, 100, 480, 80)
        profile = {
            "display_name": "Active",
            "role": "devoted",
            "title": "Devotee",
            "pronouns": "she/her",
            "total_sessions": 10,
            "sovereignty": 80,
            "devotion": 90,
            "is_active": True,
        }
        _draw_profile_card(
            surf,
            rect,
            profile,
            self._make_font(),
            self._make_font(),
            200,
            False,
            True,
            False,
        )

    def test_draw_profile_card_delete_hovered(self):
        from hosts.gui.profile_select import _draw_profile_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        rect = pygame.Rect(100, 100, 480, 80)
        profile = {
            "display_name": "X",
            "role": "unknown",
            "sovereignty": 50,
            "devotion": 50,
            "total_sessions": 1,
        }
        _draw_profile_card(
            surf,
            rect,
            profile,
            self._make_font(),
            self._make_font(),
            255,
            False,
            False,
            True,
        )

    def test_draw_new_game_button(self):
        from hosts.gui.profile_select import _draw_new_game_button

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        rect = pygame.Rect(100, 500, 480, 50)
        _draw_new_game_button(surf, rect, self._make_font(), 255, False)

    def test_draw_new_game_button_hovered(self):
        from hosts.gui.profile_select import _draw_new_game_button

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        rect = pygame.Rect(100, 500, 480, 50)
        _draw_new_game_button(surf, rect, self._make_font(), 255, True)

    def test_draw_delete_confirmation(self):
        from hosts.gui.profile_select import _draw_delete_confirmation

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        profile = {"display_name": "TestProfile"}
        _draw_delete_confirmation(surf, 800, 600, profile, self._make_font(), self._make_font())


# ===================================================================
# 16. loading_screen.py — _load_splash helper
# ===================================================================


class TestLoadingScreenHelpers:
    def test_load_splash_no_file(self):
        from hosts.gui.loading_screen import _load_splash

        with patch("hosts.gui.loading_screen._SPLASH_IMAGE", Path("/nonexistent/img.png")):
            result = _load_splash(1280, 720)
            assert result is None

    def test_load_splash_error(self):
        from hosts.gui.loading_screen import _load_splash

        mock_path = Mock()
        mock_path.exists.return_value = True
        with (
            patch("hosts.gui.loading_screen._SPLASH_IMAGE", mock_path),
            patch("hosts.gui.loading_screen.PILImage.open", side_effect=Exception("bad")),
        ):
            result = _load_splash(1280, 720)
            assert result is None

    def test_get_vignette(self):
        from hosts.gui.loading_screen import _get_vignette

        v = _get_vignette(200, 100)
        assert v.get_size() == (200, 100)
        # Second call should return cached
        v2 = _get_vignette(200, 100)
        assert v2 is v

    def test_draw_text_card_fade_in(self):
        from hosts.gui.loading_screen import _draw_text_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        font = pygame.freetype.SysFont("arial", 22)
        _draw_text_card(surf, 800, 600, 0.5, font, "Hello", "World", font)

    def test_draw_text_card_hold(self):
        from hosts.gui.loading_screen import _draw_text_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        font = pygame.freetype.SysFont("arial", 22)
        _draw_text_card(surf, 800, 600, 2.0, font, "Hello", None, None)

    def test_draw_text_card_fade_out(self):
        from hosts.gui.loading_screen import _draw_text_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        font = pygame.freetype.SysFont("arial", 22)
        _draw_text_card(surf, 800, 600, 3.2, font, "Hello", None, None)

    def test_draw_text_card_fully_faded(self):
        from hosts.gui.loading_screen import _draw_text_card

        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        font = pygame.freetype.SysFont("arial", 22)
        _draw_text_card(surf, 800, 600, 10.0, font, "Hello", None, None)

    def test_loading_ember(self):
        from hosts.gui.loading_screen import _LoadingEmber

        ember = _LoadingEmber(800, 600)
        assert hasattr(ember, "x")
        assert hasattr(ember, "alpha")
        ember.update(0.016, 800, 600)
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        ember.draw(surf)

    def test_loading_ember_faded(self):
        from hosts.gui.loading_screen import _LoadingEmber

        ember = _LoadingEmber(800, 600)
        ember.alpha = 0
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        ember.draw(surf)  # Should return early

    def test_loading_ember_reset(self):
        from hosts.gui.loading_screen import _LoadingEmber

        ember = _LoadingEmber(800, 600)
        ember.alpha = -1  # Force reset on next update
        ember.update(0.016, 800, 600)
        assert ember.alpha > 0


# ===================================================================
# 17. input_bar.py — handle_key shortcuts
# ===================================================================


class TestInputBarShortcuts:
    def _make_event(self, key, mod=0):
        e = Mock()
        e.key = key
        e.mod = mod
        e.type = pygame.KEYDOWN
        return e

    def test_ctrl_l_clears(self):
        from hosts.gui.input_bar import InputBar

        ib = InputBar()
        ib.text = "hello world"
        result = ib.handle_key(self._make_event(pygame.K_l, pygame.KMOD_CTRL))
        assert result is None
        assert ib.text == ""

    def test_ctrl_k_focus(self):
        from hosts.gui.input_bar import InputBar

        ib = InputBar()
        result = ib.handle_key(self._make_event(pygame.K_k, pygame.KMOD_CTRL))
        assert result is None

    def test_up_arrow_navigates(self):
        from hosts.gui.input_bar import InputBar

        ib = InputBar()
        ib.shortcuts.add_message("old message")
        result = ib.handle_key(self._make_event(pygame.K_UP, 0))
        assert result is None
        assert ib.text == "old message"

    def test_ctrl_backspace(self):
        from hosts.gui.input_bar import InputBar

        ib = InputBar()
        ib.text = "hello world"
        ib.handle_key(self._make_event(pygame.K_BACKSPACE, pygame.KMOD_CTRL))
        assert ib.text == "hello "

    def test_ctrl_backspace_single_word(self):
        from hosts.gui.input_bar import InputBar

        ib = InputBar()
        ib.text = "hello"
        ib.handle_key(self._make_event(pygame.K_BACKSPACE, pygame.KMOD_CTRL))
        assert ib.text == ""
