"""Tests for KeyboardShortcuts class."""

import pygame

from hosts.gui.keyboard_shortcuts import KeyboardShortcuts

# Initialize pygame for testing
pygame.init()


class TestKeyboardShortcutsInit:
    """Test KeyboardShortcuts initialization."""

    def test_init_creates_message_history(self) -> None:
        """Test that initialization creates message history."""
        shortcuts = KeyboardShortcuts()
        assert shortcuts.message_history is not None

    def test_init_no_focus(self) -> None:
        """Test that initialization has no focus."""
        shortcuts = KeyboardShortcuts()
        assert shortcuts.has_focus() is False


class TestKeyboardShortcutsCtrlK:
    """Test Ctrl+K focus shortcut."""

    def test_ctrl_k_sets_focus(self) -> None:
        """Test that Ctrl+K sets focus."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event, "")
        assert result == {"action": "focus"}
        assert shortcuts.has_focus() is True

    def test_ctrl_k_returns_focus_action(self) -> None:
        """Test that Ctrl+K returns focus action."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event, "")
        assert result["action"] == "focus"

    def test_ctrl_k_with_text(self) -> None:
        """Test Ctrl+K with existing text."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event, "existing text")
        assert result == {"action": "focus"}


class TestKeyboardShortcutsCtrlL:
    """Test Ctrl+L clear shortcut."""

    def test_ctrl_l_clears_input(self) -> None:
        """Test that Ctrl+L clears the input."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("Previous message")
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event, "current text")
        assert result == {"action": "clear"}

    def test_ctrl_l_resets_history_position(self) -> None:
        """Test that Ctrl+L resets history position."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("Message 1")
        shortcuts.add_message("Message 2")
        shortcuts.message_history.navigate(-1)  # Navigate to Message 2
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=pygame.KMOD_CTRL)
        shortcuts.handle_key(event, "")
        assert shortcuts.message_history.get_current() is None

    def test_ctrl_l_with_empty_input(self) -> None:
        """Test Ctrl+L with empty input."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event, "")
        assert result == {"action": "clear"}


class TestKeyboardShortcutsUpArrow:
    """Test Up arrow navigation."""

    def test_up_arrow_navigates_history(self) -> None:
        """Test that Up arrow navigates to previous message."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        result = shortcuts.handle_key(event, "")
        assert result == {"action": "navigate", "text": "Second"}

    def test_up_arrow_multiple_times(self) -> None:
        """Test Up arrow multiple times."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")
        shortcuts.add_message("Third")

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        result1 = shortcuts.handle_key(event, "")
        assert result1["text"] == "Third"

        result2 = shortcuts.handle_key(event, "")
        assert result2["text"] == "Second"

        result3 = shortcuts.handle_key(event, "")
        assert result3["text"] == "First"

    def test_up_arrow_empty_history(self) -> None:
        """Test Up arrow with empty history."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        result = shortcuts.handle_key(event, "")
        assert result is None

    def test_up_arrow_wraparound(self) -> None:
        """Test Up arrow wraparound from oldest to newest."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        shortcuts.handle_key(event, "")  # Navigate to Second
        shortcuts.handle_key(event, "")  # Navigate to First
        result = shortcuts.handle_key(event, "")  # Wrap to Second
        assert result["text"] == "Second"


class TestKeyboardShortcutsDownArrow:
    """Test Down arrow navigation."""

    def test_down_arrow_navigates_forward(self) -> None:
        """Test that Down arrow navigates to next message."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        shortcuts.handle_key(event, "")  # Navigate to Second
        shortcuts.handle_key(event, "")  # Navigate to First

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        result = shortcuts.handle_key(event, "")
        assert result == {"action": "navigate", "text": "Second"}

    def test_down_arrow_to_most_recent(self) -> None:
        """Test Down arrow wraps to oldest when at most recent."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")

        event_up = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        shortcuts.handle_key(event_up, "")  # Navigate to Second

        event_down = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        result = shortcuts.handle_key(event_down, "")
        # With wraparound, down from most recent goes to oldest
        assert result == {"action": "navigate", "text": "First"}

    def test_down_arrow_empty_history(self) -> None:
        """Test Down arrow with empty history."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        result = shortcuts.handle_key(event, "")
        # Empty history returns None
        assert result is None

    def test_down_arrow_clears_input_at_most_recent(self) -> None:
        """Test that Down arrow wraps to oldest when at most recent."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("Message")

        event_up = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        shortcuts.handle_key(event_up, "")

        event_down = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        result = shortcuts.handle_key(event_down, "")
        # With wraparound, down from most recent goes to oldest
        assert result["text"] == "Message"


