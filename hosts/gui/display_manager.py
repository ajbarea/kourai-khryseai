"""Display manager — owns the pygame screen surface and mode transitions.

Encapsulates display mode switching, vsync negotiation, windowed size
tracking, and window positioning.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from .settings import SettingsManager

logger = logging.getLogger(__name__)


class DisplayManager:
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
    def _set_mode_with_vsync(
        size: tuple[int, int],
        flags: int,
        display: int | None = None,
    ) -> pygame.Surface:
        """Create the display surface, preferring vsync=1.

        ``display`` selects which monitor the mode binds to (pygame-ce 2.0+
        supports the kwarg; older builds are tolerated via TypeError
        fallback). ``None`` lets SDL pick, which usually means the window's
        current display or primary on first launch.
        """

        def _try(size_, flags_, **extra):
            try:
                return pygame.display.set_mode(size_, flags_, vsync=1, **extra)
            except TypeError:
                # Older pygame builds don't accept `display` — drop and retry.
                extra.pop("display", None)
                return pygame.display.set_mode(size_, flags_, vsync=1, **extra)

        kwargs: dict = {}
        if display is not None:
            kwargs["display"] = display

        try:
            surface = _try(size, flags, **kwargs)
            logger.debug(
                "Created display surface with vsync: %sx%s flags=%s display=%s actual=%sx%s",
                size[0],
                size[1],
                flags,
                display,
                surface.get_width(),
                surface.get_height(),
            )
            return surface
        except pygame.error as exc:
            logger.debug(
                "Vsync failed for %sx%s flags=%s display=%s; retrying without (%s)",
                size[0],
                size[1],
                flags,
                display,
                exc,
            )
            try:
                return pygame.display.set_mode(size, flags, **kwargs)
            except TypeError:
                kwargs.pop("display", None)
                return pygame.display.set_mode(size, flags, **kwargs)

    def _set_screen_mode(self, mode: str) -> pygame.Surface:
        spec = build_display_mode_spec(mode, self.windowed_size)
        logger.debug("Applying display mode request: %s", spec)

        try:
            surface = self._set_mode_with_vsync(spec.size, spec.flags, display=spec.display_index)
        except pygame.error as exc:
            if spec.mode != "Fullscreen":
                logger.exception("Failed to create display surface for mode %s", spec.mode)
                raise
            logger.debug(
                "Fullscreen %sx%s (display=%s) failed; retrying with auto desktop (%s)",
                spec.size[0],
                spec.size[1],
                spec.display_index,
                exc,
            )
            # Fall back to SDL's default size + display selection.
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
