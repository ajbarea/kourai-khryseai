from __future__ import annotations

import time

import pytest

pytest.importorskip("pygame")

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.dialogue import DialogueEntry, DialogueHistory
from tests.unit.gui_test_helpers import _surf


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

    def test_scroll_uses_current_viewport_height(self):
        h = DialogueHistory()
        h._content_h = 2000
        h._viewport_h = 400

        h.scroll_to_bottom()

        assert h._scroll_y == 2000 - (400 - h.PAD * 2 - 60)

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
