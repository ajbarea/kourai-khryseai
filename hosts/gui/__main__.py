"""Kourai Khryseai — Pygame GUI client.

Full-resolution anime portrait dialogue window. JRPG/mecha comms aesthetic.
No kaomoji. The golden maidens speak for themselves.

Layout (1280×720):
  Left (320px)  — portrait panel: avatar + agent name + title
  Right (960px) — dialogue history (scrollable) + active dialogue box
  Bottom (80px) — text input bar, spans full width

Usage:
  make gui
  uv run python -m hosts.gui [--agent URL]
"""

from __future__ import annotations

import asyncio
import contextlib
import queue
import random
import signal
import sys
import textwrap
import threading
import time

import pygame
import pygame.freetype
from PIL import Image as PILImage

from .background_music import BackgroundMusic
from .client import GuiClient
from .dialogue_pacing import PacingMode
from .gui_components_integration import GUIComponentsIntegration
from .maidens import (
    AGENTS,
    HANDOFF_GENERIC,
    HANDOFF_LINES,
    VICTORY_LINES,
    detect_agent,
    get_avatar_path,
)
from .settings_ui import SettingsOverlay
from .tts_gui_integration import TTSGUIManager

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


# ---------------------------------------------------------------------------
# Particle system — floating golden embers
# ---------------------------------------------------------------------------
class Ember:
    """Single golden ember particle drifting upward."""

    __slots__ = ("x", "y", "vx", "vy", "radius", "alpha", "decay", "color")

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self.x = random.uniform(0, W)
        self.y = random.uniform(0, H)
        self.vx = random.uniform(-0.25, 0.25)
        self.vy = random.uniform(-0.6, -0.15)
        self.radius = random.uniform(1.0, 2.5)
        self.alpha = random.uniform(60, 180)
        self.decay = random.uniform(0.15, 0.5)
        r, g = random.randint(200, 255), random.randint(140, 200)
        self.color = (r, g, 20)

    def update(self, dt: float) -> bool:
        """Update position; return False when dead."""
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.alpha -= self.decay * dt * 60
        return self.alpha > 0

    def draw(self, surf: pygame.Surface) -> None:
        if self.alpha <= 0:
            return
        s = pygame.Surface((int(self.radius * 2 + 2), int(self.radius * 2 + 2)), pygame.SRCALPHA)
        pygame.draw.circle(
            s,
            (*self.color, int(self.alpha)),
            (int(self.radius + 1), int(self.radius + 1)),
            max(1, int(self.radius)),
        )
        surf.blit(s, (int(self.x - self.radius), int(self.y - self.radius)))


class ParticleSystem:
    MAX = 120

    def __init__(self) -> None:
        self._embers: list[Ember] = [Ember() for _ in range(self.MAX)]

    def update(self, dt: float) -> None:
        for e in self._embers:
            if not e.update(dt):
                e._reset()

    def draw(self, surf: pygame.Surface) -> None:
        for e in self._embers:
            e.draw(surf)


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


