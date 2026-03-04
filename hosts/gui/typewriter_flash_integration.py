"""Integration of FlashEffect with TypewriterManager for coordinated animations.

Manages pause/resume of typewriter effect during flash effect. Pauses typewriter
when flash starts and resumes when flash completes.
"""

from __future__ import annotations

from flash_effect import FlashEffect
from typewriter import TypewriterManager


class TypewriterFlashIntegration:
    """Coordinates typewriter and flash effects during agent handoff.

    Pauses the typewriter effect when a flash effect starts and resumes it
    when the flash completes. This prevents text animation from competing
    with the flash effect for visual attention.

    Attributes:
        typewriter: The TypewriterManager instance.
        flash_effect: The FlashEffect instance.
        enabled: Whether the integration is enabled.
    """

    def __init__(
        self,
        typewriter: TypewriterManager,
        flash_effect: FlashEffect,
        enabled: bool = True,
    ) -> None:
        """Initialize TypewriterFlashIntegration.

        Args:
            typewriter: The TypewriterManager instance to control.
            flash_effect: The FlashEffect instance to monitor.
            enabled: Whether the integration is enabled.
        """
        self.typewriter = typewriter
        self.flash_effect = flash_effect
        self.enabled = enabled
        self._was_paused_before_flash = False

    def on_flash_start(self) -> None:
        """Handle flash effect start by pausing typewriter.

        Called when a flash effect starts. Pauses the typewriter if it's
        currently active, saving the previous pause state.
        """
        if not self.enabled:
            return

        # Save the current pause state
        self._was_paused_before_flash = self.typewriter.paused

        # Pause the typewriter if it's active
        if self.typewriter.active and not self.typewriter.paused:
            self.typewriter.pause()

    def on_flash_complete(self) -> None:
        """Handle flash effect completion by resuming typewriter.

        Called when a flash effect completes. Resumes the typewriter if it
        was paused by the flash (not if it was already paused).
        """
        if not self.enabled:
            return

        # Resume the typewriter only if we paused it (not if it was already paused)
        if self.typewriter.active and not self._was_paused_before_flash:
            self.typewriter.resume()

    def update(self, dt: float) -> None:
        """Update integration state and manage pause/resume.

        Updates the flash effect and manages typewriter pause/resume based
        on the flash state.

        Args:
            dt: Delta time in seconds since last update.
        """
        if not self.enabled:
            return

        # Check if flash was active and is now complete
        was_active = not self.flash_effect.is_complete()
        active, _ = self.flash_effect.update(dt)
        is_now_complete = self.flash_effect.is_complete()

        # If flash just completed, resume typewriter
        if was_active and is_now_complete:
            self.on_flash_complete()

    def trigger_flash_with_pause(self, duration_ms: int | None = None) -> None:
        """Trigger flash effect and pause typewriter.

        Convenience method to trigger a flash effect and pause the typewriter
        in one call.

        Args:
            duration_ms: Optional duration in milliseconds for the flash effect.
        """
        if not self.enabled:
            return

        self.on_flash_start()
        self.flash_effect.trigger(duration_ms=duration_ms)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the integration.

        Args:
            enabled: Whether the integration should be enabled.
        """
        self.enabled = enabled

    def reset(self) -> None:
        """Reset the integration state.

        Resets the integration to initial state and resumes typewriter if paused.
        """
        if self.typewriter.active and not self._was_paused_before_flash:
            self.typewriter.resume()
        self._was_paused_before_flash = False