class TestKeyboardShortcutsAddMessage:
    """Test adding messages to history."""

    def test_add_message_stores_in_history(self) -> None:
        """Test that add_message stores in history."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("Test message")
        assert len(shortcuts.message_history) == 1

    def test_add_message_multiple(self) -> None:
        """Test adding multiple messages."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")
        shortcuts.add_message("Third")
        assert len(shortcuts.message_history) == 3

    def test_add_message_empty_ignored(self) -> None:
        """Test that empty messages are ignored."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("")
        shortcuts.add_message("   ")
        assert len(shortcuts.message_history) == 0


class TestKeyboardShortcutsFocus:
    """Test focus management."""

    def test_focus_sets_focus(self) -> None:
        """Test that focus() sets focus."""
        shortcuts = KeyboardShortcuts()
        shortcuts.focus()
        assert shortcuts.has_focus() is True

    def test_blur_removes_focus(self) -> None:
        """Test that blur() removes focus."""
        shortcuts = KeyboardShortcuts()
        shortcuts.focus()
        shortcuts.blur()
        assert shortcuts.has_focus() is False

    def test_has_focus_initial_state(self) -> None:
        """Test initial focus state."""
        shortcuts = KeyboardShortcuts()
        assert shortcuts.has_focus() is False


class TestKeyboardShortcutsIntegration:
    """Test integration scenarios."""

    def test_workflow_add_navigate_clear(self) -> None:
        """Test workflow: add message, navigate, clear."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("Message 1")
        shortcuts.add_message("Message 2")

        # Navigate up
        event_up = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        result = shortcuts.handle_key(event_up, "")
        assert result["text"] == "Message 2"

        # Clear
        event_clear = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event_clear, "")
        assert result == {"action": "clear"}

        # Navigate again should work
        result = shortcuts.handle_key(event_up, "")
        assert result["text"] == "Message 2"

    def test_workflow_focus_and_navigate(self) -> None:
        """Test workflow: focus and navigate."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("Message")

        # Focus
        event_focus = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event_focus, "")
        assert result == {"action": "focus"}
        assert shortcuts.has_focus() is True

        # Navigate
        event_up = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        result = shortcuts.handle_key(event_up, "")
        assert result["text"] == "Message"

    def test_multiple_shortcuts_in_sequence(self) -> None:
        """Test multiple shortcuts in sequence."""
        shortcuts = KeyboardShortcuts()
        shortcuts.add_message("First")
        shortcuts.add_message("Second")
        shortcuts.add_message("Third")

        # Navigate up three times
        event_up = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        shortcuts.handle_key(event_up, "")
        shortcuts.handle_key(event_up, "")
        result = shortcuts.handle_key(event_up, "")
        assert result["text"] == "First"

        # Clear
        event_clear = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=pygame.KMOD_CTRL)
        shortcuts.handle_key(event_clear, "")

        # Navigate again
        result = shortcuts.handle_key(event_up, "")
        assert result["text"] == "Third"


class TestKeyboardShortcutsEdgeCases:
    """Test edge cases."""

    def test_non_shortcut_keys_return_none(self) -> None:
        """Test that non-shortcut keys return None."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
        result = shortcuts.handle_key(event, "")
        assert result is None

    def test_ctrl_without_k_or_l(self) -> None:
        """Test Ctrl with other keys."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL)
        result = shortcuts.handle_key(event, "")
        assert result is None

    def test_k_without_ctrl(self) -> None:
        """Test K without Ctrl."""
        shortcuts = KeyboardShortcuts()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=0)
        result = shortcuts.handle_key(event, "")
        assert result is None

    def test_state_independence(self) -> None:
        """Test that multiple instances are independent."""
        shortcuts1 = KeyboardShortcuts()
        shortcuts2 = KeyboardShortcuts()

        shortcuts1.add_message("Message 1")
        shortcuts2.add_message("Message 2")

        assert len(shortcuts1.message_history) == 1
        assert len(shortcuts2.message_history) == 1

        event_up = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        result1 = shortcuts1.handle_key(event_up, "")
        result2 = shortcuts2.handle_key(event_up, "")

        assert result1["text"] == "Message 1"
        assert result2["text"] == "Message 2"
