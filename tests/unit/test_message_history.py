"""Tests for MessageHistory class."""

from hosts.gui.message_history import MessageHistory


class TestMessageHistoryInit:
    """Test MessageHistory initialization."""

    def test_init_default_max_size(self) -> None:
        """Test initialization with default max size."""
        history = MessageHistory()
        assert len(history) == 0

    def test_init_custom_max_size(self) -> None:
        """Test initialization with custom max size."""
        history = MessageHistory(max_size=10)
        assert len(history) == 0

    def test_init_index_at_most_recent(self) -> None:
        """Test that index starts at most recent position."""
        history = MessageHistory()
        assert history.get_current() is None


class TestMessageHistoryAdd:
    """Test adding messages to history."""

    def test_add_single_message(self) -> None:
        """Test adding a single message."""
        history = MessageHistory()
        history.add("Hello")
        assert len(history) == 1

    def test_add_multiple_messages(self) -> None:
        """Test adding multiple messages."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.add("Third")
        assert len(history) == 3

    def test_add_ignores_empty_messages(self) -> None:
        """Test that empty messages are ignored."""
        history = MessageHistory()
        history.add("")
        history.add("   ")
        assert len(history) == 0

    def test_add_respects_max_size(self) -> None:
        """Test that history respects max size limit."""
        history = MessageHistory(max_size=3)
        history.add("First")
        history.add("Second")
        history.add("Third")
        history.add("Fourth")
        assert len(history) == 3

    def test_add_removes_oldest_when_full(self) -> None:
        """Test that oldest message is removed when max size exceeded."""
        history = MessageHistory(max_size=2)
        history.add("First")
        history.add("Second")
        history.add("Third")
        # Navigate to check which messages remain
        msg = history.navigate(-1)
        assert msg == "Third"
        msg = history.navigate(-1)
        assert msg == "Second"

    def test_add_resets_index(self) -> None:
        """Test that adding a message resets the index."""
        history = MessageHistory()
        history.add("First")
        history.navigate(-1)  # Move to first message
        history.add("Second")
        assert history.get_current() is None


class TestMessageHistoryNavigate:
    """Test navigating through message history."""

    def test_navigate_empty_history(self) -> None:
        """Test navigating empty history returns None."""
        history = MessageHistory()
        assert history.navigate(-1) is None
        assert history.navigate(1) is None

    def test_navigate_up_from_most_recent(self) -> None:
        """Test navigating up from most recent position."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        msg = history.navigate(-1)
        assert msg == "Second"

    def test_navigate_up_multiple_times(self) -> None:
        """Test navigating up multiple times."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.add("Third")
        msg1 = history.navigate(-1)
        assert msg1 == "Third"
        msg2 = history.navigate(-1)
        assert msg2 == "Second"
        msg3 = history.navigate(-1)
        assert msg3 == "First"

    def test_navigate_down_from_oldest(self) -> None:
        """Test navigating down from oldest message."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)  # Go to Second
        history.navigate(-1)  # Go to First
        msg = history.navigate(1)
        assert msg == "Second"

    def test_navigate_down_to_most_recent(self) -> None:
        """Test navigating down to most recent position."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)  # Go to Second
        history.navigate(-1)  # Go to First
        history.navigate(1)  # Go to Second
        msg = history.navigate(1)
        # When at most recent and going down, wrap to oldest
        assert msg == "First"

    def test_navigate_wraparound_up(self) -> None:
        """Test wraparound when navigating up from oldest."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)  # Go to Second
        history.navigate(-1)  # Go to First
        msg = history.navigate(-1)  # Wrap to Second
        assert msg == "Second"

    def test_navigate_wraparound_down(self) -> None:
        """Test wraparound when navigating down from most recent."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)  # Go to Second
        msg = history.navigate(1)  # Wrap to First
        assert msg == "First"

    def test_navigate_single_message(self) -> None:
        """Test navigating with single message."""
        history = MessageHistory()
        history.add("Only")
        msg = history.navigate(-1)
        assert msg == "Only"
        msg = history.navigate(1)
        # Wrap to the only message
        assert msg == "Only"


class TestMessageHistoryReset:
    """Test resetting message history position."""

    def test_reset_from_navigated_position(self) -> None:
        """Test resetting from a navigated position."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)  # Navigate to Second
        history.reset()
        assert history.get_current() is None

    def test_reset_allows_navigation_again(self) -> None:
        """Test that reset allows navigation to start over."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)
        history.reset()
        msg = history.navigate(-1)
        assert msg == "Second"

    def test_reset_multiple_times(self) -> None:
        """Test resetting multiple times."""
        history = MessageHistory()
        history.add("Message")
        history.navigate(-1)
        history.reset()
        history.navigate(-1)
        history.reset()
        assert history.get_current() is None


class TestMessageHistoryGetCurrent:
    """Test getting current message without navigating."""

    def test_get_current_at_most_recent(self) -> None:
        """Test getting current at most recent position."""
        history = MessageHistory()
        history.add("Message")
        assert history.get_current() is None

    def test_get_current_after_navigate(self) -> None:
        """Test getting current after navigating."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)
        assert history.get_current() == "Second"

    def test_get_current_does_not_navigate(self) -> None:
        """Test that get_current doesn't change position."""
        history = MessageHistory()
        history.add("First")
        history.add("Second")
        history.navigate(-1)
        msg1 = history.get_current()
        msg2 = history.get_current()
        assert msg1 == msg2 == "Second"


class TestMessageHistoryEdgeCases:
    """Test edge cases and special scenarios."""

    def test_whitespace_only_messages_ignored(self) -> None:
        """Test that whitespace-only messages are ignored."""
        history = MessageHistory()
        history.add("   \t\n   ")
        assert len(history) == 0

    def test_messages_with_special_characters(self) -> None:
        """Test messages with special characters."""
        history = MessageHistory()
        history.add("Hello! @#$%^&*()")
        history.add("Unicode: 你好 🎉")
        assert len(history) == 2
        msg = history.navigate(-1)
        assert msg == "Unicode: 你好 🎉"

    def test_very_long_messages(self) -> None:
        """Test handling very long messages."""
        history = MessageHistory()
        long_msg = "x" * 10000
        history.add(long_msg)
        msg = history.navigate(-1)
        assert msg == long_msg

    def test_max_size_boundary(self) -> None:
        """Test behavior at max size boundary."""
        history = MessageHistory(max_size=5)
        for i in range(10):
            history.add(f"Message {i}")
        assert len(history) == 5

    def test_navigate_after_max_size_exceeded(self) -> None:
        """Test navigation after max size is exceeded."""
        history = MessageHistory(max_size=2)
        history.add("First")
        history.add("Second")
        history.add("Third")
        # Should only have Second and Third
        msg1 = history.navigate(-1)
        assert msg1 == "Third"
        msg2 = history.navigate(-1)
        assert msg2 == "Second"
        msg3 = history.navigate(-1)
        # Wrap to Third
        assert msg3 == "Third"

    def test_len_method(self) -> None:
        """Test __len__ method."""
        history = MessageHistory()
        assert len(history) == 0
        history.add("First")
        assert len(history) == 1
        history.add("Second")
        assert len(history) == 2

    def test_state_independence(self) -> None:
        """Test that multiple instances are independent."""
        history1 = MessageHistory()
        history2 = MessageHistory()
        history1.add("Message 1")
        history2.add("Message 2")
        assert len(history1) == 1
        assert len(history2) == 1
        msg1 = history1.navigate(-1)
        msg2 = history2.navigate(-1)
        assert msg1 == "Message 1"
        assert msg2 == "Message 2"
