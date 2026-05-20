"""Shared layout, color palette, and font constants for the Kourai GUI.

All visual modules import their design tokens from here to keep
the theme centralized and DRY.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pygame.freetype

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
W, H = 1920, 1080  # Preferred window size defaults
# research(2026-05): 1080p is modal at 52.21% of Steam users (April 2026 survey);
# Ren'Py's modern GUI ships at 1280x720 OR 1920x1080 as designed targets. The
# LayoutMetrics in layout.py reflows from the live screen size, so any window
# size works — this is the *preferred* default for a fresh install.

# ---------------------------------------------------------------------------
# Color palette — deep black + molten gold (defaults)
# ---------------------------------------------------------------------------
BLACK = (5, 5, 5)
GOLD_GLOW = (241, 210, 161)  # #F1D2A1 — champagne highlight for embers/glow

# Default values — kept as constants for non-themed contexts (loading screen, etc.)
# Warm amber palette matches docs/stylesheets/variables.css tiers
# (gold-light #F1D2A1, gold-mid #C9944A, gold-dark #AA771C) so GUI, CLI,
# docs site, and poster share one canonical gold.
_DEFAULT_DARK_BG = (12, 10, 8)
_DEFAULT_PANEL_BG = (18, 14, 10)
_DEFAULT_GOLD = (201, 148, 74)  # #C9944A — warm amber (gold-mid)
_DEFAULT_GOLD_BRIGHT = (241, 210, 161)  # #F1D2A1 — champagne (gold-light)
_DEFAULT_GOLD_DIM = (170, 119, 28)  # #AA771C — bronze (gold-dark)
_DEFAULT_WHITE = (240, 235, 225)
_DEFAULT_DIM_WHITE = (160, 155, 145)
_DEFAULT_INPUT_BG = (20, 16, 12)
_DEFAULT_SCROLLBAR = (50, 40, 25)
_DEFAULT_ERROR_RED = (200, 80, 60)


class Theme:
    """Mutable color palette that propagates high-contrast changes to all modules.

    All drawing code should read colors from the singleton ``theme`` instance
    rather than module-level constants so that high-contrast toggles take
    effect everywhere immediately.
    """

    def __init__(self) -> None:
        self.dark_bg = _DEFAULT_DARK_BG
        self.panel_bg = _DEFAULT_PANEL_BG
        self.gold = _DEFAULT_GOLD
        self.gold_bright = _DEFAULT_GOLD_BRIGHT
        self.gold_dim = _DEFAULT_GOLD_DIM
        self.white = _DEFAULT_WHITE
        self.dim_white = _DEFAULT_DIM_WHITE
        self.input_bg = _DEFAULT_INPUT_BG
        self.scrollbar = _DEFAULT_SCROLLBAR
        self.error_red = _DEFAULT_ERROR_RED
        self._last_palette: dict[str, tuple[int, int, int]] | None = None

    def apply_palette(self, palette: dict[str, tuple[int, int, int]]) -> None:
        """Apply a palette dict (from HighContrastGUIIntegration) if it changed."""
        if palette == self._last_palette:
            return
        self._last_palette = dict(palette)
        self.dark_bg = palette.get("background", _DEFAULT_DARK_BG)
        self.panel_bg = palette.get("bubble_bg", _DEFAULT_PANEL_BG)
        self.gold = palette.get("gold", _DEFAULT_GOLD)
        self.gold_bright = palette.get("gold", _DEFAULT_GOLD_BRIGHT)
        self.gold_dim = palette.get("gold_dim", _DEFAULT_GOLD_DIM)
        self.white = palette.get("text", _DEFAULT_WHITE)
        self.dim_white = palette.get("scrollbar", _DEFAULT_DIM_WHITE)
        self.input_bg = palette.get("bubble_bg", _DEFAULT_INPUT_BG)
        self.scrollbar = palette.get("scrollbar", _DEFAULT_SCROLLBAR)
        self.error_red = palette.get("error_red", _DEFAULT_ERROR_RED)


theme = Theme()

# Legacy aliases — keep old names importable for loading_screen and other
# non-themed code that only runs once.  New drawing code should use ``theme.*``.
DARK_BG = _DEFAULT_DARK_BG
PANEL_BG = _DEFAULT_PANEL_BG
GOLD = _DEFAULT_GOLD
GOLD_BRIGHT = _DEFAULT_GOLD_BRIGHT
GOLD_DIM = _DEFAULT_GOLD_DIM
WHITE = _DEFAULT_WHITE
DIM_WHITE = _DEFAULT_DIM_WHITE
INPUT_BG = _DEFAULT_INPUT_BG
SCROLLBAR = _DEFAULT_SCROLLBAR
ERROR_RED = _DEFAULT_ERROR_RED


# ---------------------------------------------------------------------------
# Fonts — try system fonts, fall back to freetype defaults
# ---------------------------------------------------------------------------
def _ensure_freetype_ready() -> None:
    if not pygame.freetype.get_init():
        pygame.freetype.init()


def _create_font(names: list[str], size: int) -> pygame.freetype.Font:
    _ensure_freetype_ready()
    for name in names:
        path = pygame.freetype.match_font(name)
        if path:
            return pygame.freetype.Font(path, size)
    return pygame.freetype.SysFont("serif", size)


# ---------------------------------------------------------------------------
# Font scale — VSCode-style content zoom.
# ---------------------------------------------------------------------------
# FontProxy reads this multiplier when it creates its underlying
# pygame.freetype.Font, so every text-rendering path gets the font
# rasterised *at the target size* (not a post-scaled bitmap).  That's the
# difference between crisp zoomed text and the blurry-smoothscale trap.
#
# Update via ``set_font_scale(x)`` in this module — that invalidates every
# proxy so the next render rebuilds at the new size.  FontScaler lives in
# hosts/gui/font_scaler.py for persistence / clamping; this is the
# render-time reflection of its value.

_font_scale: float = 1.0
_font_proxy_registry: list[FontProxy] = []  # type: ignore[name-defined]  # defined below

# Components that cache rendered-text *surfaces* (DialogueHistory,
# message_history_integration, etc.) must be told when fonts change so they
# can bust their own caches — invalidating the underlying FontProxy isn't
# enough if a pre-rendered pygame.Surface still holds the old glyphs.
_font_scale_listeners: list[Callable[[], None]] = []


def get_font_scale() -> float:
    """Return the current font scale multiplier (1.0 = default)."""
    return _font_scale


def on_font_scale_change(callback: Callable[[], None]) -> None:
    """Register a callback (no args) to run after the font scale changes.

    Intended for dialogue-history / message-history widgets that cache
    rendered text to a pygame.Surface and need to mark themselves dirty.
    """
    _font_scale_listeners.append(callback)


def set_font_scale(scale: float) -> None:
    """Set the font scale, invalidate every FontProxy, notify listeners.

    Call after FontScaler.set_scale() in the event handler so the next
    frame rebuilds every cached pygame.freetype.Font at the new size AND
    every cached text surface is recomputed.
    """
    global _font_scale
    if abs(scale - _font_scale) < 0.001:
        return
    _font_scale = scale
    for proxy in _font_proxy_registry:
        proxy.invalidate()
    for cb in _font_scale_listeners:
        try:
            cb()
        except Exception:
            # Deliberately broad — a broken listener must not prevent other
            # caches from being busted.
            import logging as _logging

            _logging.getLogger(__name__).exception("font-scale listener failed")


def _scaled_size(base: int) -> int:
    """Apply the global font scale to a base point size, min 6."""
    return max(6, round(base * _font_scale))


class FontProxy:
    """Lazily recreate fonts after pygame.freetype quit/reinit cycles
    or whenever the global font scale changes."""

    def __init__(self, names: list[str], size: int) -> None:
        self._names = names
        self._size = size  # base (unscaled) point size
        self._rendered_size = 0  # scale actually baked into _font
        self._font: pygame.freetype.Font | None = None
        _font_proxy_registry.append(self)

    def invalidate(self) -> None:
        """Drop the cached font so the next access rebuilds at current scale."""
        self._font = None

    def _current_size(self) -> int:
        return _scaled_size(self._size)

    def _get_font(self) -> pygame.freetype.Font:
        target = self._current_size()
        if self._font is None or self._rendered_size != target:
            self._font = _create_font(self._names, target)
            self._rendered_size = target
        return self._font

    def _recreate_font(self) -> pygame.freetype.Font:
        target = self._current_size()
        self._font = _create_font(self._names, target)
        self._rendered_size = target
        return self._font

    def _call(self, method_name: str, *args: object, **kwargs: object) -> object:
        try:
            return getattr(self._get_font(), method_name)(*args, **kwargs)
        except (RuntimeError, pygame.error):
            return getattr(self._recreate_font(), method_name)(*args, **kwargs)

    @property
    def path(self) -> str | None:
        try:
            return self._get_font().path
        except (RuntimeError, pygame.error):
            return self._recreate_font().path

    def get_rect(self, *args: object, **kwargs: object) -> pygame.Rect:
        return self._call("get_rect", *args, **kwargs)  # type: ignore[return-value]

    def render_to(self, *args: object, **kwargs: object) -> pygame.Rect:
        return self._call("render_to", *args, **kwargs)  # type: ignore[return-value]

    def __getattr__(self, name: str) -> object:
        attr = getattr(self._get_font(), name)
        if callable(attr):
            return lambda *args, **kwargs: self._call(name, *args, **kwargs)
        return attr


FONT_BODY = FontProxy(["inter", "segoeui", "arial", "helvetica"], 16)
FONT_AGENT = FontProxy(["inter", "segoeui", "arial"], 13)
FONT_TITLE = FontProxy(["inter", "segoeui", "arial"], 11)
FONT_INPUT = FontProxy(["inter", "segoeui", "consolas", "monospace"], 16)
FONT_NAME = FontProxy(["inter", "segoeui", "arial"], 20)
FONT_BANNER = FontProxy(["inter", "segoeui", "arial"], 13)
