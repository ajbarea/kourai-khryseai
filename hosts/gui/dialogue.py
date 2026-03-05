"""Dialogue system — entry model, scrollable history, and banner rendering."""

from __future__ import annotations

import re
import textwrap
import time

import pygame

from .constants import (
    DIALOGUE_H,
    DIALOGUE_W,
    DIALOGUE_X,
    DIM_WHITE,
    ERROR_RED,
    FONT_AGENT,
    FONT_BANNER,
    FONT_BODY,
    GOLD,
    GOLD_DIM,
    SCROLLBAR,
    WHITE,
    W,
)
from .maidens import AGENTS

# Pattern for emote cues: *action text*
_EMOTE_RE = re.compile(r"\*([^*]+)\*")


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
        "is_system",
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
        is_system: bool = False,
        processing_time: float | None = None,
        agent_count: int | None = None,
    ) -> None:
        self.agent = agent
        self.text = text
        self.is_user = is_user
        self.is_result = is_result
        self.is_error = is_error
        self.is_system = is_system
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

        surf_x = pos[0] - dest_rect.x
        surf_y = pos[1] - dest_rect.y + self._scroll_y

        for e, rect in self._entry_rects:
            if rect.collidepoint(surf_x, surf_y):
                return e.text
        return None

    def _render(self) -> None:
        """Re-render all entries onto self._surf."""
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

    # System message fade timing (seconds)
    SYSTEM_FADE_START = 4.0
    SYSTEM_FADE_DURATION = 1.5

    def _system_alpha(self, e: DialogueEntry) -> float:
        """Return 0.0–1.0 alpha for a system entry based on age."""
        age = time.monotonic() - e.timestamp
        if age < self.SYSTEM_FADE_START:
            return 1.0
        fade_progress = (age - self.SYSTEM_FADE_START) / self.SYSTEM_FADE_DURATION
        return max(0.0, 1.0 - fade_progress)

    def _entry_height(self, e: DialogueEntry) -> int:
        if e.is_system:
            alpha = self._system_alpha(e)
            if alpha <= 0.0:
                return 0  # fully faded — collapse
            return 24  # compact single-line height
        h = 0
        if not e.is_user:
            h += self.AGENT_LINE_H + 4
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

        if e.is_system:
            # Compact, borderless, dim, auto-fading system message
            alpha = self._system_alpha(e)
            if alpha <= 0.0:
                return None
            a = int(alpha * 140)
            col = (*DIM_WHITE, a)
            FONT_AGENT.render_to(surf, (16, y + 4), f"⋯ {e.text}", col)
            drawn_rect = pygame.Rect(8, y, DIALOGUE_W - 16, 24)
        elif e.is_user:
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
            # Agent dialogue bubble — with emote rendering
            info = AGENTS.get(e.agent, {})
            agent_color = info.get("color", GOLD)
            bubble = pygame.Surface((DIALOGUE_W - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (20, 16, 8, 180), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(bubble, (*agent_color, 80), bubble.get_rect(), 1, border_radius=6)
            hdr = f"{e.agent.upper()} — {info.get('title', '')}"
            FONT_AGENT.render_to(bubble, (pad, 3), hdr, agent_color)
            for i, line in enumerate(lines):
                dim = min(i * 8, 40)
                base_col = tuple(max(0, c - dim) for c in WHITE)
                self._draw_line_with_emotes(bubble, pad, header_h + pad + i * self.LINE_H, line, base_col)
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, DIALOGUE_W - 16, total_h)

        return drawn_rect

    def _draw_line_with_emotes(
        self, surf: pygame.Surface, x: int, y: int, line: str, base_col: tuple
    ) -> None:
        """Render a line with *emote* spans in dim gold italic."""
        parts = _EMOTE_RE.split(line)
        cursor_x = x
        is_emote = False
        for part in parts:
            if not part:
                is_emote = not is_emote
                continue
            if is_emote:
                text = f"*{part}*"
                col = (*GOLD_DIM, 180)
                rect = FONT_AGENT.render_to(surf, (cursor_x, y + 2), text, col)
            else:
                rect = FONT_BODY.render_to(surf, (cursor_x, y), part, base_col)
            cursor_x += rect.width + 1
            is_emote = not is_emote

    def draw(self, surf: pygame.Surface, dest_rect: pygame.Rect) -> None:
        # Re-render whenever system messages are still fading
        if any(
            e.is_system and self._system_alpha(e) > 0.0
            for e in self._entries
        ):
            self._dirty = True

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
        pass

    def toggle_metadata(self) -> None:
        """Toggle metadata visibility."""
        pass

    def set_timestamp_format(self, fmt: str) -> None:
        """Set timestamp format (12h or 24h)."""
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
# Banner / title bar
# ---------------------------------------------------------------------------
def draw_banner(surf: pygame.Surface, connected: bool, agent_url: str) -> None:
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
