"""Unit tests for AutoScrollManager."""

from hosts.gui.auto_scroll import AutoScrollManager


class TestAutoScrollManagerBasic:
    """Test basic initialization and state management."""

    def test_init_enabled_by_default(self) -> None:
        """Test that auto-scroll is enabled by default."""
        manager = AutoScrollManager()
        assert manager.enabled is True

    def test_init_scroll_distance_zero(self) -> None:
        """Test that scroll distance is initialized to zero."""
        manager = AutoScrollManager()
        assert manager.scroll_distance == 0

    def test_init_last_scroll_y_zero(self) -> None:
        """Test that last scroll position is initialized to zero."""
        manager = AutoScrollManager()
        assert manager._last_scroll_y == 0

    def test_should_scroll_when_enabled(self) -> None:
        """Test should_scroll returns True when enabled."""
        manager = AutoScrollManager()
        manager.enabled = True
        assert manager.should_scroll() is True

    def test_should_scroll_when_disabled(self) -> None:
        """Test should_scroll returns False when disabled."""
        manager = AutoScrollManager()
        manager.enabled = False
        assert manager.should_scroll() is False


class TestAutoScrollToggle:
    """Test toggle functionality."""

    def test_toggle_from_enabled_to_disabled(self) -> None:
        """Test toggling from enabled to disabled."""
        manager = AutoScrollManager()
        manager.enabled = True
        manager.toggle()
        assert manager.enabled is False

    def test_toggle_from_disabled_to_enabled(self) -> None:
        """Test toggling from disabled to enabled."""
        manager = AutoScrollManager()
        manager.enabled = False
        manager.toggle()
        assert manager.enabled is True

    def test_toggle_multiple_times(self) -> None:
        """Test toggling multiple times."""
        manager = AutoScrollManager()
        initial = manager.enabled
        manager.toggle()
        manager.toggle()
        assert manager.enabled == initial

    def test_toggle_preserves_scroll_distance(self) -> None:
        """Test that toggle preserves scroll distance."""
        manager = AutoScrollManager()
        manager.update_distance(100, 1000, 500)
        distance_before = manager.scroll_distance
        manager.toggle()
        assert manager.scroll_distance == distance_before


class TestAutoScrollDistance:
    """Test scroll distance calculation."""

    def test_update_distance_at_bottom(self) -> None:
        """Test distance calculation when at bottom."""
        manager = AutoScrollManager()
        # At bottom: current_scroll = max_scroll
        manager.update_distance(current_scroll=500, content_height=1000, view_height=500)
        assert manager.scroll_distance == 0

    def test_update_distance_at_top(self) -> None:
        """Test distance calculation when at top."""
        manager = AutoScrollManager()
        # At top: current_scroll = 0, max_scroll = 500
        manager.update_distance(current_scroll=0, content_height=1000, view_height=500)
        assert manager.scroll_distance == 500

    def test_update_distance_in_middle(self) -> None:
        """Test distance calculation in middle of content."""
        manager = AutoScrollManager()
        # Middle: current_scroll = 250, max_scroll = 500
        manager.update_distance(current_scroll=250, content_height=1000, view_height=500)
        assert manager.scroll_distance == 250

    def test_update_distance_stores_scroll_position(self) -> None:
        """Test that update_distance stores the scroll position."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=123, content_height=1000, view_height=500)
        assert manager._last_scroll_y == 123

    def test_update_distance_with_small_content(self) -> None:
        """Test distance when content is smaller than view."""
        manager = AutoScrollManager()
        # Content smaller than view: max_scroll = 0
        manager.update_distance(current_scroll=0, content_height=300, view_height=500)
        assert manager.scroll_distance == 0

    def test_update_distance_with_large_content(self) -> None:
        """Test distance with very large content."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=0, content_height=10000, view_height=500)
        assert manager.scroll_distance == 9500

    def test_update_distance_negative_scroll_clamped(self) -> None:
        """Test that negative scroll is clamped to zero."""
        manager = AutoScrollManager()
        # Negative scroll should be treated as 0
        manager.update_distance(current_scroll=-100, content_height=1000, view_height=500)
        # max_scroll = 500, distance = 500 - (-100) = 600
        assert manager.scroll_distance == 600


