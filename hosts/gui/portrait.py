"""Portrait panel — left-side agent avatar with crossfade on switch."""

from __future__ import annotations

import textwrap

import pygame
from PIL import Image as PILImage

from .constants import DIALOGUE_H, FONT_BANNER, FONT_NAME, FONT_TITLE, PORTRAIT_W, theme
from .maidens import AGENTS, get_avatar_path


# ---------------------------------------------------------------------------
# Avatar loading — PIL → pygame Surface
# ---------------------------------------------------------------------------
def load_avatar(name: str, size: int = 256) -> pygame.Surface | None:
    """Load a golden avatar PNG as a pygame Surface, scaled to `size`."""
    path = get_avatar_path(name)
    if not path:
        return None
    try:
        img = PILImage.open(path).convert("RGBA")
        img = img.resize((size, size), PILImage.Resampling.LANCZOS)
        raw = img.tobytes()
        surf = pygame.image.frombytes(raw, (size, size), "RGBA").convert_alpha()
        return surf
    except Exception:
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

    def draw(self, surf: pygame.Surface, flash_alpha: int = 0) -> None:
        panel_rect = pygame.Rect(0, 0, PORTRAIT_W, DIALOGUE_H)

        # Panel background
        pygame.draw.rect(surf, theme.panel_bg, panel_rect)
        pygame.draw.line(surf, theme.gold_dim, (PORTRAIT_W, 0), (PORTRAIT_W, DIALOGUE_H), 1)

        cx = PORTRAIT_W // 2
        avatar_y = 24
        avatar_size = self.AVATAR_SIZE

        # Gold circular frame behind avatar
        frame_cx, frame_cy = cx, avatar_y + avatar_size // 2
        frame_r = avatar_size // 2 + 6
        pygame.draw.circle(surf, theme.gold_dim, (frame_cx, frame_cy), frame_r, 2)
        # Glow rings
        frame_glow = pygame.Surface((frame_r * 2 + 20, frame_r * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(
            frame_glow, (*theme.gold, 20), (frame_r + 10, frame_r + 10), frame_r + 4, 6
        )
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

        # Flash overlay on handoff (golden flash fading out)
        if flash_alpha > 0:
            flash_surf = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            pygame.draw.circle(
                flash_surf,
                (*theme.gold, flash_alpha),
                (avatar_size // 2, avatar_size // 2),
                avatar_size // 2,
            )
            surf.blit(flash_surf, (cx - avatar_size // 2, avatar_y))

        # Agent name + title (below portrait)
        info = AGENTS.get(self._current, {})
        name_y = avatar_y + avatar_size + 18
        agent_color = info.get("color", theme.gold)

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
            theme.gold_dim,
        )

        # Decorative separator
        sep_y = name_y + 54
        sep_w = 120
        pygame.draw.line(
            surf, theme.gold_dim, (cx - sep_w // 2, sep_y), (cx + sep_w // 2, sep_y), 1
        )

        # Quote at bottom of panel
        if self.current_quote:
            wrapped = textwrap.wrap(self.current_quote, width=28)
            q_y = sep_y + 12
            for line in wrapped[:6]:
                r = FONT_BANNER.get_rect(line)
                FONT_BANNER.render_to(
                    surf,
                    (cx - r.width // 2, q_y),
                    line,
                    theme.dim_white,
                )
                q_y += 18
