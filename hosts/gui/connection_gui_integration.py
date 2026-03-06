"""Integration of ConnectionManager with the GUI.

Provides connection status display in the title bar and reconnect button functionality.
"""

from __future__ import annotations

import pygame
import pygame.freetype
from connection_manager import ConnectionManager


class ConnectionStatusDisplay:
    """Displays connection status in the title bar with reconnect button."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        """Initialize connection status display.

        Args:
            connection_manager: ConnectionManager instance to display status from.
        """
        self.manager = connection_manager
        self.reconnect_button_rect = pygame.Rect(0, 0, 0, 0)
        self._font: pygame.freetype.Font | None = None

    def set_font(self, font: pygame.freetype.Font) -> None:
        """Set the font for rendering status text.

        Args:
            font: pygame.freetype.Font instance to use for rendering.
        """
        self._font = font

    def update_button_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Update the position and size of the reconnect button.

        Args:
            x: X coordinate of button.
            y: Y coordinate of button.
            width: Width of button.
            height: Height of button.
        """
        self.reconnect_button_rect = pygame.Rect(x, y, width, height)

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on the status display area.

        Args:
            pos: Mouse position (x, y).

        Returns:
            True if reconnect button was clicked, False otherwise.
        """
        if (
            self.reconnect_button_rect.collidepoint(pos)
            and not self.manager.is_connected()
            and not self.manager.is_reconnecting()
        ):
            self.manager.attempt_reconnect()
            return True
        return False

    def draw(self, surf: pygame.Surface, x: int, y: int) -> None:
        """Draw connection status in the title bar.

        Args:
            surf: Surface to draw on.
            x: X coordinate for status text.
            y: Y coordinate for status text.
        """
        if not self._font:
            return

        status_text = self.manager.get_status_text()
        status_color = self.manager.get_status_color()

        # Draw status text
        self._font.render_to(surf, (x, y), status_text, status_color)

        # Draw reconnect button if disconnected or error
        if (
            not self.manager.is_connected()
            and not self.manager.is_reconnecting()
            and self.manager.has_error()
        ):
            self._draw_reconnect_button(surf)

    def _draw_reconnect_button(self, surf: pygame.Surface) -> None:
        """Draw the reconnect button.

        Args:
            surf: Surface to draw on.
        """
        if not self.reconnect_button_rect.width:
            return

        # Draw button background
        pygame.draw.rect(surf, (100, 50, 50), self.reconnect_button_rect)
        pygame.draw.rect(surf, (200, 100, 100), self.reconnect_button_rect, 1)

        # Draw button text
        if self._font:
            button_text = "Retry"
            text_rect = self._font.get_rect(button_text)
            text_x = (
                self.reconnect_button_rect.x
                + (self.reconnect_button_rect.width - text_rect.width) // 2
            )
            text_y = (
                self.reconnect_button_rect.y
                + (self.reconnect_button_rect.height - text_rect.height) // 2
            )
            self._font.render_to(surf, (text_x, text_y), button_text, (200, 100, 100))

    def get_status_text(self) -> str:
        """Get the current status text.

        Returns:
            Status text string.
        """
        return self.manager.get_status_text()

    def get_status_color(self) -> tuple[int, int, int]:
        """Get the current status color.

        Returns:
            RGB tuple for status color.
        """
        return self.manager.get_status_color()

    def is_showing_reconnect_button(self) -> bool:
        """Check if reconnect button should be shown.

        Returns:
            True if button should be shown, False otherwise.
        """
        return (
            not self.manager.is_connected()
            and not self.manager.is_reconnecting()
            and self.manager.has_error()
        )
