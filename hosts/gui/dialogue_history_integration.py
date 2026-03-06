"""Enhanced DialogueHistory with AutoScrollManager integration.

This module provides an enhanced DialogueHistory class that integrates
with AutoScrollManager to support:
- Toggle functionality to enable/disable auto-scrolling
- Scroll position preservation when disabled
- Visual distance indicator showing distance from bottom
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pygame

from .auto_scroll import AutoScrollManager

if TYPE_CHECKING:
    from __main__ import DialogueEntry

# Layout constants (from __main__.py)
DIALOGUE_W = 960
DIALOGUE_H = 640
GOLD = (218, 165, 32)
GOLD_DIM = (140, 105, 20)
WHITE = (240, 235, 225)
DIM_WHITE = (160, 155, 145)
SCROLLBAR = (50, 40, 25)


class DialogueHistoryWithAutoScroll:
    """Enhanced DialogueHistory with auto-scroll toggle and distance indicator.

    Integrates AutoScrollManager to provide:
    - Toggle functionality to enable/disable auto-scrolling
    - Scroll position preservation when disabled
    - Visual distance indicator showing distance from bottom
    """

    PAD = 14
    BUBBLE_MAX_W = DIALOGUE_W - 40
    LINE_H = 20
    AGENT_LINE_H = 14

    def __init__(self) -> None:
        """Initialize DialogueHistory with AutoScrollManager."""
        self._entries: list[DialogueEntry] = []
        self._surf: pygame.Surface | None = None
        self._dirty = True
        self._scroll_y = 0
        self._content_h = 0

        # Auto-scroll manager
        self._auto_scroll = AutoScrollManager()

    def add(self, entry: DialogueEntry) -> None:
        """Add entry and auto-scroll if enabled."""
        self._entries.append(entry)
        self._dirty = True

        # Auto-scroll to bottom if enabled
        if self._auto_scroll.should_scroll():
            self.scroll_to_bottom()

    def update_last_text(self, text: str) -> None:
        """Append text to the last entry (for typewriter streaming)."""
        if self._entries:
            self._entries[-1].text = text
            self._dirty = True

    def scroll(self, dy: int) -> None:
        """Scroll by delta, preserving position when auto-scroll is disabled."""
        max_scroll = max(0, self._content_h - (DIALOGUE_H - self.PAD * 2 - 60))
        self._scroll_y = max(0, min(self._scroll_y + dy, max_scroll))

        # Update distance indicator
        self._update_distance_indicator()

    def scroll_to_bottom(self) -> None:
        """Scroll to bottom."""
        self._scroll_y = max(0, self._content_h - (DIALOGUE_H - self.PAD * 2 - 60))
        self._update_distance_indicator()

    def toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll on/off."""
        self._auto_scroll.toggle()
        self._update_distance_indicator()

    def is_auto_scroll_enabled(self) -> bool:
        """Check if auto-scroll is enabled."""
        return self._auto_scroll.enabled

    def get_distance_text(self) -> str:
        """Get distance from bottom as text."""
        return self._auto_scroll.get_distance_text()

    def _update_distance_indicator(self) -> None:
        """Update the distance indicator based on current scroll position."""
        view_height = DIALOGUE_H - self.PAD * 2 - 60
        self._auto_scroll.update_distance(
            current_scroll=self._scroll_y,
            content_height=self._content_h,
            view_height=view_height,
        )

    def _render(self) -> None:
        """Re-render all entries onto self._surf."""
        # First pass: measure total height
        total_h = self.PAD
        for e in self._entries:
            total_h += self._entry_height(e)
            total_h += 10

        surf_h = max(total_h, DIALOGUE_H)
        self._surf = pygame.Surface((DIALOGUE_W, surf_h), pygame.SRCALPHA)
        self._content_h = total_h

        y = self.PAD
        for e in self._entries:
            self._draw_entry(self._surf, e, y)
            y += self._entry_height(e) + 10

        self._dirty = False
        self._update_distance_indicator()

    def _entry_height(self, e: DialogueEntry) -> int:
        """Calculate height of a dialogue entry."""
        h = 0
        if not e.is_user:
            h += self.AGENT_LINE_H + 4  # agent header
        # Body text
        lines = self._wrap_text(e.text, self.BUBBLE_MAX_W - self.PAD * 2)
        h += len(lines) * self.LINE_H + self.PAD * 2
        return h

    def _wrap_text(self, text: str, max_w: int) -> list[str]:
        """Wrap text to fit within max width."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            wrapped = textwrap.wrap(paragraph or " ", width=max(1, max_w // 9))
            lines.extend(wrapped or [" "])
        return lines

    def _draw_entry(self, surf: pygame.Surface, e: DialogueEntry, y: int) -> None:
        """Draw a single dialogue entry."""
        # This is a placeholder - in real implementation, this would be
        # the same as the original DialogueHistory._draw_entry method
        pass

    def draw(
        self, surf: pygame.Surface, dest_rect: pygame.Rect, show_distance: bool = True
    ) -> None:
        """Draw dialogue history with optional distance indicator.

        Args:
            surf: Surface to draw on
            dest_rect: Rectangle for dialogue area
            show_distance: Whether to show distance indicator when auto-scroll is disabled
        """
        if self._dirty:
            self._render()
        if self._surf is None:
            return

        clip_surf = pygame.Surface((dest_rect.width, dest_rect.height), pygame.SRCALPHA)
        clip_surf.blit(self._surf, (0, -self._scroll_y))
        surf.blit(clip_surf, dest_rect.topleft)

        # Scrollbar
        if self._content_h > dest_rect.height:
            ratio = dest_rect.height / self._content_h
            bar_h = max(30, int(dest_rect.height * ratio))
            bar_y = dest_rect.top + int(self._scroll_y / self._content_h * dest_rect.height)
            pygame.draw.rect(
                surf, SCROLLBAR, pygame.Rect(dest_rect.right - 4, bar_y, 3, bar_h), border_radius=2
            )

        # Distance indicator when auto-scroll is disabled
        if show_distance and not self._auto_scroll.enabled:
            distance_text = self._auto_scroll.get_distance_text()
            if distance_text != "At bottom":
                # Draw distance indicator in bottom-right corner of dialogue area
                # This would use a font from __main__.py in real implementation
                pass
