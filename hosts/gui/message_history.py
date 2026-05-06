"""Message history navigation for InputBar."""

from collections import deque


class MessageHistory:
    """Manages message history with navigation support.

    Stores up to 20 previous messages and provides navigation through them
    with wraparound behavior.
    """

    def __init__(self, max_size: int = 20) -> None:
        """Initialize message history.

        Args:
            max_size: Maximum number of messages to store (default 20)
        """
        self._messages: deque[str] = deque(maxlen=max_size)
        self._index = -1

    def add(self, message: str) -> None:
        """Add a message to history.

        Args:
            message: The message text to add
        """
        if message.strip():
            self._messages.append(message)
            self.reset()

    def navigate(self, direction: int) -> str | None:
        """Navigate through message history.

        Args:
            direction: 1 for next (down), -1 for previous (up)

        Returns:
            The message at the new position, or None if history is empty
        """
        if not self._messages:
            return None

        # If we're at the "current" position (index -1), start from the end
        if self._index == -1:
            if direction == -1:  # Up arrow
                self._index = len(self._messages) - 1
            else:  # Down arrow - wrap to oldest
                self._index = 0
        else:
            # Move in the specified direction
            self._index += direction

            # Wraparound behavior: wrap around at boundaries
            if self._index < 0:
                # Wrap from oldest to newest
                self._index = len(self._messages) - 1
            elif self._index >= len(self._messages):
                # Wrap from newest to oldest
                self._index = 0

        return self._messages[self._index]

    def reset(self) -> None:
        """Reset to the most recent position (no message selected)."""
        self._index = -1

    def get_current(self) -> str | None:
        """Get the current message without navigating.

        Returns:
            The current message, or None if at the most recent position
        """
        if self._index == -1 or self._index >= len(self._messages):
            return None
        return self._messages[self._index]

    def __len__(self) -> int:
        """Return the number of messages in history."""
        return len(self._messages)
