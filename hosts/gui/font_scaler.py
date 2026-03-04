"""Font scaling manager for Kourai Khryseai GUI.

Manages font scaling from 80% to 200% of default size. Provides methods to
scale fonts and adjust scroll positions when scale changes.
"""

from __future__ import annotations

import pygame.freetype


class FontScaler:
    """Manages font scaling from 80% to 200% of default size.

    Provides methods to set the scale factor, scale fonts, and adjust scroll
    positions when the scale changes. Clamps scale values to the valid range.
    """

    def __init__(self, min_scale: float = 0.8, max_scale: float = 2.0) -> None:
        """Initialize FontScaler with scale range.

        Args:
            min_scale: Minimum scale factor (default 0.8 for 80%).
            max_scale: Maximum scale factor (default 2.0 for 200%).
        """
        self.min_scale = min_scale
        self.max_scale = max_scale
        self.scale = 1.0  # Default 100%

    def set_scale(self, scale: float) -> None:
        """Set font scale factor.

        Clamps the scale to the valid range [min_scale, max_scale].

        Args:
            scale: Scale factor to set (e.g., 1.0 for 100%, 1.5 for 150%).
        """
        self.scale = max(self.min_scale, min(scale, self.max_scale))

    def scale_font(self, font: pygame.freetype.Font, base_size: int) -> pygame.freetype.Font:
        """Get a scaled font.

        Creates a new font with the size scaled by the current scale factor.

        Args:
            font: The base font to scale.
            base_size: The base font size in pixels.

        Returns:
            A new font object with the scaled size.
        """
        scaled_size = int(base_size * self.scale)
        return pygame.freetype.Font(font.path, scaled_size)

    def adjust_scroll(self, current_scroll: int, old_scale: float, new_scale: float) -> int:
        """Adjust scroll position when scale changes.

        When font scale changes, adjusts the scroll position to maintain
        the approximate view position. Uses proportional scaling to keep
        the same relative position in the content.

        Args:
            current_scroll: Current scroll position in pixels.
            old_scale: Previous scale factor.
            new_scale: New scale factor.

        Returns:
            Adjusted scroll position.
        """
        if old_scale == 0:
            return current_scroll

        # Scale the scroll position proportionally
        adjusted_scroll = int(current_scroll * (new_scale / old_scale))
        return adjusted_scroll
