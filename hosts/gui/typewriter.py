"""Typewriter effect manager for character-by-character text display.

Manages character-by-character text display with delta time for consistent
animation speed regardless of frame rate. Supports skip functionality,
speed settings (10ms to 100ms), pause/resume, and motion sensitivity.
"""

from __future__ import annotations


class TypewriterManager:
    """Manages character-by-character text display with delta time.

    Displays text one character at a time using delta time for consistent
    animation speed regardless of frame rate. Supports skip, pause/resume,
    and motion sensitivity settings.

    Attributes:
        min_speed_ms: Minimum speed in milliseconds per character (default 10).
        max_speed_ms: Maximum speed in milliseconds per character (default 100).
        current_speed_ms: Current speed setting in milliseconds per character.
        active: Whether the typewriter effect is currently active.
        paused: Whether the typewriter effect is currently paused.
        current_text: The full text being displayed.
        displayed_chars: Number of characters currently displayed.
        motion_sensitivity_enabled: Whether motion sensitivity is enabled.
    """

    def __init__(
        self,
        min_speed_ms: int = 10,
        max_speed_ms: int = 100,
        motion_sensitivity_enabled: bool = False,
    ) -> None:
        """Initialize TypewriterManager.

        Args:
            min_speed_ms: Minimum speed in milliseconds per character.
            max_speed_ms: Maximum speed in milliseconds per character.
            motion_sensitivity_enabled: Whether motion sensitivity is enabled.
        """
        self.min_speed_ms = min_speed_ms
        self.max_speed_ms = max_speed_ms
        self.current_speed_ms = 30  # Default speed
        self.active = False
        self.paused = False
        self.current_text = ""
        self.displayed_chars = 0
        self.motion_sensitivity_enabled = motion_sensitivity_enabled
        self._timer = 0.0  # Accumulated time in milliseconds
        self._skip_requested = False

    def start(self, text: str, speed_ms: int | None = None) -> None:
        """Start typewriter effect for text.

        Begins displaying the given text character-by-character using the
        specified speed or the current speed setting.

        Args:
            text: The text to display.
            speed_ms: Speed in milliseconds per character. If None, uses current_speed_ms.
        """
        self.current_text = text
        self.displayed_chars = 0
        self._timer = 0.0
        self._skip_requested = False
        self.paused = False
        self.active = True

        if speed_ms is not None:
            # Clamp speed to valid range
            self.current_speed_ms = max(self.min_speed_ms, min(speed_ms, self.max_speed_ms))

        # If motion sensitivity is enabled, skip the effect entirely
        if self.motion_sensitivity_enabled:
            self.displayed_chars = len(self.current_text)
            self.active = False

    def update(self, dt: float) -> str:
        """Update effect using delta time and return current displayed text.

        Advances the typewriter effect by the given delta time and returns
        the currently displayed text. Uses delta time for consistent animation
        speed regardless of frame rate.

        Args:
            dt: Delta time in seconds since last update.

        Returns:
            The currently displayed text (partial or full).
        """
        if not self.active or self.paused:
            return self.current_text[: self.displayed_chars]

        # Convert dt from seconds to milliseconds
        dt_ms = dt * 1000.0
        self._timer += dt_ms

        # Calculate how many characters should be displayed
        chars_to_display = int(self._timer / self.current_speed_ms)

        # Update displayed characters
        self.displayed_chars = min(chars_to_display, len(self.current_text))

        # Check if effect is complete
        if self.displayed_chars >= len(self.current_text):
            self.active = False
            self.displayed_chars = len(self.current_text)

        return self.current_text[: self.displayed_chars]

    def skip(self) -> None:
        """Skip to full text immediately.

        Immediately displays the full text and marks the effect as complete.
        """
        if self.active:
            self.displayed_chars = len(self.current_text)
            self.active = False
            self._skip_requested = True

    def is_complete(self) -> bool:
        """Check if effect has finished.

        Returns:
            True if the effect has finished displaying all characters, False otherwise.
        """
        return not self.active

    def pause(self) -> None:
        """Pause the effect.

        Pauses the typewriter effect without resetting progress. The effect
        can be resumed with resume().
        """
        if self.active:
            self.paused = True

    def resume(self) -> None:
        """Resume the effect.

        Resumes a paused typewriter effect from where it was paused.
        """
        if self.active and self.paused:
            self.paused = False

    def set_motion_sensitivity(self, enabled: bool) -> None:
        """Set motion sensitivity setting.

        When enabled, the typewriter effect is disabled and text is displayed
        immediately to accommodate users with motion sensitivity preferences.

        Args:
            enabled: Whether motion sensitivity is enabled.
        """
        self.motion_sensitivity_enabled = enabled

    def set_speed(self, speed_ms: int) -> None:
        """Set the typewriter speed.

        Sets the speed for new typewriter effects. The speed is clamped to
        the valid range [min_speed_ms, max_speed_ms].

        Args:
            speed_ms: Speed in milliseconds per character.
        """
        self.current_speed_ms = max(self.min_speed_ms, min(speed_ms, self.max_speed_ms))

    def get_displayed_text(self) -> str:
        """Get the currently displayed text.

        Returns:
            The text that should currently be displayed.
        """
        return self.current_text[: self.displayed_chars]

    def reset(self) -> None:
        """Reset the typewriter effect.

        Stops the effect and resets all state to initial values.
        """
        self.active = False
        self.paused = False
        self.current_text = ""
        self.displayed_chars = 0
        self._timer = 0.0
        self._skip_requested = False
