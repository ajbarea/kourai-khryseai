"""Integration tests for AutoScrollManager with DialogueHistory.

Tests the integration of AutoScrollManager with DialogueHistory to ensure
proper scroll behavior based on auto-scroll state.
"""

from hosts.gui.auto_scroll import AutoScrollManager


class MockDialogueEntry:
    """Mock DialogueEntry for testing."""

    def __init__(self, text: str, is_user: bool = False) -> None:
        self.text = text
        self.is_user = is_user
        self.agent = "test_agent"
        self.is_result = False
        self.is_error = False


class DialogueHistoryWithAutoScroll:
    """Simplified DialogueHistory with AutoScrollManager integration for testing."""

    def __init__(self) -> None:
        self._entries: list[MockDialogueEntry] = []
        self._scroll_y = 0
        self._content_h = 0
        self._auto_scroll = AutoScrollManager()
        self._view_height = 500

    def add(self, entry: MockDialogueEntry) -> None:
        """Add entry and auto-scroll if enabled."""
        self._entries.append(entry)
        # Simulate content height increase
        self._content_h += 60  # Assume each entry is ~60 pixels

        # Auto-scroll to bottom if enabled
        if self._auto_scroll.should_scroll():
            self.scroll_to_bottom()

    def scroll(self, dy: int) -> None:
        """Scroll by delta."""
        max_scroll = max(0, self._content_h - self._view_height)
        self._scroll_y = max(0, min(self._scroll_y + dy, max_scroll))
        self._update_distance_indicator()

    def scroll_to_bottom(self) -> None:
        """Scroll to bottom."""
        self._scroll_y = max(0, self._content_h - self._view_height)
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
        """Update the distance indicator."""
        self._auto_scroll.update_distance(
            current_scroll=self._scroll_y,
            content_height=self._content_h,
            view_height=self._view_height,
        )


class TestAutoScrollIntegrationBasic:
    """Test basic integration of AutoScrollManager with DialogueHistory."""

    def test_auto_scroll_enabled_by_default(self) -> None:
        """Test that auto-scroll is enabled by default."""
        history = DialogueHistoryWithAutoScroll()
        assert history.is_auto_scroll_enabled() is True

    def test_add_entry_scrolls_to_bottom_when_enabled(self) -> None:
        """Test that adding entry scrolls to bottom when auto-scroll is enabled."""
        history = DialogueHistoryWithAutoScroll()
        history.add(MockDialogueEntry("First message"))

        # Should be at bottom
        max_scroll = max(0, history._content_h - history._view_height)
        assert history._scroll_y == max_scroll

    def test_add_entry_preserves_position_when_disabled(self) -> None:
        """Test that adding entry preserves position when auto-scroll is disabled."""
        history = DialogueHistoryWithAutoScroll()
        history.add(MockDialogueEntry("First message"))

        # Disable auto-scroll
        history.toggle_auto_scroll()

        # Scroll up
        history.scroll(-100)
        position_before = history._scroll_y

        # Add new entry
        history.add(MockDialogueEntry("Second message"))

        # Position should be preserved
        assert history._scroll_y == position_before

    def test_toggle_auto_scroll(self) -> None:
        """Test toggling auto-scroll on/off."""
        history = DialogueHistoryWithAutoScroll()

        assert history.is_auto_scroll_enabled() is True
        history.toggle_auto_scroll()
        assert history.is_auto_scroll_enabled() is False
        history.toggle_auto_scroll()
        assert history.is_auto_scroll_enabled() is True


class TestAutoScrollIntegrationScrollBehavior:
    """Test scroll behavior based on auto-scroll state."""

    def test_manual_scroll_updates_distance(self) -> None:
        """Test that manual scroll updates distance indicator."""
        history = DialogueHistoryWithAutoScroll()
        history._view_height = 100  # Very small view to allow scrolling

        # Add many messages to create scrollable content
        for i in range(10):
            history.add(MockDialogueEntry(f"Message {i}"))

        # First scroll to bottom to establish max scroll
        history.scroll_to_bottom()
        max(0, history._content_h - history._view_height)

        # Scroll up from bottom
        history.scroll(-200)

        # Distance should be non-zero (we scrolled up)
        assert history._auto_scroll.scroll_distance > 0

    def test_scroll_to_bottom_resets_distance(self) -> None:
        """Test that scrolling to bottom resets distance to zero."""
        history = DialogueHistoryWithAutoScroll()
        history._view_height = 100  # Very small view to allow scrolling

        # Add many messages to create scrollable content
        for i in range(10):
            history.add(MockDialogueEntry(f"Message {i}"))

        # First scroll to bottom to establish max scroll
        history.scroll_to_bottom()
        max(0, history._content_h - history._view_height)

        # Scroll up from bottom
        history.scroll(-200)
        assert history._auto_scroll.scroll_distance > 0

        # Scroll to bottom
        history.scroll_to_bottom()
        assert history._auto_scroll.scroll_distance == 0

    def test_distance_text_at_bottom(self) -> None:
        """Test distance text when at bottom."""
        history = DialogueHistoryWithAutoScroll()
        history.add(MockDialogueEntry("Message 1"))

        assert history.get_distance_text() == "At bottom"

    def test_distance_text_when_scrolled_up(self) -> None:
        """Test distance text when scrolled up."""
        history = DialogueHistoryWithAutoScroll()
        for i in range(10):
            history.add(MockDialogueEntry(f"Message {i}"))

        # Scroll up
        history.scroll(-200)

        distance_text = history.get_distance_text()
        assert "↓" in distance_text
        assert "messages" in distance_text or "message" in distance_text


