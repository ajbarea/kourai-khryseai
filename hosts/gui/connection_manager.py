"""Connection state management for the GUI.

Tracks connection state (connected, disconnected, reconnecting) and provides
status display and reconnection functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class ConnectionManager:
    def __init__(self, reconnect_callback: Callable[[], None] | None = None) -> None:
        """Initialize ConnectionManager.

        Args:
            reconnect_callback: Optional callback to invoke when reconnect is attempted.
        """
        self.connected = False
        self.reconnecting = False
        self.error_message = ""
        self._reconnect_callback = reconnect_callback
        self._agent_name = ""

    def handle_connected(self, name: str) -> None:
        """Handle successful connection.

        Args:
            name: Name of the connected agent.
        """
        self.connected = True
        self.reconnecting = False
        self.error_message = ""
        self._agent_name = name

    def handle_disconnected(self) -> None:
        """Handle disconnection."""
        self.connected = False
        self.reconnecting = False
        self.error_message = ""
        self._agent_name = ""

    def attempt_reconnect(self) -> None:
        """Attempt to reconnect."""
        if self.reconnecting:
            return

        self.reconnecting = True
        self.error_message = ""

        if self._reconnect_callback:
            self._reconnect_callback()

    def set_error(self, error_message: str) -> None:
        """Set error message when reconnection fails.

        Args:
            error_message: Error message to display.
        """
        self.reconnecting = False
        self.error_message = error_message

    def get_status_text(self) -> str:
        """Get status text for display.

        Returns:
            Status text describing current connection state.
        """
        if self.reconnecting:
            return "Reconnecting..."
        elif self.connected:
            return f"Connected: {self._agent_name}"
        elif self.error_message:
            return f"Error: {self.error_message}"
        else:
            return "Disconnected"

    def get_status_color(self) -> tuple[int, int, int]:
        """Get status color for display.

        Returns:
            RGB tuple for status color.
        """
        if self.reconnecting:
            # Yellow for reconnecting
            return (255, 200, 0)
        elif self.connected:
            # Green for connected
            return (0, 200, 0)
        elif self.error_message:
            # Red for error
            return (200, 0, 0)
        else:
            # Gray for disconnected
            return (128, 128, 128)

    def is_connected(self) -> bool:
        """Check if currently connected.

        Returns:
            True if connected, False otherwise.
        """
        return self.connected

    def is_reconnecting(self) -> bool:
        """Check if currently reconnecting.

        Returns:
            True if reconnecting, False otherwise.
        """
        return self.reconnecting

    def has_error(self) -> bool:
        """Check if there is an error message.

        Returns:
            True if error message is set, False otherwise.
        """
        return bool(self.error_message)
