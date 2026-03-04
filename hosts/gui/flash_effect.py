"""Flash effect manager for agent handoff visual indicator.

Manages flash effect on portrait panel during agent handoff. Provides
configurable duration (200-500ms) with alpha fade animation from 150 to 0.
"""

from __future__ import annotations


class FlashEffect:
    """Manages agent handoff flash effect on portrait panel.

    Displays a flash effect with alpha fade animation when agents hand off.
    Supports configurable duration between 200ms and 500ms. Uses delta time
    for consistent animation speed regardless of frame rate.

    Attributes:
        min_duration_ms: Minimum duration in milliseconds (default 200).
        max_duration_ms: Maximum duration in milliseconds (default 500).
        current_duration_ms: Current duration setting in milliseconds.
        active: Whether the flash effect is currently active.
    """

    def __init__(
        self,
        min_duration_ms: int = 200,
        max_duration_ms: int = 500,
    ) -> None:
        """Initialize FlashEffect.

        Args:
            min_duration_ms: Minimum duration in milliseconds.
            max_duration_ms: Maximum duration in milliseconds.
        """
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.current_duration_ms = 350  # Default duration
        self.active = False
        self._timer = 0.0  # Accumulated time in milliseconds
        self._start_alpha = 150
        self._end_alpha = 0

    def trigger(self, duration_ms: int | None = None) -> None:
        """Trigger flash effect.

        Begins the flash effect with the specified duration or the current
        duration setting. The effect will fade alpha from 150 to 0 over the
        specified duration.

        Args:
            duration_ms: Duration in milliseconds. If None, uses current_duration_ms.
        """
        self._timer = 0.0
        self.active = True

        if duration_ms is not None:
            # Clamp duration to valid range
            self.current_duration_ms = max(
                self.min_duration_ms, min(duration_ms, self.max_duration_ms)
            )

    def update(self, dt: float) -> tuple[bool, int]:
        """Update effect and return (active, alpha).

        Advances the flash effect by the given delta time and returns the
        current active state and alpha value. Uses delta time for consistent
        animation speed regardless of frame rate.

        Args:
            dt: Delta time in seconds since last update.

        Returns:
            Tuple of (active, alpha) where:
            - active: Whether the effect is still active
            - alpha: Current alpha value (0-255)
        """
        if not self.active:
            return (False, 0)

        # Convert dt from seconds to milliseconds
        dt_ms = dt * 1000.0
        self._timer += dt_ms

        # Calculate progress (0.0 to 1.0)
        progress = min(self._timer / self.current_duration_ms, 1.0)

        # Calculate alpha using linear interpolation
        alpha = int(self._start_alpha + (self._end_alpha - self._start_alpha) * progress)

        # Check if effect is complete
        if progress >= 1.0:
            self.active = False
            alpha = self._end_alpha

        return (self.active, alpha)

    def is_complete(self) -> bool:
        """Check if effect has finished.

        Returns:
            True if the effect has finished, False otherwise.
        """
        return not self.active

    def reset(self) -> None:
        """Reset the flash effect.

        Stops the effect and resets all state to initial values.
        """
        self.active = False
        self._timer = 0.0
