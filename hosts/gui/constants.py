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

# ---------------------------------------------------------------------------
# Color palette — deep black + molten gold
# ---------------------------------------------------------------------------
BLACK = (5, 5, 5)
DARK_BG = (12, 10, 8)
PANEL_BG = (18, 14, 10)
GOLD = (218, 165, 32)
GOLD_BRIGHT = (255, 215, 0)
GOLD_DIM = (140, 105, 20)
GOLD_GLOW = (255, 200, 60)
WHITE = (240, 235, 225)
DIM_WHITE = (160, 155, 145)
INPUT_BG = (20, 16, 12)
SCROLLBAR = (50, 40, 25)
ERROR_RED = (200, 80, 60)

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