class TestAutoScrollDistanceText:
    """Test distance text formatting."""

    def test_get_distance_text_at_bottom(self) -> None:
        """Test distance text when at bottom."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=500, content_height=1000, view_height=500)
        assert manager.get_distance_text() == "At bottom"

    def test_get_distance_text_one_message(self) -> None:
        """Test distance text for approximately one message."""
        manager = AutoScrollManager()
        # One message ≈ 60 pixels
        manager.update_distance(current_scroll=440, content_height=1000, view_height=500)
        assert manager.get_distance_text() == "↓ 1 message"

    def test_get_distance_text_multiple_messages(self) -> None:
        """Test distance text for multiple messages."""
        manager = AutoScrollManager()
        # Three messages ≈ 180 pixels
        manager.update_distance(current_scroll=320, content_height=1000, view_height=500)
        assert manager.get_distance_text() == "↓ 3 messages"

    def test_get_distance_text_many_messages(self) -> None:
        """Test distance text for many messages."""
        manager = AutoScrollManager()
        # Ten messages ≈ 600 pixels
        manager.update_distance(current_scroll=0, content_height=1000, view_height=500)
        # distance = 500, 500 // 60 = 8
        assert "↓" in manager.get_distance_text()
        assert "messages" in manager.get_distance_text()

    def test_get_distance_text_before_update(self) -> None:
        """Test distance text before any update."""
        manager = AutoScrollManager()
        # Before update, distance is 0
        assert manager.get_distance_text() == "At bottom"

    def test_get_distance_text_singular_vs_plural(self) -> None:
        """Test singular vs plural message text."""
        manager = AutoScrollManager()

        # One message
        manager.update_distance(current_scroll=440, content_height=1000, view_height=500)
        text_one = manager.get_distance_text()
        assert "1 message" in text_one

        # Two messages
        manager.update_distance(current_scroll=380, content_height=1000, view_height=500)
        text_two = manager.get_distance_text()
        assert "messages" in text_two
        assert "1" not in text_two or "2" in text_two


class TestAutoScrollPreservation:
    """Test scroll position preservation when disabled."""

    def test_disabled_preserves_position_on_update(self) -> None:
        """Test that disabled auto-scroll preserves position."""
        manager = AutoScrollManager()
        manager.enabled = False

        # Set initial position
        manager.update_distance(current_scroll=200, content_height=1000, view_height=500)

        # Update with new content (simulating new message)
        manager.update_distance(current_scroll=200, content_height=1100, view_height=500)

        # Position should be preserved (distance should increase due to more content)
        assert manager._last_scroll_y == 200

    def test_enabled_updates_position(self) -> None:
        """Test that enabled auto-scroll updates position."""
        manager = AutoScrollManager()
        manager.enabled = True

        manager.update_distance(current_scroll=200, content_height=1000, view_height=500)
        assert manager._last_scroll_y == 200


class TestAutoScrollEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_view_height(self) -> None:
        """Test with zero view height."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=0, content_height=1000, view_height=0)
        # max_scroll = 1000, distance = 1000
        assert manager.scroll_distance == 1000

    def test_zero_content_height(self) -> None:
        """Test with zero content height."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=0, content_height=0, view_height=500)
        # max_scroll = 0, distance = 0
        assert manager.scroll_distance == 0

    def test_equal_content_and_view_height(self) -> None:
        """Test when content height equals view height."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=0, content_height=500, view_height=500)
        # max_scroll = 0, distance = 0
        assert manager.scroll_distance == 0

    def test_very_large_scroll_distance(self) -> None:
        """Test with very large scroll distance."""
        manager = AutoScrollManager()
        manager.update_distance(current_scroll=0, content_height=100000, view_height=500)
        assert manager.scroll_distance == 99500

    def test_scroll_position_exceeds_max(self) -> None:
        """Test when scroll position exceeds maximum."""
        manager = AutoScrollManager()
        # current_scroll > max_scroll (shouldn't happen but test robustness)
        manager.update_distance(current_scroll=600, content_height=1000, view_height=500)
        # max_scroll = 500, distance = max(0, 500 - 600) = 0
        assert manager.scroll_distance == 0

    def test_multiple_updates_in_sequence(self) -> None:
        """Test multiple distance updates in sequence."""
        manager = AutoScrollManager()

        manager.update_distance(current_scroll=0, content_height=1000, view_height=500)
        assert manager.scroll_distance == 500

        manager.update_distance(current_scroll=250, content_height=1000, view_height=500)
        assert manager.scroll_distance == 250

        manager.update_distance(current_scroll=500, content_height=1000, view_height=500)
        assert manager.scroll_distance == 0

    def test_state_independence(self) -> None:
        """Test that multiple managers are independent."""
        manager1 = AutoScrollManager()
        manager2 = AutoScrollManager()

        manager1.enabled = False
        manager1.update_distance(100, 1000, 500)

        manager2.enabled = True
        manager2.update_distance(200, 1000, 500)

        assert manager1.enabled is False
        assert manager2.enabled is True
        assert manager1._last_scroll_y == 100
        assert manager2._last_scroll_y == 200
