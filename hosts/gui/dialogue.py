"""Dialogue system — entry model, scrollable history, and banner rendering."""

from __future__ import annotations

import re
import time

import pygame
import pygame.freetype

from . import constants
from .maidens import AGENTS

# Pattern for emote cues: *action text*
_EMOTE_RE = re.compile(r"\*([^*]+)\*")


def _is_quoted_dialogue(text: str) -> bool:
    """Speech-vs-action: a leading double-quote marks the line as dialogue.

    The agents' SYSTEM_PROMPT instructs them to wrap player-directed lines
    in double quotes; status/action lines stay unquoted. This single
    line-level check drives italic styling so the human-on-the-loop
    checkpoint pops against the plain status stream.
    """
    return text.lstrip().startswith('"')


# ---------------------------------------------------------------------------
# Dialogue entry — one message bubble in history
# ---------------------------------------------------------------------------
class DialogueEntry:
    __slots__ = (
        "_timestamp",
        "_timestamp_source",
        "_wall_timestamp",
        "agent",
        "agent_count",
        "is_error",
        "is_result",
        "is_system",
        "is_user",
        "metadata_visible",
        "processing_time",
        "text",
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
        self._timestamp = time.monotonic()
        self._timestamp_source = "monotonic"
        self._wall_timestamp = time.time()
        self.processing_time = processing_time
        self.agent_count = agent_count
        self.metadata_visible = True

    @property
    def timestamp(self) -> float:
        """Expose the creation timestamp for tests and age-based UI logic."""
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: float) -> None:
        ts = float(value)
        self._timestamp = ts
        self._timestamp_source = "manual"
        self._wall_timestamp = ts

    def get_age_seconds(self) -> float:
        """Return the entry age using the correct clock source."""
        if self._timestamp_source == "monotonic":
            return time.monotonic() - self._timestamp
        if self._timestamp >= 1_000_000_000:
            return time.time() - self._timestamp
        return time.monotonic() - self._timestamp

    def get_display_timestamp(self) -> float:
        """Return the wall-clock timestamp used for user-visible formatting."""
        return self._wall_timestamp


