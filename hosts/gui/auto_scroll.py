"""Auto-scroll manager for dialogue history.

Tracks whether auto-scroll is enabled and provides a distance indicator
showing how far the view is from the bottom of the content.
"""

from __future__ import annotations


class AutoScrollManager:
    """Manages auto-scroll state and distance-from-bottom indicator."""

    def __init__(self) -> None:
        self.enabled = True
        self._distance_lines = 0

    def toggle(self) -> None:
        """Toggle auto-scroll on/off."""
        self.enabled = not self.enabled

    def should_scroll(self) -> bool:
        """Return True if auto-scroll should move to the bottom."""
        return self.enabled

    def update_distance(self, current_scroll: int, content_height: int, view_height: int) -> None:
        """Update the distance indicator based on scroll position.

        Args:
            current_scroll: Current scroll offset in pixels.
            content_height: Total content height in pixels.
            view_height: Visible view height in pixels.
        """
        max_scroll = max(0, content_height - view_height)
        if max_scroll == 0:
            self._distance_lines = 0
        else:
            remaining = max_scroll - current_scroll
            self._distance_lines = max(0, remaining // 20)

    def get_distance_text(self) -> str:
        """Return human-readable distance from the bottom."""
        if self._distance_lines == 0:
            return "At bottom"
        return f"{self._distance_lines} lines above"
