"""Integration of FlashEffect with PortraitPanel for agent handoff visual indicator.

Manages flash effect on portrait panel during agent handoff. Triggers flash
when agent switches and applies alpha blending to portrait during flash.
"""

from __future__ import annotations

from .flash_effect import FlashEffect


class PortraitFlashIntegration:
    """Integrates flash effect with portrait panel during agent handoff.

    Triggers flash effect when agent handoff is detected and applies alpha
    blending to the portrait during the flash. Coordinates with PortraitPanel
    to provide visual feedback for agent switches.

    Attributes:
        flash_effect: The FlashEffect instance managing the flash animation.
        enabled: Whether the flash effect is enabled.
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize PortraitFlashIntegration.

        Args:
            enabled: Whether the flash effect is enabled.
        """
        self.flash_effect = FlashEffect()
        self.enabled = enabled
        self._last_agent: str | None = None

    def on_agent_switch(self, new_agent: str, duration_ms: int | None = None) -> None:
        """Handle agent handoff by triggering flash effect.

        Called when the portrait panel switches to a new agent. Triggers the
        flash effect with the specified duration or default.

        Args:
            new_agent: The name of the new agent.
            duration_ms: Optional duration in milliseconds for the flash effect.
        """
        if not self.enabled:
            return

        self._last_agent = new_agent
        self.flash_effect.trigger(duration_ms=duration_ms)

    def update(self, dt: float) -> tuple[bool, int]:
        """Update flash effect and return current state.

        Updates the flash effect with delta time and returns the current
        active state and alpha value for portrait highlighting.

        Args:
            dt: Delta time in seconds since last update.

        Returns:
            Tuple of (active, alpha) where:
            - active: Whether the flash effect is still active
            - alpha: Current alpha value (0-255) for portrait highlighting
        """
        return self.flash_effect.update(dt)

    def get_flash_alpha(self) -> int:
        """Get current flash alpha value for portrait highlighting.

        Returns the current alpha value from the flash effect, which can be
        used to apply alpha blending to the portrait during the flash.

        Returns:
            Alpha value (0-255) for portrait highlighting.
        """
        active, alpha = self.flash_effect.update(0.0)
        return alpha

    def is_active(self) -> bool:
        """Check if flash effect is currently active.

        Returns:
            True if the flash effect is active, False otherwise.
        """
        return not self.flash_effect.is_complete()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the flash effect.

        Args:
            enabled: Whether the flash effect should be enabled.
        """
        self.enabled = enabled
        if not enabled:
            self.flash_effect.reset()

    def reset(self) -> None:
        """Reset the flash effect.

        Stops the effect and resets all state to initial values.
        """
        self.flash_effect.reset()
        self._last_agent = None