class TestAutoScrollIntegrationMultipleMessages:
    """Test auto-scroll behavior with multiple messages."""

    def test_multiple_messages_auto_scroll_enabled(self) -> None:
        """Test that multiple messages auto-scroll to bottom when enabled."""
        history = DialogueHistoryWithAutoScroll()

        for i in range(5):
            history.add(MockDialogueEntry(f"Message {i}"))
            # Should always be at bottom
            max_scroll = max(0, history._content_h - history._view_height)
            assert history._scroll_y == max_scroll

    def test_multiple_messages_auto_scroll_disabled(self) -> None:
        """Test that multiple messages preserve position when disabled."""
        history = DialogueHistoryWithAutoScroll()

        # Add first message
        history.add(MockDialogueEntry("Message 1"))

        # Disable auto-scroll
        history.toggle_auto_scroll()

        # Scroll to middle
        history.scroll(-100)
        position = history._scroll_y

        # Add more messages
        for i in range(2, 6):
            history.add(MockDialogueEntry(f"Message {i}"))
            # Position should be preserved
            assert history._scroll_y == position

    def test_toggle_during_conversation(self) -> None:
        """Test toggling auto-scroll during conversation."""
        history = DialogueHistoryWithAutoScroll()

        # Add messages with auto-scroll enabled
        for i in range(3):
            history.add(MockDialogueEntry(f"Message {i}"))

        # Should be at bottom
        max_scroll = max(0, history._content_h - history._view_height)
        assert history._scroll_y == max_scroll

        # Disable auto-scroll
        history.toggle_auto_scroll()

        # Scroll up
        history.scroll(-100)
        position = history._scroll_y

        # Add more messages
        history.add(MockDialogueEntry("Message 3"))
        assert history._scroll_y == position

        # Re-enable auto-scroll
        history.toggle_auto_scroll()

        # Add message - should scroll to bottom
        history.add(MockDialogueEntry("Message 4"))
        max_scroll = max(0, history._content_h - history._view_height)
        assert history._scroll_y == max_scroll


class TestAutoScrollIntegrationEdgeCases:
    """Test edge cases in auto-scroll integration."""

    def test_empty_history(self) -> None:
        """Test with empty history."""
        history = DialogueHistoryWithAutoScroll()
        assert history._scroll_y == 0
        assert history.get_distance_text() == "At bottom"

    def test_single_message(self) -> None:
        """Test with single message."""
        history = DialogueHistoryWithAutoScroll()
        history.add(MockDialogueEntry("Only message"))

        # Should be at bottom
        max_scroll = max(0, history._content_h - history._view_height)
        assert history._scroll_y == max_scroll

    def test_content_smaller_than_view(self) -> None:
        """Test when content is smaller than view height."""
        history = DialogueHistoryWithAutoScroll()
        history._view_height = 1000  # Very large view

        history.add(MockDialogueEntry("Message 1"))

        # Should be at top (no scrolling needed)
        assert history._scroll_y == 0

    def test_rapid_toggle(self) -> None:
        """Test rapid toggling of auto-scroll."""
        history = DialogueHistoryWithAutoScroll()

        for _ in range(10):
            history.toggle_auto_scroll()

        # Should be back to enabled
        assert history.is_auto_scroll_enabled() is True

    def test_scroll_bounds_respected(self) -> None:
        """Test that scroll position respects bounds."""
        history = DialogueHistoryWithAutoScroll()

        for i in range(5):
            history.add(MockDialogueEntry(f"Message {i}"))

        # Try to scroll beyond bounds
        history.scroll(-10000)

        # Should be clamped to valid range
        assert history._scroll_y >= 0
        max_scroll = max(0, history._content_h - history._view_height)
        assert history._scroll_y <= max_scroll


class TestAutoScrollIntegrationStateConsistency:
    """Test state consistency across operations."""

    def test_distance_indicator_consistency(self) -> None:
        """Test that distance indicator is consistent with scroll position."""
        history = DialogueHistoryWithAutoScroll()

        for i in range(10):
            history.add(MockDialogueEntry(f"Message {i}"))

        # Scroll to various positions
        for scroll_amount in [0, -50, -100, -200]:
            history.scroll(scroll_amount)

            # Distance should match scroll position
            max_scroll = max(0, history._content_h - history._view_height)
            expected_distance = max(0, max_scroll - history._scroll_y)
            assert history._auto_scroll.scroll_distance == expected_distance

    def test_auto_scroll_state_independent_of_scroll_position(self) -> None:
        """Test that auto-scroll state is independent of scroll position."""
        history = DialogueHistoryWithAutoScroll()

        for i in range(5):
            history.add(MockDialogueEntry(f"Message {i}"))

        # Scroll to various positions
        for _ in range(3):
            history.scroll(-50)

        # Auto-scroll state should be independent
        assert history.is_auto_scroll_enabled() is True

        history.toggle_auto_scroll()
        assert history.is_auto_scroll_enabled() is False

        # Scroll more
        history.scroll(-50)
        assert history.is_auto_scroll_enabled() is False
