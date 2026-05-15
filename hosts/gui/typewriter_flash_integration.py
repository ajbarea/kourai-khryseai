"""Integration of FlashEffect with TypewriterManager for coordinated animations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .flash_effect import FlashEffect
    from .typewriter import TypewriterManager


class TypewriterFlashIntegration:
    """Pause typewriter during flash so text animation doesn't compete with the flash."""

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
        """Pause the typewriter, remembering the prior pause state so resume is conditional."""
        if not self.enabled:
            return

        # Save the current pause state
        self._was_paused_before_flash = self.typewriter.paused

        # Pause the typewriter if it's active
        if self.typewriter.active and not self.typewriter.paused:
            self.typewriter.pause()

    def on_flash_complete(self) -> None:
        """Resume the typewriter only if the flash paused it (not if it was already paused)."""
        if not self.enabled:
            return

        # Resume the typewriter only if we paused it (not if it was already paused)
        if self.typewriter.active and not self._was_paused_before_flash:
            self.typewriter.resume()

    def update(self, dt: float) -> None:
        """Advance flash state by `dt` seconds and resume typewriter on flash completion."""
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