# ---------------------------------------------------------------------------
# Dialogue history — right panel scrollable transcript
# ---------------------------------------------------------------------------
class DialogueHistory:
    PAD = 14
    BUBBLE_MAX_W = constants.DIALOGUE_W - 40
    _LINE_H_BASE = 20
    _AGENT_LINE_H_BASE = 14

    @property
    def line_h(self) -> int:
        return max(16, round(self._LINE_H_BASE * constants.get_font_scale()))

    @property
    def agent_line_h(self) -> int:
        return max(12, round(self._AGENT_LINE_H_BASE * constants.get_font_scale()))

    def __init__(self) -> None:
        self._entries: list[DialogueEntry] = []
        self._entry_rects: list[tuple[DialogueEntry, pygame.Rect]] = []
        self._surf: pygame.Surface | None = None
        self._dirty = True
        self._scroll_y = 0
        self._content_h = 0
        self._viewport_h = constants.DIALOGUE_H
        self.show_timestamps = True
        self.show_metadata = True
        self.timestamp_format = "24h"
        # Re-rasterise the cached transcript surface whenever the font
        # scale changes — otherwise zoom updates the FontProxy glyphs
        # but this surface still holds pre-zoom text.
        constants.on_font_scale_change(self._mark_dirty_from_font_scale)

    def _mark_dirty_from_font_scale(self) -> None:
        self._dirty = True

    def add(self, entry: DialogueEntry) -> None:
        self._entries.append(entry)
        self._dirty = True

    def update_layout(self, width: int, height: int) -> None:
        """Force a re-render if the width has changed."""
        if self._surf is None or width != self._surf.get_width():
            self._dirty = True
        self._viewport_h = height

    def update_last_text(self, text: str) -> None:
        """Append text to the last entry (for typewriter streaming)."""
        if self._entries:
            self._entries[-1].text = text
            self._dirty = True

    def scroll(self, dy: int) -> None:
        max_scroll = max(0, self._content_h - (self._viewport_h - self.PAD * 2 - 60))
        self._scroll_y = max(0, min(self._scroll_y + dy, max_scroll))

    def scroll_to_bottom(self) -> None:
        self._scroll_y = max(0, self._content_h - (self._viewport_h - self.PAD * 2 - 60))

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

    def _render(self, dest_rect: pygame.Rect) -> None:
        """Re-render all entries onto self._surf."""
        self._viewport_h = dest_rect.height
        total_h = self.PAD
        dest_w = dest_rect.width

        for e in self._entries:
            total_h += self._entry_height(e, dest_w)
            total_h += 10

        surf_h = max(total_h, dest_rect.height)
        self._surf = pygame.Surface((dest_w, surf_h), pygame.SRCALPHA)
        self._content_h = total_h
        self._entry_rects.clear()

        y = self.PAD
        for e in self._entries:
            rect = self._draw_entry(self._surf, e, y, dest_w)
            if rect:
                self._entry_rects.append((e, rect))
            y += self._entry_height(e, dest_w) + 10

        self._dirty = False

    # System message fade timing (seconds)
    SYSTEM_FADE_START = 4.0
    SYSTEM_FADE_DURATION = 1.5

    def _system_alpha(self, e: DialogueEntry) -> float:
        """Return 0.0–1.0 alpha for a system entry based on age."""
        age = e.get_age_seconds()
        if age < self.SYSTEM_FADE_START:
            return 1.0
        fade_progress = (age - self.SYSTEM_FADE_START) / self.SYSTEM_FADE_DURATION
        return max(0.0, 1.0 - fade_progress)

    def _entry_height(self, e: DialogueEntry, dest_w: int) -> int:
        if e.is_system:
            alpha = self._system_alpha(e)
            if alpha <= 0.0:
                return 0  # fully faded — collapse
            return 24  # compact single-line height
        h = 0
        if not e.is_user:
            h += self.agent_line_h + 4
        bubble_max_w = dest_w - 40
        lines = self._wrap_text(e.text, bubble_max_w - self.PAD * 2)
        h += len(lines) * self.line_h + self.PAD * 2
        return h

    def _wrap_text(self, text: str, max_w: int) -> list[str]:
        # Measure against the actual scaled font instead of estimating 9px/char.
        # The old char-count estimate over-packed lines once zoom scaled glyphs
        # wider than 9px, so messages overflowed the bubble at higher zoom.
        max_w = max(1, max_w)
        lines: list[str] = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append(" ")
                continue
            current = ""
            for word in paragraph.split(" "):
                candidate = word if not current else f"{current} {word}"
                if constants.FONT_BODY.get_rect(candidate).width <= max_w:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                    current = ""
                if constants.FONT_BODY.get_rect(word).width > max_w:
                    # single word overflows — fall back to character-level break
                    chunk = ""
                    for ch in word:
                        probe = chunk + ch
                        if constants.FONT_BODY.get_rect(probe).width <= max_w:
                            chunk = probe
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = ch
                    current = chunk
                else:
                    current = word
            if current:
                lines.append(current)
        return lines or [" "]

    def _draw_entry(
        self, surf: pygame.Surface, e: DialogueEntry, y: int, dest_w: int
    ) -> pygame.Rect | None:
        pad = self.PAD
        bubble_max_w = dest_w - 40
        lines = self._wrap_text(e.text, bubble_max_w - pad * 2)
        body_h = len(lines) * self.line_h + pad * 2
        header_h = 0 if e.is_user else (self.agent_line_h + 4)
        total_h = body_h + header_h

        drawn_rect = None

        if e.is_system:
            # Compact, borderless, dim, auto-fading system message
            alpha = self._system_alpha(e)
            if alpha <= 0.0:
                return None
            a = int(alpha * 140)
            col = (*constants.DIM_WHITE, a)
            constants.FONT_AGENT.render_to(surf, (16, y + 4), f"⋯ {e.text}", col)
            drawn_rect = pygame.Rect(8, y, dest_w - 16, 24)
        elif e.is_user:
            # User bubble — right-aligned, dim gold border.
            # Pre-measure the timestamp and reserve horizontal room for it in
            # the bubble width, otherwise it paints on top of the message in
            # tight single-line bubbles (no agent-header strip to clear).
            ts_text = (
                self.get_timestamp_text(e, self.timestamp_format) if self.show_timestamps else ""
            )
            ts_rect = constants.FONT_TITLE.get_rect(ts_text) if ts_text else pygame.Rect(0, 0, 0, 0)
            ts_reserved = ts_rect.width + 8 if ts_text else 0

            text_px_w = constants.FONT_BODY.get_rect(e.text).width
            bubble_w = min(bubble_max_w, max(200, text_px_w + pad * 2 + ts_reserved))
            bx = dest_w - bubble_w - 8
            bubble = pygame.Surface((bubble_w, body_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (30, 22, 10, 200), bubble.get_rect(), border_radius=8)
            pygame.draw.rect(
                bubble, (*constants.GOLD_DIM, 180), bubble.get_rect(), 1, border_radius=8
            )

            if ts_text:
                constants.FONT_TITLE.render_to(
                    bubble, (bubble_w - ts_rect.width - 8, 4), ts_text, constants.GOLD_DIM
                )

            for i, line in enumerate(lines):
                constants.FONT_BODY.render_to(
                    bubble, (pad, pad + i * self.line_h), line, constants.WHITE
                )
            surf.blit(bubble, (bx, y))
            drawn_rect = pygame.Rect(bx, y, bubble_w, body_h)
        elif e.is_result:
            # Result block — full width, slightly highlighted
            bubble = pygame.Surface((dest_w - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (20, 18, 10, 220), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(bubble, (*constants.GOLD, 120), bubble.get_rect(), 1, border_radius=6)
            # Left gold accent bar
            pygame.draw.rect(bubble, constants.GOLD, pygame.Rect(0, 0, 3, total_h), border_radius=2)
            info = AGENTS.get(e.agent, {})
            hdr = f"* {e.agent.upper()} — {info.get('title', '')}"
            constants.FONT_AGENT.render_to(bubble, (pad + 4, 4), hdr, constants.GOLD)

            # Metadata and timestamp — right-aligned with measured widths so
            # both stay on-screen when the font scales up at higher zoom.
            bubble_inner_right = (dest_w - 16) - pad
            right_x = bubble_inner_right
            if self.show_timestamps:
                ts = self.get_timestamp_text(e, self.timestamp_format)
                ts_rect = constants.FONT_TITLE.get_rect(ts)
                right_x -= ts_rect.width
                constants.FONT_TITLE.render_to(bubble, (right_x, 4), ts, constants.GOLD_DIM)
                right_x -= 8  # gap between ts and metadata
            if self.show_metadata and e.metadata_visible:
                meta = self.get_metadata_text(e)
                meta_rect = constants.FONT_TITLE.get_rect(meta)
                constants.FONT_TITLE.render_to(
                    bubble, (right_x - meta_rect.width, 4), meta, constants.GOLD_DIM
                )

            for i, line in enumerate(lines):
                constants.FONT_BODY.render_to(
                    bubble, (pad + 4, header_h + pad + i * self.line_h), line, constants.WHITE
                )
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, dest_w - 16, total_h)
        elif e.is_error:
            bubble = pygame.Surface((dest_w - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (40, 10, 10, 200), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(
                bubble, (*constants.ERROR_RED, 160), bubble.get_rect(), 1, border_radius=6
            )
            for i, line in enumerate(lines):
                constants.FONT_BODY.render_to(
                    bubble, (pad, pad + i * self.line_h), line, (220, 100, 80)
                )
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, dest_w - 16, total_h)
        else:
            # Agent dialogue bubble — with emote rendering
            info = AGENTS.get(e.agent, {})
            agent_color = info.get("color", constants.GOLD)
            bubble = pygame.Surface((dest_w - 16, total_h), pygame.SRCALPHA)
            pygame.draw.rect(bubble, (20, 16, 8, 180), bubble.get_rect(), border_radius=6)
            pygame.draw.rect(bubble, (*agent_color, 80), bubble.get_rect(), 1, border_radius=6)
            hdr = f"{e.agent.upper()} — {info.get('title', '')}"
            constants.FONT_AGENT.render_to(bubble, (pad, 3), hdr, agent_color)

            # Metadata and timestamp — right-aligned with measured widths so
            # both stay on-screen when the font scales up at higher zoom.
            bubble_inner_right = (dest_w - 16) - pad
            right_x = bubble_inner_right
            if self.show_timestamps:
                ts = self.get_timestamp_text(e, self.timestamp_format)
                ts_rect = constants.FONT_TITLE.get_rect(ts)
                right_x -= ts_rect.width
                constants.FONT_TITLE.render_to(bubble, (right_x, 4), ts, constants.GOLD_DIM)
                right_x -= 8  # gap between ts and metadata
            if self.show_metadata and e.metadata_visible:
                meta = self.get_metadata_text(e)
                meta_rect = constants.FONT_TITLE.get_rect(meta)
                constants.FONT_TITLE.render_to(
                    bubble, (right_x - meta_rect.width, 4), meta, constants.GOLD_DIM
                )

            oblique = _is_quoted_dialogue(e.text)
            for i, line in enumerate(lines):
                dim = min(i * 8, 40)
                base_col = tuple(max(0, c - dim) for c in constants.WHITE)
                self._draw_line_with_emotes(
                    bubble,
                    pad,
                    header_h + pad + i * self.line_h,
                    line,
                    base_col,
                    oblique=oblique,
                )
            surf.blit(bubble, (8, y))
            drawn_rect = pygame.Rect(8, y, dest_w - 16, total_h)

        return drawn_rect

    def _draw_line_with_emotes(
        self,
        surf: pygame.Surface,
        x: int,
        y: int,
        line: str,
        base_col: tuple,
        *,
        oblique: bool = False,
    ) -> None:
        """Render a line with *emote* spans in dim gold italic.

        When ``oblique`` is true the body text is rendered with
        ``pygame.freetype.STYLE_OBLIQUE`` — the agent's SYSTEM_PROMPT
        wraps player-directed dialogue in double quotes and the host
        italicizes those lines so they read as speech against the plain
        status stream. ``*emote*`` spans keep their existing dim-gold
        treatment regardless.
        """
        parts = _EMOTE_RE.split(line)
        cursor_x = x
        is_emote = False
        body_style = pygame.freetype.STYLE_OBLIQUE if oblique else pygame.freetype.STYLE_DEFAULT
        for part in parts:
            if not part:
                is_emote = not is_emote
                continue
            if is_emote:
                text = f"*{part}*"
                col = (*constants.GOLD_DIM, 180)
                rect = constants.FONT_AGENT.render_to(surf, (cursor_x, y + 2), text, col)
            else:
                rect = constants.FONT_BODY.render_to(
                    surf, (cursor_x, y), part, base_col, style=body_style
                )
            cursor_x += rect.width + 1
            is_emote = not is_emote

    def draw(self, surf: pygame.Surface, dest_rect: pygame.Rect) -> None:
        # Re-render whenever system messages are still fading
        if any(e.is_system and self._system_alpha(e) > 0.0 for e in self._entries):
            self._dirty = True

        if self._dirty:
            self._render(dest_rect)
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
                surf,
                constants.SCROLLBAR,
                pygame.Rect(dest_rect.right - 4, bar_y, 3, bar_h),
                border_radius=2,
            )

    def toggle_timestamps(self) -> None:
        """Toggle timestamp visibility."""
        self.show_timestamps = not self.show_timestamps
        self._dirty = True

    def toggle_metadata(self) -> None:
        """Toggle metadata visibility."""
        self.show_metadata = not self.show_metadata
        self._dirty = True

    def set_timestamp_format(self, fmt: str) -> None:
        """Set timestamp format (12h or 24h)."""
        self.timestamp_format = fmt
        self._dirty = True

    def get_timestamp_text(self, entry: DialogueEntry, fmt: str = "24h") -> str:
        """Get formatted timestamp for entry."""
        import datetime

        dt = datetime.datetime.fromtimestamp(entry.get_display_timestamp())
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
    screen_w = surf.get_width()
    dialogue_w = screen_w - constants.DIALOGUE_X
    r = pygame.Rect(constants.DIALOGUE_X, 0, dialogue_w, 32)
    pygame.draw.rect(surf, (10, 8, 5), r)
    pygame.draw.line(surf, constants.GOLD_DIM, (constants.DIALOGUE_X, 32), (screen_w, 32), 1)

    title = "KOURAI KHRYSEAI  —  Golden Maidens"
    constants.FONT_AGENT.render_to(surf, (constants.DIALOGUE_X + 12, 8), title, constants.GOLD)

    status_text = "connected" if connected else "connecting..."
    status_col = (100, 180, 100) if connected else constants.GOLD_DIM
    sr = constants.FONT_BANNER.get_rect(status_text)
    constants.FONT_BANNER.render_to(surf, (screen_w - sr.width - 12, 10), status_text, status_col)
