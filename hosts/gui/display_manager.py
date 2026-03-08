"""Display manager — owns the pygame screen surface and mode transitions.

Encapsulates display mode switching, vsync negotiation, windowed size
tracking, and window positioning. Extracted from __main__.py to keep
the main loop thin.
"""

from __future__ import annotations

import contextlib
import logging

import pygame

from .display_modes import (
    DISPLAY_MODE_WINDOWED,
    build_display_mode_spec,
    clamp_windowed_size,
    get_primary_desktop_size,
    get_saved_windowed_size,
    normalize_display_mode,
    save_windowed_size,
)
from .settings import SettingsManager

logger = logging.getLogger(__name__)


class DisplayManager:
    """Manages the pygame display surface, mode, and windowed size."""

    def __init__(self, settings: SettingsManager) -> None:
        self.mode = normalize_display_mode(settings.get("display_mode", DISPLAY_MODE_WINDOWED))
        self.windowed_size = get_saved_windowed_size(settings)
        self.screen = self._set_screen_mode(self.mode)

        logger.debug(
            "DisplayManager initialized: mode=%s windowed_size=%sx%s",
            self.mode,
            self.windowed_size[0],
            self.windowed_size[1],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_mode(self, mode: str, settings: SettingsManager) -> None:
        """Switch to a new display mode, saving the old windowed size."""
        normalized = normalize_display_mode(mode)
        logger.debug("Display mode change requested: %s -> %s", self.mode, normalized)

        if self.mode == DISPLAY_MODE_WINDOWED:
            self.windowed_size = clamp_windowed_size(
                self.screen.get_size(), get_primary_desktop_size()
            )
            save_windowed_size(settings, self.windowed_size)

        self.mode = normalized
        settings.set("display_mode", self.mode)
        self.screen = self._set_screen_mode(self.mode)

    def handle_resize(
        self, event: pygame.event.Event, settings: SettingsManager | None = None
    ) -> tuple[int, int]:
        """Process a resize event, return the new (w, h).

        Args:
            event: The pygame resize event.
            settings: If provided, persist the new windowed size immediately
                so it survives a crash.
        """
        if hasattr(event, "size"):
            w, h = event.size
        elif hasattr(event, "x") and hasattr(event, "y"):
            w, h = event.x, event.y
        else:
            w, h = self.screen.get_size()

        logger.debug(
            "Received window resize event %s with size %sx%s",
            event.type,
            w,
            h,
        )

        if self.mode == DISPLAY_MODE_WINDOWED:
            self.windowed_size = clamp_windowed_size((w, h), get_primary_desktop_size())
            # Re-create the surface so pygame has the correct buffer size
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            if settings is not None:
                save_windowed_size(settings, self.windowed_size)
            logger.debug(
                "Updated windowed surface to %sx%s",
                self.windowed_size[0],
                self.windowed_size[1],
            )

        return self.screen.get_size()

    def save_state(self, settings: SettingsManager) -> None:
        """Persist current display state to settings (called on shutdown)."""
        if self.mode == DISPLAY_MODE_WINDOWED:
            self.windowed_size = clamp_windowed_size(
                self.screen.get_size(), get_primary_desktop_size()
            )
        save_windowed_size(settings, self.windowed_size)
        settings.set("display_mode", self.mode)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_window_position(position: tuple[int, int] | None) -> None:
        if position is None:
            return
        with contextlib.suppress(Exception):
            pygame.display.set_window_position(position)
            logger.debug("Set window position to x=%s y=%s", position[0], position[1])

    @staticmethod
    def _set_mode_with_vsync(size: tuple[int, int], flags: int) -> pygame.Surface:
        try:
            surface = pygame.display.set_mode(size, flags, vsync=1)
            logger.debug(
                "Created display surface with vsync: %sx%s flags=%s actual=%sx%s",
                size[0],
                size[1],
                flags,
                surface.get_width(),
                surface.get_height(),
            )
            return surface
        except pygame.error as exc:
            logger.debug(
                "Vsync failed for %sx%s flags=%s; retrying without (%s)",
                size[0],
                size[1],
                flags,
                exc,
            )
            return pygame.display.set_mode(size, flags)

    def _set_screen_mode(self, mode: str) -> pygame.Surface:
        spec = build_display_mode_spec(mode, self.windowed_size)
        logger.debug("Applying display mode request: %s", spec)

        try:
            surface = self._set_mode_with_vsync(spec.size, spec.flags)
        except pygame.error as exc:
            if spec.mode != "Fullscreen":
                logger.exception("Failed to create display surface for mode %s", spec.mode)
                raise
            logger.debug(
                "Fullscreen %sx%s failed; retrying with auto desktop (%s)",
                spec.size[0],
                spec.size[1],
                exc,
            )
            surface = self._set_mode_with_vsync((0, 0), spec.flags)

        self._set_window_position(spec.position)

        if spec.mode == DISPLAY_MODE_WINDOWED:
            self.windowed_size = surface.get_size()
            logger.debug(
                "Windowed mode; captured size %sx%s",
                self.windowed_size[0],
                self.windowed_size[1],
            )

        logger.debug(
            "Display mode %s applied: %sx%s",
            spec.mode,
            surface.get_width(),
            surface.get_height(),
        )
        return surface
