"""Keyboard shortcuts for InputBar.

Implements WCAG 2.2 SC 2.1.1 (Keyboard) compliance.
"""

import pygame
from message_history import MessageHistory


class KeyboardShortcuts:
    """Manages keyboard shortcuts for the InputBar.

    Handles:
    - Ctrl+K: Focus the input bar
    - Ctrl+L: Clear the input bar
    - Up/Down arrows: Navigate message history
    """

    def __init__(self) -> None:
        """Initialize keyboard shortcuts manager."""
        self.message_history = MessageHistory()
        self._has_focus = False

    def handle_key(self, event: pygame.event.Event, current_text: str) -> dict | None:
        """Handle keyboard shortcuts.

        Args:
            event: The pygame KEYDOWN event
            current_text: The current text in the input bar

        Returns:
            A dict with action information, or None if no action
            Possible actions:
            - {"action": "focus"}: Focus the input bar
            - {"action": "clear"}: Clear the input bar
            - {"action": "navigate", "text": str}: Navigate history and set text
            - {"action": "submit", "text": str}: Submit the current text
        """
        # Get mod safely (may not exist in all event types)
        mod = getattr(event, "mod", 0)

        # Ctrl+K: Focus the input bar
        if event.key == pygame.K_k and mod & pygame.KMOD_CTRL:
            self._has_focus = True
            return {"action": "focus"}

        # Ctrl+L: Clear the input bar
        if event.key == pygame.K_l and mod & pygame.KMOD_CTRL:
            self.message_history.reset()
            return {"action": "clear"}

        # Up/Down arrows: Navigate message history
        if event.key == pygame.K_UP:
            message = self.message_history.navigate(-1)
            if message is not None:
                return {"action": "navigate", "text": message}
            return None

        if event.key == pygame.K_DOWN:
            message = self.message_history.navigate(1)
            if message is not None:
                return {"action": "navigate", "text": message}
            return None

        return None

    def add_message(self, message: str) -> None:
        """Add a message to history.

        Args:
            message: The message text to add
        """
        self.message_history.add(message)

    def focus(self) -> None:
        """Set focus to the input bar."""
        self._has_focus = True

    def blur(self) -> None:
        """Remove focus from the input bar."""
        self._has_focus = False

    def has_focus(self) -> bool:
        """Check if the input bar has focus.

        Returns:
            True if focused, False otherwise
        """
        return self._has_focus
