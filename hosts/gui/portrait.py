"""Portrait panel — left-side agent avatar with crossfade on switch."""

from __future__ import annotations

import logging

import pygame
from PIL import Image as PILImage

from . import layout as gui_layout
from .constants import (
    DIM_WHITE,
    FONT_BANNER,
    FONT_NAME,
    FONT_TITLE,
    GOLD,
    GOLD_DIM,
    PANEL_BG,
    get_font_scale,
)
from .maidens import AGENTS, get_avatar_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Avatar loading — PIL → pygame Surface
# ---------------------------------------------------------------------------
def load_avatar(name: str, size: int = 256) -> pygame.Surface | None:
    """Load a golden avatar PNG as a pygame Surface, scaled to `size`."""
    path = get_avatar_path(name)
    if not path:
        logger.debug("Avatar path not found for: %s", name)
        return None
    try:
        logger.debug("Loading avatar from path: %s", path)
        img = PILImage.open(path).convert("RGBA")
        img = img.resize((size, size), PILImage.Resampling.LANCZOS)
        raw = img.tobytes()
        surf = pygame.image.frombytes(raw, (size, size), "RGBA").convert_alpha()
        logger.debug("Avatar loaded successfully for: %s", name)
        return surf
    except Exception as e:
        logger.error("Error loading avatar for %s: %s", name, e)
        return None


_AVATAR_CACHE: dict[str, pygame.Surface | None] = {}


def _get_avatar(name: str, size: int = 256) -> pygame.Surface | None:
    if name not in _AVATAR_CACHE:
        _AVATAR_CACHE[name] = load_avatar(name, size)
    return _AVATAR_CACHE[name]


class PortraitPanel:
    """Renders the active agent's portrait with crossfade on switch."""

    AVATAR_SIZE = 256
    FADE_MS = 350

    def __init__(self) -> None:
        self._current: str = "hephaestus"
        self._prev: str | None = None
        self._fade_t: float = 0.0  # 0.0 → fully faded (show current), 1.0 → at start of fade
        self._fading = False
        self.current_quote: str = ""

    def switch_to(self, name: str) -> None:
        if name == self._current or name not in AGENTS:
            return
        self._prev = self._current
        self._current = name
        self._fade_t = 1.0
        self._fading = True

    def update(self, dt: float) -> None:
        if self._fading:
            self._fade_t -= dt / (self.FADE_MS / 1000)
            if self._fade_t <= 0:
                self._fade_t = 0.0
                self._fading = False

    def draw(self, surf: pygame.Surface) -> None:
        screen_h = surf.get_height()
        lm = gui_layout.current_layout
        panel_rect = pygame.Rect(0, 0, lm.portrait_w, screen_h)

        # Panel background
        pygame.draw.rect(surf, PANEL_BG, panel_rect)
        pygame.draw.line(surf, GOLD_DIM, (lm.portrait_w, 0), (lm.portrait_w, screen_h), 1)

        cx = lm.portrait_w // 2
        avatar_y = 24
        avatar_size = self.AVATAR_SIZE

        # Gold circular frame behind avatar
        frame_cx, frame_cy = cx, avatar_y + avatar_size // 2
        frame_r = avatar_size // 2 + 6
        pygame.draw.circle(surf, GOLD_DIM, (frame_cx, frame_cy), frame_r, 2)
        # Glow rings
        frame_glow = pygame.Surface((frame_r * 2 + 20, frame_r * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(frame_glow, (*GOLD, 20), (frame_r + 10, frame_r + 10), frame_r + 4, 6)
        surf.blit(frame_glow, (frame_cx - frame_r - 10, frame_cy - frame_r - 10))

        def _blit_avatar(name: str, alpha: int) -> None:
            av = _get_avatar(name, avatar_size)
            if av is None:
                return
            av2 = av.copy()
            av2.set_alpha(alpha)
            # Clip to circle using a mask
            mask_surf = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            pygame.draw.circle(
                mask_surf,
                (255, 255, 255, 255),
                (avatar_size // 2, avatar_size // 2),
                avatar_size // 2,
            )
            masked = av2.copy()
            masked.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(masked, (cx - avatar_size // 2, avatar_y))

        if self._fading and self._prev:
            _blit_avatar(self._prev, int(self._fade_t * 255))
            _blit_avatar(self._current, int((1 - self._fade_t) * 255))
        else:
            _blit_avatar(self._current, 255)

        # Agent name + title (below portrait)
        info = AGENTS.get(self._current, {})
        name_y = avatar_y + avatar_size + 18
        agent_color = info.get("color", GOLD)

        FONT_NAME.render_to(
            surf,
            (cx - FONT_NAME.get_rect(self._current.upper()).width // 2, name_y),
            self._current.upper(),
            agent_color,
        )

        title = info.get("title", "")
        title_rect = FONT_TITLE.get_rect(title)
        FONT_TITLE.render_to(
            surf,
            (cx - title_rect.width // 2, name_y + 28),
            title,
            GOLD_DIM,
        )

        # Decorative separator
        sep_y = name_y + 54
        sep_w = 120
        pygame.draw.line(surf, GOLD_DIM, (cx - sep_w // 2, sep_y), (cx + sep_w // 2, sep_y), 1)

        # Quote at bottom of panel — pixel-measured wrap so lines stay
        # inside the portrait panel at any font scale (the old char-count
        # wrap overflowed the panel at higher zoom levels).
        if self.current_quote:
            max_quote_w = lm.portrait_w - 24
            line_h = max(14, int(18 * get_font_scale()))
            wrapped: list[str] = []
            current = ""
            for word in self.current_quote.split(" "):
                candidate = word if not current else f"{current} {word}"
                if FONT_BANNER.get_rect(candidate).width <= max_quote_w:
                    current = candidate
                else:
                    if current:
                        wrapped.append(current)
                    current = word
            if current:
                wrapped.append(current)
            q_y = sep_y + 12
            for line in wrapped[:6]:
                r = FONT_BANNER.get_rect(line)
                FONT_BANNER.render_to(
                    surf,
                    (cx - r.width // 2, q_y),
                    line,
                    DIM_WHITE,
                )
                q_y += line_h
