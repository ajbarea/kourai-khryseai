"""Shared layout, color palette, and font constants for the Kourai GUI.

All visual modules import their design tokens from here to keep
the theme centralized and DRY.
"""

from __future__ import annotations

import pygame.freetype

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
W, H = 1280, 720
PORTRAIT_W = 310
DIALOGUE_X = PORTRAIT_W + 8
DIALOGUE_W = W - PORTRAIT_W - 8
INPUT_H = 80
DIALOGUE_H = H - INPUT_H
BANNER_H = 32
BANNER_BORDER_H = 2
BANNER_TOTAL_H = BANNER_H + BANNER_BORDER_H  # 34 — top offset for dialogue area
SCROLL_CHROME_H = 60  # vertical chrome eaten by banner + padding in scroll math

# ---------------------------------------------------------------------------
# Color palette — deep black + molten gold (defaults)
# ---------------------------------------------------------------------------
BLACK = (5, 5, 5)
GOLD_GLOW = (255, 200, 60)

# Default values — kept as constants for non-themed contexts (loading screen, etc.)
_DEFAULT_DARK_BG = (12, 10, 8)
_DEFAULT_PANEL_BG = (18, 14, 10)
_DEFAULT_GOLD = (218, 165, 32)
_DEFAULT_GOLD_BRIGHT = (255, 215, 0)
_DEFAULT_GOLD_DIM = (140, 105, 20)
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
pygame.freetype.init()


def _load_font(names: list[str], size: int) -> pygame.freetype.Font:
    for name in names:
        path = pygame.freetype.match_font(name)
        if path:
            return pygame.freetype.Font(path, size)
    return pygame.freetype.SysFont("serif", size)


FONT_BODY = _load_font(["inter", "segoeui", "arial", "helvetica"], 16)
FONT_AGENT = _load_font(["inter", "segoeui", "arial"], 13)
FONT_TITLE = _load_font(["inter", "segoeui", "arial"], 11)
FONT_INPUT = _load_font(["inter", "segoeui", "consolas", "monospace"], 16)
FONT_NAME = _load_font(["inter", "segoeui", "arial"], 20)
FONT_BANNER = _load_font(["inter", "segoeui", "arial"], 13)
