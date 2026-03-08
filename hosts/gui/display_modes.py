"""Display-mode helpers for the Kourai GUI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import pygame

from .constants import H, W

logger = logging.getLogger(__name__)

DISPLAY_MODE_WINDOWED = "Windowed"
DISPLAY_MODE_BORDERLESS = "Borderless"
DISPLAY_MODE_FULLSCREEN = "Fullscreen"
DISPLAY_MODE_OPTIONS = [
    DISPLAY_MODE_WINDOWED,
    DISPLAY_MODE_BORDERLESS,
    DISPLAY_MODE_FULLSCREEN,
]

_PREFERRED_WINDOWED_SIZE = (1600, 900)
_MIN_WINDOWED_SIZE = (960, 540)


class SettingsLike(Protocol):
    """Settings manager contract used by the display helpers."""

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any) -> None: ...


@dataclass(frozen=True)
class DisplayModeSpec:
    """Resolved parameters for a concrete display mode."""

    mode: str
    size: tuple[int, int]
    flags: int
    position: tuple[int, int] | None = None


def normalize_display_mode(mode: str | None) -> str:
    """Return a supported display mode, falling back to windowed."""

    if mode in DISPLAY_MODE_OPTIONS:
        return mode
    if mode is not None:
        logger.debug("Unsupported display mode %r; falling back to %s", mode, DISPLAY_MODE_WINDOWED)
    return DISPLAY_MODE_WINDOWED


def get_primary_desktop_size() -> tuple[int, int]:
    """Return the current primary desktop size in pixels."""

    with_desktop_sizes = getattr(pygame.display, "get_desktop_sizes", None)
    if callable(with_desktop_sizes):
        for size in with_desktop_sizes():
            width, height = _sanitize_size(size)
            if width > 0 and height > 0:
                logger.debug(
                    "Resolved primary desktop size from pygame.display.get_desktop_sizes(): %sx%s",
                    width,
                    height,
                )
                return width, height

    info = pygame.display.Info()
    width = int(getattr(info, "current_w", 0) or W)
    height = int(getattr(info, "current_h", 0) or H)
    logger.debug("Resolved primary desktop size from pygame.display.Info(): %sx%s", width, height)
    return max(width, 1), max(height, 1)


def get_preferred_windowed_size(desktop_size: tuple[int, int]) -> tuple[int, int]:
    """Pick a modern default window size that fits the current desktop."""

    desktop_w, desktop_h = _sanitize_size(desktop_size)
    max_w = max(1, int(desktop_w * 0.85))
    max_h = max(1, int(desktop_h * 0.85))
    fitted = _fit_size_within(_PREFERRED_WINDOWED_SIZE, (max_w, max_h))
    preferred = clamp_windowed_size(fitted, (desktop_w, desktop_h))
    logger.debug(
        "Computed preferred windowed size %sx%s for desktop %sx%s",
        preferred[0],
        preferred[1],
        desktop_w,
        desktop_h,
    )
    return preferred


def get_saved_windowed_size(
    settings: SettingsLike, desktop_size: tuple[int, int] | None = None
) -> tuple[int, int]:
    """Load the saved windowed size, or derive a sensible default."""

    resolved_desktop = desktop_size or get_primary_desktop_size()
    width = settings.get("windowed_width")
    height = settings.get("windowed_height")

    if width is None or height is None:
        preferred = get_preferred_windowed_size(resolved_desktop)
        logger.debug(
            "No saved windowed size found; using preferred size %sx%s",
            preferred[0],
            preferred[1],
        )
        return preferred

    resolved = clamp_windowed_size((width, height), resolved_desktop)
    logger.debug(
        "Loaded saved windowed size %sx%s -> clamped to %sx%s",
        width,
        height,
        resolved[0],
        resolved[1],
    )
    return resolved


def save_windowed_size(settings: SettingsLike, size: tuple[int, int]) -> None:
    """Persist the last usable windowed size."""

    width, height = _sanitize_size(size)
    settings.set("windowed_width", width)
    settings.set("windowed_height", height)
    logger.debug("Saved windowed size %sx%s", width, height)


def clamp_windowed_size(size: tuple[int, int], desktop_size: tuple[int, int]) -> tuple[int, int]:
    """Clamp a windowed size so it remains usable on the current desktop."""

    width, height = _sanitize_size(size)
    desktop_w, desktop_h = _sanitize_size(desktop_size)
    min_w = min(_MIN_WINDOWED_SIZE[0], desktop_w)
    min_h = min(_MIN_WINDOWED_SIZE[1], desktop_h)

    return (
        max(min_w, min(width, desktop_w)),
        max(min_h, min(height, desktop_h)),
    )


def build_display_mode_spec(
    mode: str | None,
    windowed_size: tuple[int, int],
    desktop_size: tuple[int, int] | None = None,
) -> DisplayModeSpec:
    """Resolve the pygame mode arguments for the requested display mode."""

    normalized = normalize_display_mode(mode)
    resolved_desktop = desktop_size or get_primary_desktop_size()

    if normalized == DISPLAY_MODE_FULLSCREEN:
        spec = DisplayModeSpec(
            mode=normalized,
            size=_sanitize_size(resolved_desktop),
            flags=pygame.FULLSCREEN,
        )
        logger.debug("Built display mode spec: %s", spec)
        return spec

    if normalized == DISPLAY_MODE_BORDERLESS:
        spec = DisplayModeSpec(
            mode=normalized,
            size=_sanitize_size(resolved_desktop),
            flags=pygame.NOFRAME,
            position=(0, 0),
        )
        logger.debug("Built display mode spec: %s", spec)
        return spec

    resolved_windowed_size = clamp_windowed_size(windowed_size, resolved_desktop)
    spec = DisplayModeSpec(
        mode=normalized,
        size=resolved_windowed_size,
        flags=pygame.RESIZABLE,
        position=_center_window_position(resolved_windowed_size, resolved_desktop),
    )
    logger.debug("Built display mode spec: %s", spec)
    return spec


def _fit_size_within(preferred_size: tuple[int, int], bounds: tuple[int, int]) -> tuple[int, int]:
    preferred_w, preferred_h = _sanitize_size(preferred_size)
    bounds_w, bounds_h = _sanitize_size(bounds)
    scale = min(1.0, bounds_w / preferred_w, bounds_h / preferred_h)
    return (
        max(1, int(preferred_w * scale)),
        max(1, int(preferred_h * scale)),
    )


def _center_window_position(
    window_size: tuple[int, int], desktop_size: tuple[int, int]
) -> tuple[int, int]:
    window_w, window_h = _sanitize_size(window_size)
    desktop_w, desktop_h = _sanitize_size(desktop_size)
    return (
        max((desktop_w - window_w) // 2, 0),
        max((desktop_h - window_h) // 2, 0),
    )


def _sanitize_size(size: object) -> tuple[int, int]:
    try:
        width = int(size[0])  # type: ignore[index]
        height = int(size[1])  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        return W, H

    return max(width, 1), max(height, 1)
