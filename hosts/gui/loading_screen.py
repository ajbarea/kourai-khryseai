"""Cinematic title screen — generator-based loading with studio splash.

Uses the **generator method** (modern Pygame-CE best practice) to keep the
event pump alive during initialization.  The main loop calls ``next()`` on
the loading generator each frame while rendering a multi-phase cinematic:

Flow:
  1. Black screen → "ajsoftworks presents" fades in → holds → fades out
  2. "an agentic AI experience" fades in → holds → fades out
  3. Golden-maidens splash art fades in from black over ~2.5s
  4. Title "Κοῦραι Χρύσεαι" and subtitle appear
  5. "Press any key" pulses once all assets are loaded
  6. Any key / click → fade-to-black → return True to caller

Generator loading runs underneath throughout all phases.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pygame.freetype
from PIL import Image as PILImage

from .constants import DARK_BG, GOLD, GOLD_BRIGHT, GOLD_DIM

if TYPE_CHECKING:
    from collections.abc import Generator

# Path to the splash image
_SPLASH_IMAGE = Path(__file__).resolve().parents[2] / "docs" / "assets" / "golden-maidens.png"

# Timing constants (seconds)
_CARD_FADE_IN = 1.2
_CARD_HOLD = 1.5
_CARD_FADE_OUT = 0.8
_CARD_GAP = 0.4
_IMAGE_FADE_SECS = 2.5
_FADE_OUT_SPEED = 600  # alpha units per second

# Cinematic phases
PHASE_CARD_1 = 0  # "ajsoftworks presents"
PHASE_CARD_2 = 1  # "an agentic AI experience"
PHASE_SPLASH = 2  # Golden maidens fade-in + title
PHASE_READY = 3  # "Press any key" (waiting for input)
PHASE_FADE_OUT = 4  # Fade to black → done


# ---------------------------------------------------------------------------
# Lightweight ember particles for the title screen
# ---------------------------------------------------------------------------


class _LoadingEmber:
    """Single golden ember drifting upward."""

    __slots__ = ("alpha", "color", "decay", "radius", "vx", "vy", "x", "y")

    def __init__(self, max_w: int, max_h: int) -> None:
        self._reset(max_w, max_h)

    def _reset(self, max_w: int, max_h: int) -> None:
        self.x = random.uniform(0, max_w)  # noqa: S311
        self.y = random.uniform(0, max_h)  # noqa: S311
        self.vx = random.uniform(-0.2, 0.2)  # noqa: S311
        self.vy = random.uniform(-0.5, -0.1)  # noqa: S311
        self.radius = random.uniform(1.0, 2.2)  # noqa: S311
        self.alpha = random.uniform(40, 150)  # noqa: S311
        self.decay = random.uniform(0.12, 0.4)  # noqa: S311
        r = random.randint(200, 255)  # noqa: S311
        g = random.randint(140, 200)  # noqa: S311
        self.color = (r, g, 20)

    def update(self, dt: float, max_w: int, max_h: int) -> None:
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.alpha -= self.decay * dt * 60
        if self.alpha <= 0:
            self._reset(max_w, max_h)

    def draw(self, surf: pygame.Surface) -> None:
        if self.alpha <= 0:
            return
        size = int(self.radius * 2 + 2)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(
            s,
            (*self.color, int(self.alpha)),
            (size // 2, size // 2),
            max(1, int(self.radius)),
        )
        surf.blit(s, (int(self.x - self.radius), int(self.y - self.radius)))


# ---------------------------------------------------------------------------
# Splash image loader
# ---------------------------------------------------------------------------


def _load_splash(screen_w: int, screen_h: int) -> pygame.Surface | None:
    """Load and scale the golden-maidens splash image to fit the screen."""
    if not _SPLASH_IMAGE.exists():
        return None
    try:
        img = PILImage.open(_SPLASH_IMAGE).convert("RGBA")
        iw, ih = img.size
        # Scale to ~70% of screen height, preserving aspect ratio
        target_h = int(screen_h * 0.70)
        scale = target_h / ih
        target_w = int(iw * scale)
        if target_w > int(screen_w * 0.85):
            target_w = int(screen_w * 0.85)
            scale = target_w / iw
            target_h = int(ih * scale)
        img = img.resize((target_w, target_h), PILImage.Resampling.LANCZOS)
        raw = img.tobytes()
        return pygame.image.frombytes(raw, (target_w, target_h), "RGBA").convert_alpha()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pre-rendered vignette (cached per size to avoid per-frame allocation)
# ---------------------------------------------------------------------------

_vignette_cache: dict[tuple[int, int], pygame.Surface] = {}


def _get_vignette(w: int, h: int) -> pygame.Surface:
    """Return a cached vignette overlay for the given dimensions."""
    key = (w, h)
    if key not in _vignette_cache:
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)
        band_h = h // 4
        for i in range(band_h):
            alpha = int(80 * (1 - i / band_h))
            pygame.draw.line(vignette, (0, 0, 0, alpha), (0, i), (w, i))
            pygame.draw.line(vignette, (0, 0, 0, alpha), (0, h - 1 - i), (w, h - 1 - i))
        _vignette_cache[key] = vignette
    return _vignette_cache[key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_loading_screen(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    load_generator: Generator[tuple[float, str], None, None],
) -> bool:
    """Run the cinematic title/loading screen.

    The generator is advanced once per frame throughout all cinematic phases.
    Once the generator is exhausted AND the splash is visible, the "press
    any key" prompt appears.

    Args:
        screen: The pygame display surface.
        clock: The pygame Clock for frame timing.
        load_generator: Yields ``(progress, description)`` where *progress*
            is 0.0–1.0.

    Returns:
        ``True`` if loading completed and the user pressed a key.
        ``False`` if the user closed the window.
    """
    screen_w, screen_h = screen.get_size()

    # --- Pre-render assets ---
    splash = _load_splash(screen_w, screen_h)
    embers = [_LoadingEmber(screen_w, screen_h) for _ in range(60)]
    vignette = _get_vignette(screen_w, screen_h)

    card_font = pygame.freetype.SysFont("inter,segoeui,arial", 22)
    card_font_small = pygame.freetype.SysFont("inter,segoeui,arial", 16)
    title_font = pygame.freetype.SysFont("inter,segoeui,arial", 24)
    prompt_font = pygame.freetype.SysFont("inter,segoeui,arial", 15)
    subtitle_font = pygame.freetype.SysFont("inter,segoeui,arial", 12)

    # --- State ---
    phase = PHASE_CARD_1
    phase_elapsed = 0.0
    total_elapsed = 0.0
    loading_done = False
    fade_alpha = 0  # Fade-to-black overlay on keypress
    image_alpha = 0  # Splash image opacity (0–255)
    skip_cards = False  # True if user presses key during cards

    # Flush accumulated delta from asset loading so the first frame's dt is near-zero
    clock.tick()

    while True:
        dt = clock.tick(60) / 1000.0
        phase_elapsed += dt
        total_elapsed += dt

        # --- Events ---
        pressed_key = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and not loading_done:
                    return False
                pressed_key = True
            if event.type == pygame.MOUSEBUTTONDOWN:
                pressed_key = True

        # --- Advance loading generator (always, regardless of phase) ---
        if not loading_done:
            try:
                _progress, _status = next(load_generator)
            except StopIteration:
                loading_done = True

        # --- Phase transitions ---
        card_duration = _CARD_FADE_IN + _CARD_HOLD + _CARD_FADE_OUT

        if phase == PHASE_CARD_1:
            # Skip cards on keypress
            if pressed_key:
                skip_cards = True
            if phase_elapsed >= card_duration + _CARD_GAP or skip_cards:
                phase = PHASE_CARD_2
                phase_elapsed = 0.0
                if skip_cards:
                    phase_elapsed = card_duration  # Instant skip

        elif phase == PHASE_CARD_2:
            if pressed_key:
                skip_cards = True
            if phase_elapsed >= card_duration + _CARD_GAP or skip_cards:
                phase = PHASE_SPLASH
                phase_elapsed = 0.0

        elif phase == PHASE_SPLASH:
            image_alpha = min(255, int(255 * (phase_elapsed / _IMAGE_FADE_SECS)))
            if loading_done and image_alpha >= 255:
                phase = PHASE_READY
                phase_elapsed = 0.0

        elif phase == PHASE_READY:
            image_alpha = 255
            if pressed_key:
                phase = PHASE_FADE_OUT
                phase_elapsed = 0.0

        elif phase == PHASE_FADE_OUT:
            fade_alpha = min(fade_alpha + int(_FADE_OUT_SPEED * dt), 255)
            if fade_alpha >= 255:
                return True

        # --- Update particles ---
        for e in embers:
            e.update(dt, screen_w, screen_h)

        # --- Draw ---
        screen.fill(DARK_BG)

        # Particles always visible (subtle background life)
        for e in embers:
            e.draw(screen)

        # Phase-specific rendering
        if phase == PHASE_CARD_1:
            _draw_text_card(
                screen,
                screen_w,
                screen_h,
                phase_elapsed,
                card_font,
                "ajsoftworks",
                "presents",
                card_font_small,
            )

        elif phase == PHASE_CARD_2:
            _draw_text_card(
                screen,
                screen_w,
                screen_h,
                phase_elapsed,
                card_font_small,
                "an agentic AI experience",
                None,
                None,
            )

        elif phase in (PHASE_SPLASH, PHASE_READY, PHASE_FADE_OUT):
            # Splash image (centered, nudged up)
            if splash:
                sx = (screen_w - splash.get_width()) // 2
                sy = (screen_h - splash.get_height()) // 2 - 30
                if image_alpha < 255:
                    tmp = splash.copy()
                    tmp.set_alpha(image_alpha)
                    screen.blit(tmp, (sx, sy))
                else:
                    screen.blit(splash, (sx, sy))

            # Vignette overlay
            screen.blit(vignette, (0, 0))

            # Title: Κοῦραι Χρύσεαι
            title_str = "Κοῦραι Χρύσεαι"
            tr = title_font.get_rect(title_str)
            title_y = screen_h - 100
            title_font.render_to(
                screen,
                ((screen_w - tr.width) // 2, title_y),
                title_str,
                (*GOLD, min(image_alpha, 255)),
            )

            # Subtitle
            sub_str = "The Golden Maidens"
            sr = subtitle_font.get_rect(sub_str)
            subtitle_font.render_to(
                screen,
                ((screen_w - sr.width) // 2, title_y + tr.height + 8),
                sub_str,
                (*GOLD_DIM, min(image_alpha, 255)),
            )

            # "Press any key" (pulsing, only in READY phase)
            if phase == PHASE_READY:
                pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 400.0)
                prompt_str = "— Press any key —"
                pr = prompt_font.get_rect(prompt_str)
                prompt_alpha = max(0, min(255, int(255 * pulse)))
                prompt_font.render_to(
                    screen,
                    ((screen_w - pr.width) // 2, screen_h - 40),
                    prompt_str,
                    (*GOLD_BRIGHT, prompt_alpha),
                )

        # Fade-to-black overlay
        if phase == PHASE_FADE_OUT:
            overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            overlay.fill((*DARK_BG, fade_alpha))
            screen.blit(overlay, (0, 0))

        pygame.display.flip()


def _draw_text_card(
    screen: pygame.Surface,
    screen_w: int,
    screen_h: int,
    elapsed: float,
    main_font: pygame.freetype.Font,
    main_text: str,
    sub_text: str | None,
    sub_font: pygame.freetype.Font | None,
) -> None:
    """Draw a centered text card with fade-in / hold / fade-out timing."""
    card_duration = _CARD_FADE_IN + _CARD_HOLD + _CARD_FADE_OUT

    if elapsed < _CARD_FADE_IN:
        alpha = int(255 * (elapsed / _CARD_FADE_IN))
    elif elapsed < _CARD_FADE_IN + _CARD_HOLD:
        alpha = 255
    elif elapsed < card_duration:
        fade_t = (elapsed - _CARD_FADE_IN - _CARD_HOLD) / _CARD_FADE_OUT
        alpha = int(255 * (1.0 - fade_t))
    else:
        alpha = 0

    if alpha <= 0:
        return

    # Main text
    mr = main_font.get_rect(main_text)
    center_y = screen_h // 2
    main_font.render_to(
        screen,
        ((screen_w - mr.width) // 2, center_y - mr.height // 2),
        main_text,
        (*GOLD, alpha),
    )

    # Subtitle (below main text)
    if sub_text and sub_font:
        sr = sub_font.get_rect(sub_text)
        sub_font.render_to(
            screen,
            ((screen_w - sr.width) // 2, center_y + mr.height + 8),
            sub_text,
            (*GOLD_DIM, min(alpha, 180)),
        )