# ---------------------------------------------------------------------------
# Portrait panel — left side
# ---------------------------------------------------------------------------
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
        panel_rect = pygame.Rect(0, 0, PORTRAIT_W, DIALOGUE_H)

        # Panel background
        pygame.draw.rect(surf, PANEL_BG, panel_rect)
        pygame.draw.line(surf, GOLD_DIM, (PORTRAIT_W, 0), (PORTRAIT_W, DIALOGUE_H), 1)

        cx = PORTRAIT_W // 2
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

        # Random quote shown at bottom of panel (updated on agent switch)
        # stored externally via PortraitPanel.current_quote
        qtext = getattr(self, "current_quote", "")
        if qtext:
            wrapped = textwrap.wrap(qtext, width=28)
            q_y = sep_y + 12
            for line in wrapped[:6]:
                r = FONT_BANNER.get_rect(line)
                FONT_BANNER.render_to(
                    surf,
                    (cx - r.width // 2, q_y),
                    line,
                    DIM_WHITE,
                )
                q_y += 18


# ---------------------------------------------------------------------------
# Dialogue entry — one message bubble in history
# ---------------------------------------------------------------------------
class DialogueEntry:
    __slots__ = (
        "agent",
        "text",
        "is_user",
        "is_result",
        "is_error",
        "timestamp",
        "processing_time",
        "agent_count",
        "metadata_visible",
    )

    def __init__(
        self,
        agent: str,
        text: str,
        *,
        is_user: bool = False,
        is_result: bool = False,
        is_error: bool = False,
        processing_time: float | None = None,
        agent_count: int | None = None,
    ) -> None:
        self.agent = agent
        self.text = text
        self.is_user = is_user
        self.is_result = is_result
        self.is_error = is_error
        self.timestamp = time.monotonic()
        self.processing_time = processing_time
        self.agent_count = agent_count
        self.metadata_visible = True


# ---------------------------------------------------------------------------
# Dialogue history — right panel scrollable transcript
# ---------------------------------------------------------------------------
class DialogueHistory:
    PAD = 14
    BUBBLE_MAX_W = DIALOGUE_W - 40
    LINE_H = 20
    AGENT_LINE_H = 14

    def __init__(self) -> None:
        self._entries: list[DialogueEntry] = []
        self._entry_rects: list[tuple[DialogueEntry, pygame.Rect]] = []
        self._surf: pygame.Surface | None = None
        self._dirty = True
        self._scroll_y = 0
        self._content_h = 0

    def add(self, entry: DialogueEntry) -> None:
        self._entries.append(entry)
        self._dirty = True

    def update_last_text(self, text: str) -> None:
        """Append text to the last entry (for typewriter streaming)."""
        if self._entries:
            self._entries[-1].text = text
            self._dirty = True

    def scroll(self, dy: int) -> None:
        max_scroll = max(0, self._content_h - (DIALOGUE_H - self.PAD * 2 - 60))
        self._scroll_y = max(0, min(self._scroll_y + dy, max_scroll))

    def scroll_to_bottom(self) -> None:
        self._scroll_y = max(0, self._content_h - (DIALOGUE_H - self.PAD * 2 - 60))

    def handle_click(self, pos: tuple[int, int], dest_rect: pygame.Rect) -> str | None:
        """Handle mouse click and return the agent of the clicked message."""
        if not dest_rect.collidepoint(pos):
            return None

        # Convert screen coordinate to coordinate on the history surface
        surf_x = pos[0] - dest_rect.x
        surf_y = pos[1] - dest_rect.y + self._scroll_y

        for e, rect in self._entry_rects:
            if rect.collidepoint(surf_x, surf_y) and e.agent != "user" and e.agent in AGENTS:
                return e.agent
        return None

    def handle_right_click(self, pos: tuple[int, int], dest_rect: pygame.Rect) -> str | None:
        """Handle right click and return the text of the clicked message."""
        if not dest_rect.collidepoint(pos):
            return None

        # Convert screen coordinate to coordinate on the history surface
        surf_x = pos[0] - dest_rect.x
        surf_y = pos[1] - dest_rect.y + self._scroll_y

        for e, rect in self._entry_rects:
            if rect.collidepoint(surf_x, surf_y):
                return e.text
        return None

    def _render(self) -> None:
        """Re-render all entries onto self._surf."""
        # First pass: measure total height
        total_h = self.PAD
        for e in self._entries:
            total_h += self._entry_height(e)
            total_h += 10

        surf_h = max(total_h, DIALOGUE_H)
        self._surf = pygame.Surface((DIALOGUE_W, surf_h), pygame.SRCALPHA)
        self._content_h = total_h
        self._entry_rects.clear()

        y = self.PAD
        for e in self._entries:
            rect = self._draw_entry(self._surf, e, y)
            if rect:
                self._entry_rects.append((e, rect))
            y += self._entry_height(e) + 10

        self._dirty = False

    def _entry_height(self, e: DialogueEntry) -> int:
        h = 0
        if not e.is_user:
            h += self.AGENT_LINE_H + 4  # agent header
        # Body text
        lines = self._wrap_text(e.text, self.BUBBLE_MAX_W - self.PAD * 2)
        h += len(lines) * self.LINE_H + self.PAD * 2
        return h

    def _wrap_text(self, text: str, max_w: int) -> list[str]:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            wrapped = textwrap.wrap(paragraph or " ", width=max(1, max_w // 9))
            lines.extend(wrapped or [" "])
        return lines

    def _draw_entry(self, surf: pygame.Surface, e: DialogueEntry, y: int) -> pygame.Rect | None:
        pad = self.PAD
        lines = self._wrap_text(e.text, self.BUBBLE_MAX_W - pad * 2)
        body_h = len(lines) * self.LINE_H + pad * 2
        header_h = 0 if e.is_user else (self.AGENT_LINE_H + 4)
        total_h = body_h + header_h

        drawn_rect = None

        if e.is_user:
            # User bubble — right-aligned, dim gold border
            bubble_w = min(self.BUBBLE_MAX_W, max(200, len(e.text) * 9 + pad * 2))
            bx = DIALOGUE_W - bubble_w - 8
            bubble = pygame.Surface((bubble_w, body_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (30, 22, 10, 200), bubble.get_rect(), border_radius=8)
            pygame.draw.rect(bubble, (*GOLD_DIM, 180), bubble.get_rect(), 1, border_radius=8)
            for i, line in enumerate(lines):
                FONT_BODY.render_to(bubble, (pad, pad + i * self.LINE_H), line, WHITE)
            surf.blit(bubble, (bx, y))
            drawn_rect = pygame.Rect(bx, y, bubble_w, body_h)
        elif e.is_result:
            # Result block — full width, slightly highlighted
            bubble = pygame.Surface((DIALOGUE_W - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (20, 18, 10, 220), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(bubble, (*GOLD, 120), bubble.get_rect(), 1, border_radius=6)
            # Left gold accent bar
            pygame.draw.rect(bubble, GOLD, pygame.Rect(0, 0, 3, total_h), border_radius=2)
            info = AGENTS.get(e.agent, {})
            hdr = f"✦ {e.agent.upper()} — {info.get('title', '')}"
            FONT_AGENT.render_to(bubble, (pad + 4, 4), hdr, GOLD)
            for i, line in enumerate(lines):
                FONT_BODY.render_to(
                    bubble, (pad + 4, header_h + pad + i * self.LINE_H), line, WHITE
                )
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, DIALOGUE_W - 16, total_h)
        elif e.is_error:
            bubble = pygame.Surface((DIALOGUE_W - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (40, 10, 10, 200), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(bubble, (*ERROR_RED, 160), bubble.get_rect(), 1, border_radius=6)
            for i, line in enumerate(lines):
                FONT_BODY.render_to(bubble, (pad, pad + i * self.LINE_H), line, (220, 100, 80))
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, DIALOGUE_W - 16, total_h)
        else:
            # Agent status bubble
            info = AGENTS.get(e.agent, {})
            agent_color = info.get("color", GOLD)
            bubble = pygame.Surface((DIALOGUE_W - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (20, 16, 8, 180), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(bubble, (*agent_color, 80), bubble.get_rect(), 1, border_radius=6)
            hdr = f"{e.agent.upper()} — {info.get('title', '')}"
            FONT_AGENT.render_to(bubble, (pad, 3), hdr, agent_color)
            for i, line in enumerate(lines):
                dim = min(i * 8, 40)
                col = tuple(max(0, c - dim) for c in WHITE)
                FONT_BODY.render_to(bubble, (pad, header_h + pad + i * self.LINE_H), line, col)
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, DIALOGUE_W - 16, total_h)

        return drawn_rect

    def draw(self, surf: pygame.Surface, dest_rect: pygame.Rect) -> None:
        if self._dirty:
            self._render()
        if self._surf is None:
            return

        clip_surf = pygame.Surface((dest_rect.width, dest_rect.height), pygame.SRCALPHA)
        clip_surf.blit(self._surf, (0, -self._scroll_y))
        surf.blit(clip_surf, dest_rect.topleft)

        # Scrollbar
        if self._content_h > dest_rect.height:
            ratio = dest_rect.height / self._content_h
            bar_h = max(30, int(dest_rect.height * ratio))
            bar_y = dest_rect.top + int(self._scroll_y / self._content_h * dest_rect.height)
            pygame.draw.rect(
                surf, SCROLLBAR, pygame.Rect(dest_rect.right - 4, bar_y, 3, bar_h), border_radius=2
            )

    def toggle_timestamps(self) -> None:
        """Toggle timestamp visibility."""
        # This will be managed by settings
        pass

    def toggle_metadata(self) -> None:
        """Toggle metadata visibility."""
        # This will be managed by settings
        pass

    def set_timestamp_format(self, fmt: str) -> None:
        """Set timestamp format (12h or 24h)."""
        # This will be managed by settings
        pass

    def get_timestamp_text(self, entry: DialogueEntry, fmt: str = "24h") -> str:
        """Get formatted timestamp for entry."""
        import datetime

        dt = datetime.datetime.fromtimestamp(entry.timestamp)
        if fmt == "12h":
            return dt.strftime("%I:%M:%S %p")
        else:
            return dt.strftime("%H:%M:%S")

    def get_metadata_text(self, entry: DialogueEntry) -> str:
        """Get metadata text for entry."""
        parts = []
        if entry.processing_time is not None:
            parts.append(f"⏱ {entry.processing_time:.2f}s")
        if entry.agent_count is not None:
            parts.append(f"👥 {entry.agent_count}")
        return " | ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Input bar
# ---------------------------------------------------------------------------
class InputBar:
    PAD = 12
    CURSOR_BLINK = 0.5

    def __init__(self) -> None:
        self.text = ""
        self._cursor_on = True
        self._blink_acc = 0.0
        self.processing = False
        self.waiting_for_agent: str | None = None
        self._placeholder = "Type a message... (Enter to send)"

    def update(self, dt: float) -> None:
        self._blink_acc += dt
        if self._blink_acc >= self.CURSOR_BLINK:
            self._cursor_on = not self._cursor_on
            self._blink_acc = 0.0

    def handle_key(self, event: pygame.event.Event) -> str | None:
        """Handle a KEYDOWN event. Returns the submitted text or None."""
        if event.key == pygame.K_RETURN and not event.mod & pygame.KMOD_SHIFT:
            if self.text.strip() and not self.processing:
                submitted = self.text.strip()
                self.text = ""
                return submitted
        elif event.key == pygame.K_BACKSPACE:
            if event.mod & pygame.KMOD_CTRL:
                # Ctrl+Backspace deletes last word
                parts = self.text.rstrip().rsplit(" ", 1)
                self.text = parts[0] + " " if len(parts) > 1 else ""
            else:
                self.text = self.text[:-1]
        return None

    def handle_textinput(self, event: pygame.event.Event) -> None:
        self.text += event.text

    def draw(self, surf: pygame.Surface) -> None:
        rect = pygame.Rect(0, H - INPUT_H, W, INPUT_H)
        pygame.draw.rect(surf, INPUT_BG, rect)

        if self.waiting_for_agent:
            # Pulsing color border to indicate agent waiting
            pulse = int((time.monotonic() * 4) % 2 * 50)
            agent_color = AGENTS.get(self.waiting_for_agent, {}).get("color", GOLD)
            pulse_color = (
                min(255, agent_color[0] + pulse),
                min(255, agent_color[1] + pulse),
                min(255, agent_color[2] + pulse),
            )
            pygame.draw.line(surf, pulse_color, (0, H - INPUT_H), (W, H - INPUT_H), 2)
        else:
            pygame.draw.line(surf, GOLD_DIM, (0, H - INPUT_H), (W, H - INPUT_H), 1)

        # Forge mark (left icon)
        FONT_BODY.render_to(surf, (self.PAD, H - INPUT_H + (INPUT_H - 18) // 2), "✦", GOLD)

        # Input text area
        text_x = self.PAD + 28
        text_y = H - INPUT_H + (INPUT_H - 18) // 2

        if self.processing and not self.waiting_for_agent:
            # Animated dots while processing
            dots = "." * (int(time.monotonic() * 3) % 4)
            FONT_INPUT.render_to(surf, (text_x, text_y), f"processing{dots}", GOLD_DIM)
        elif self.text:
            FONT_INPUT.render_to(surf, (text_x, text_y), self.text, WHITE)
            if self._cursor_on:
                cursor_x = text_x + FONT_INPUT.get_rect(self.text).width + 2
                pygame.draw.line(surf, GOLD, (cursor_x, text_y), (cursor_x, text_y + 18), 2)
        else:
            placeholder = (
                f"[{self.waiting_for_agent.capitalize()} is waiting for input] Type your answer..."
                if self.waiting_for_agent
                else self._placeholder
            )
            color = (
                AGENTS.get(self.waiting_for_agent, {}).get("color", GOLD)
                if self.waiting_for_agent
                else (80, 70, 50)
            )
            FONT_INPUT.render_to(surf, (text_x, text_y), placeholder, color)
            if self._cursor_on:
                pygame.draw.line(surf, GOLD_DIM, (text_x, text_y), (text_x, text_y + 18), 2)

        # Send hint
        hint = "↵ send" if not (self.processing and not self.waiting_for_agent) else ""
        FONT_TITLE.render_to(surf, (W - 80, H - INPUT_H + (INPUT_H - 12) // 2), hint, GOLD_DIM)


# ---------------------------------------------------------------------------
# Banner / title bar
# ---------------------------------------------------------------------------
def _draw_banner(surf: pygame.Surface, connected: bool, agent_url: str) -> None:
    """Top-of-transcript title strip."""
    r = pygame.Rect(DIALOGUE_X, 0, DIALOGUE_W, 32)
    pygame.draw.rect(surf, (10, 8, 5), r)
    pygame.draw.line(surf, GOLD_DIM, (DIALOGUE_X, 32), (W, 32), 1)

    title = "✦  KOURAI KHRYSEAI  —  Golden Maidens"
    FONT_AGENT.render_to(surf, (DIALOGUE_X + 12, 8), title, GOLD)

    status_text = "connected" if connected else "connecting..."
    status_col = (100, 180, 100) if connected else GOLD_DIM
    sr = FONT_BANNER.get_rect(status_text)
    FONT_BANNER.render_to(surf, (W - sr.width - 12, 10), status_text, status_col)


# ---------------------------------------------------------------------------
# Main GUI entry point
# ---------------------------------------------------------------------------
def main(agent_url: str | None = None) -> None:
    # Setup shutdown flag and signal handlers for graceful Ctrl+C shutdown
    _shutdown_flag = {"running": True}
    _queues = {"send_q": None}

    def _signal_handler(signum: int, frame) -> None:
        _shutdown_flag["running"] = False
        # Signal the client to shut down
        try:
            if _queues["send_q"] is not None:
                _queues["send_q"].put(None)
        except Exception:
            pass

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    pygame.init()
    pygame.display.set_caption("Kourai Khryseai — Golden Maidens")

    # Try to set a nice window icon (hephaestus avatar)
    icon_path = get_avatar_path("hephaestus")
    if icon_path:
        try:
            icon_img = PILImage.open(icon_path).convert("RGBA").resize((32, 32))
            icon_surf = pygame.image.frombytes(icon_img.tobytes(), (32, 32), "RGBA")
            pygame.display.set_icon(icon_surf)
        except Exception:
            pass

    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    # --- Subsystems ---
    gui_integration = GUIComponentsIntegration(None)
    settings_overlay = SettingsOverlay(W, H, gui_integration)

    particles = ParticleSystem()
    portrait = PortraitPanel()
    history = DialogueHistory()
    input_bar = InputBar()

    # Set initial Hephaestus quote
    heph_quotes = AGENTS["hephaestus"].get("user_quotes", [])
    portrait.current_quote = random.choice(heph_quotes) if heph_quotes else ""

    # --- Fullscreen state ---
    is_fullscreen = gui_integration.settings.get("fullscreen", False)

    if is_fullscreen:
        pygame.display.toggle_fullscreen()

    def toggle_fullscreen(enable: bool) -> None:
        nonlocal is_fullscreen, dialogue_rect, settings_overlay
        is_fullscreen = enable
        pygame.display.toggle_fullscreen()

        # Small delay to let pygame update the display
        time.sleep(0.1)

        # Get the actual screen size after toggle
        screen_w, screen_h = screen.get_size()
        dialogue_rect.width = screen_w - DIALOGUE_X
        dialogue_rect.height = screen_h - INPUT_H

        # Update settings overlay dimensions
        settings_overlay.screen_w = screen_w
        settings_overlay.screen_h = screen_h
        settings_overlay.panel_rect.centerx = screen_w // 2
        settings_overlay.panel_rect.centery = screen_h // 2

        # Update settings overlay dimensions
        settings_overlay.screen_w = screen_w
        settings_overlay.screen_h = screen_h
        settings_overlay.panel_rect.centerx = screen_w // 2
        settings_overlay.panel_rect.centery = screen_h // 2

    settings_overlay.set_fullscreen_callback(toggle_fullscreen)

    def on_quit() -> None:
        nonlocal running
        running = False
        send_q.put(None)  # shutdown client

    settings_overlay.set_quit_callback(on_quit)

    # --- A2A client in background thread ---
    send_q: queue.Queue[tuple[str, str] | None] = queue.Queue()
    recv_q: queue.Queue[dict] = queue.Queue()
    _queues["send_q"] = send_q  # Store for signal handler
    client = GuiClient(send_q, recv_q, agent_url)

    def _run_client() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.run())
        finally:
            loop.close()

    _thread = threading.Thread(target=_run_client, daemon=True)
    _thread.start()

    # --- Background Music ---
    bg_music = BackgroundMusic()
    bg_music.play_ambient_music()

    # --- TTS Manager ---
    tts_manager = TTSGUIManager(recv_q, enable_tts=True, pacing_mode=PacingMode.NORMAL)
    tts_manager.set_current_agent("hephaestus")

    # --- State ---
    connected = False
    current_agent = "hephaestus"
    last_agent = "hephaestus"

    dialogue_rect = pygame.Rect(DIALOGUE_X, 34, DIALOGUE_W, DIALOGUE_H - 34)

    while _shutdown_flag["running"]:
        dt = clock.tick(60) / 1000.0

        # --- Process recv_q events ---
        while not recv_q.empty():
            event = recv_q.get_nowait()
            etype = event.get("type")

            if etype == "connected":
                connected = True
                history.add(
                    DialogueEntry(
                        "hephaestus",
                        f"Connected to {event.get('name', 'Hephaestus')}. "
                        "The forge is hot. What are we building?",
                    )
                )
                history.scroll_to_bottom()

            elif etype == "disconnected":
                connected = False

            elif etype == "status":
                raw = event["text"]
                agent, text = detect_agent(raw)
                if not text:
                    continue

                if "INPUT_REQUIRED:" in text:
                    parts = text.split("INPUT_REQUIRED:", 1)
                    question = parts[1].strip()
                    input_bar.waiting_for_agent = agent or current_agent
                    input_bar.processing = False
                    history.add(DialogueEntry(agent or current_agent, question))
                    history.scroll_to_bottom()
                    continue

                if agent:
                    # Detect agent switch
                    if agent != current_agent:
                        # Handoff chatter from outgoing agent
                        key = (current_agent, agent)
                        lines = HANDOFF_LINES.get(key) or HANDOFF_GENERIC.get(current_agent)
                        if lines:
                            handoff_line = random.choice(lines)
                            history.add(DialogueEntry(current_agent, handoff_line))

                        portrait.switch_to(agent)
                        # Update quote for new agent
                        agent_quotes = AGENTS.get(agent, {}).get("quotes", [])
                        portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""
                        current_agent = agent
                        last_agent = agent

                    history.add(DialogueEntry(agent, text))
                else:
                    history.add(DialogueEntry(current_agent, text))

                history.scroll_to_bottom()

            elif etype == "result":
                text = event["text"]
                history.add(DialogueEntry(last_agent, text, is_result=True))
                history.scroll_to_bottom()

            elif etype == "complete":
                elapsed = event.get("elapsed", 0.0)
                input_bar.processing = False

                # Victory line
                vlines = VICTORY_LINES.get(last_agent, [])
                if vlines:
                    history.add(
                        DialogueEntry(last_agent, f"{random.choice(vlines)}  ✦ {elapsed:.1f}s")
                    )

                history.scroll_to_bottom()

            elif etype == "error":
                history.add(DialogueEntry("hephaestus", event["text"], is_error=True))
                input_bar.processing = False
                history.scroll_to_bottom()

        # --- Pygame events ---
        for event in pygame.event.get():
            if settings_overlay.handle_event(event):
                continue

            if event.type == pygame.QUIT:
                running = False
                send_q.put(None)  # shutdown client

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    settings_overlay.toggle()
                else:
                    submitted = input_bar.handle_key(event)
                    if submitted:
                        # Show user bubble
                        history.add(DialogueEntry("user", submitted, is_user=True))
                        history.scroll_to_bottom()
                        # Send to pipeline
                        send_q.put((input_bar.waiting_for_agent or current_agent, submitted))
                        input_bar.processing = True

                        # Reset to Hephaestus for the incoming pipeline
                        portrait.switch_to(input_bar.waiting_for_agent or "hephaestus")
                        current_agent = input_bar.waiting_for_agent or "hephaestus"
                        input_bar.waiting_for_agent = None

                        agent_quotes = AGENTS[current_agent].get("user_quotes", [])
                        portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""

            elif event.type == pygame.TEXTINPUT:
                if not input_bar.processing:
                    input_bar.handle_textinput(event)

            elif event.type == pygame.MOUSEWHEEL:
                history.scroll(-event.y * 40)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_agent = history.handle_click(event.pos, dialogue_rect)
                if clicked_agent and clicked_agent in AGENTS:
                    portrait.switch_to(clicked_agent)
                    current_agent = clicked_agent
                    agent_quotes = AGENTS.get(clicked_agent, {}).get("quotes", [])
                    portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                clicked_text = history.handle_right_click(event.pos, dialogue_rect)
                if clicked_text:
                    try:
                        pygame.scrap.put_text(clicked_text)
                    except Exception as e:
                        print(f"Clipboard error: {e}")

            elif event.type == pygame.VIDEORESIZE:
                # Update layout for new window size
                screen_w, screen_h = event.size
                dialogue_rect.width = screen_w - DIALOGUE_X
                dialogue_rect.height = screen_h - INPUT_H

                # Update settings overlay dimensions
                settings_overlay.screen_w = screen_w
                settings_overlay.screen_h = screen_h
                settings_overlay.panel_rect.centerx = screen_w // 2
                settings_overlay.panel_rect.centery = screen_h // 2

        # --- Updates ---
        gui_integration.update(dt)
        settings_overlay.update(dt)

        # Map dynamic high-contrast colors to global constants for immediate UI feedback
        palette = gui_integration.high_contrast.get_color_palette()
        global \
            DARK_BG, \
            PANEL_BG, \
            GOLD, \
            GOLD_BRIGHT, \
            GOLD_DIM, \
            GOLD_GLOW, \
            WHITE, \
            DIM_WHITE, \
            INPUT_BG, \
            SCROLLBAR, \
            ERROR_RED
        DARK_BG = palette.get("background", (12, 10, 8))
        PANEL_BG = palette.get("bubble_bg", (18, 14, 10))
        GOLD = palette.get("gold", (218, 165, 32))
        GOLD_BRIGHT = palette.get("gold", (255, 215, 0))
        GOLD_DIM = palette.get("gold_dim", (140, 105, 20))
        WHITE = palette.get("text", (240, 235, 225))
        DIM_WHITE = palette.get("scrollbar", (160, 155, 145))
        INPUT_BG = palette.get("bubble_bg", (20, 16, 12))
        SCROLLBAR = palette.get("scrollbar", (50, 40, 25))
        ERROR_RED = palette.get("error_red", (200, 80, 60))

        if not gui_integration.settings.get("reduce_motion", False):
            particles.update(dt)

        portrait.update(dt)
        input_bar.update(dt)

        # --- Draw ---
        screen.fill(DARK_BG)

        # Background particles (full canvas)
        if not gui_integration.settings.get("reduce_motion", False):
            particles.draw(screen)

        # Left: portrait panel
        portrait.draw(screen)

        # Right: banner + dialogue history
        _draw_banner(screen, connected, agent_url or "")
        history.draw(screen, dialogue_rect)

        # Right panel border
        pygame.draw.line(screen, GOLD_DIM, (DIALOGUE_X, 0), (DIALOGUE_X, H - INPUT_H), 1)

        # Bottom: input
        input_bar.draw(screen)

        # Overlay
        settings_overlay.draw(screen)

        pygame.display.flip()

    # Cleanup (graceful shutdown on Ctrl+C)
    with contextlib.suppress(Exception):
        bg_music.cleanup()
    with contextlib.suppress(Exception):
        tts_manager.cleanup()
    with contextlib.suppress(Exception):
        pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kourai Khryseai — Pygame GUI")
    parser.add_argument("--agent", default=None, help="Hephaestus agent URL")
    args = parser.parse_args()
    main(agent_url=args.agent)
