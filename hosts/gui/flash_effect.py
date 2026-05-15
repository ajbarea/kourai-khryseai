"""Flash effect for agent-handoff visual indicator (200-500ms alpha fade)."""

from __future__ import annotations


class FlashEffect:
    """Alpha-fade flash (configurable 200-500ms) driven by delta time so animation
    speed is frame-rate independent.
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
        """Start the alpha-fade (150 -> 0) over `duration_ms` or the current setting."""
        self._timer = 0.0
        self.active = True

        if duration_ms is not None:
            # Clamp duration to valid range
            self.current_duration_ms = max(
                self.min_duration_ms, min(duration_ms, self.max_duration_ms)
            )

    def update(self, dt: float) -> tuple[bool, int]:
        """Advance by `dt` seconds and return (active, alpha 0-255)."""
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
        return not self.active

    def reset(self) -> None:
        """Stop the effect and clear all state."""
        self.active = False
        self._timer = 0.0
