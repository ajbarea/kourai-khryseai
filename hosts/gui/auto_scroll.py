"""Auto-scroll manager for dialogue history with toggle and distance indicator."""


class AutoScrollManager:
    """Manages auto-scrolling behavior with toggle and visual indicator.

    Supports:
    - Toggle functionality to enable/disable auto-scrolling
    - Scroll position preservation when disabled
    - Scroll distance indicator showing distance from bottom
    """

    def __init__(self) -> None:
        """Initialize AutoScrollManager with auto-scroll enabled by default."""
        self.enabled = True
        self.scroll_distance = 0
        self._last_scroll_y = 0

    def toggle(self) -> None:
        """Toggle auto-scroll on/off."""
        self.enabled = not self.enabled

    def should_scroll(self) -> bool:
        """Check if auto-scroll should occur.

        Returns:
            True if auto-scroll is enabled, False otherwise.
        """
        return self.enabled

    def update_distance(self, current_scroll: int, content_height: int, view_height: int) -> None:
        """Update scroll distance indicator.

        Calculates the distance from the current scroll position to the bottom
        of the content.

        Args:
            current_scroll: Current scroll position in pixels
            content_height: Total height of content in pixels
            view_height: Height of visible area in pixels
        """
        # Maximum scroll position (bottom of content)
        max_scroll = max(0, content_height - view_height)
        # Distance from current position to bottom
        self.scroll_distance = max(0, max_scroll - current_scroll)
        self._last_scroll_y = current_scroll

    def get_distance_text(self) -> str:
        """Get distance from bottom as text.

        Returns:
            Human-readable text showing distance from bottom.
            Examples: "↓ 5 messages", "↓ 1 message", "At bottom"
        """
        if self.scroll_distance == 0:
            return "At bottom"

        # Estimate number of messages based on typical message height
        # Assuming average message height of ~60 pixels
        message_count = max(1, self.scroll_distance // 60)

        if message_count == 1:
            return "↓ 1 message"
        else:
            return f"↓ {message_count} messages"
