"""Debug log panel — live A2A traffic viewer for full pipeline transparency.

Captures all recv_q events, writes them to logs/gui.log, and renders a
toggleable overlay panel showing timestamped, agent-colored entries.

Tier 3 of the three-tier content system:
  Tier 1 — Dialogue history (the dating sim / RPG experience)
  Tier 2 — Scratchpad (agent reasoning, CoT plans, TODOs)
  Tier 3 — Debug log (raw A2A traffic, connections, routing, errors)
"""

from __future__ import annotations

import datetime
import logging
from collections import deque
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pygame

from .constants import FONT_AGENT, FONT_TITLE, theme
from .maidens import AGENTS

# GUI-side file logger — writes everything the player sees in the debug panel
_LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
_gui_file_logger: logging.Logger | None = None


def _get_file_logger() -> logging.Logger:
    """Lazy-init the gui.log file logger."""
    global _gui_file_logger
    if _gui_file_logger is None:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        _gui_file_logger = logging.getLogger("kourai.gui.debug_log")
        _gui_file_logger.propagate = False
        handler = RotatingFileHandler(
            _LOGS_DIR / "gui.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
        _gui_file_logger.addHandler(handler)
        _gui_file_logger.setLevel(logging.DEBUG)
    return _gui_file_logger


# Event type badges for the panel
_TYPE_LABELS = {
    "connected": "CONN",
    "disconnected": "DISC",
    "status": "A2A",
    "result": "RESULT",
    "complete": "DONE",
    "error": "ERR",
    "user": "SEND",
    "system": "SYS",
}

_TYPE_COLORS = {
    "connected": (100, 200, 100),
    "disconnected": (200, 100, 80),
    "status": None,  # uses agent color
    "result": None,
    "complete": (100, 200, 100),
    "error": (200, 80, 60),
    "user": (180, 180, 180),
    "system": (120, 115, 105),
}


@dataclass
class DebugEntry:
    """A single debug log line."""

    timestamp: float
    event_type: str
    agent: str
    text: str
    wall_time: str = field(init=False)

    def __post_init__(self) -> None:
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        self.wall_time = dt.strftime("%H:%M:%S")


class DebugLog:
    """Captures A2A traffic and renders the debug panel overlay."""

    MAX_ENTRIES = 500
    LINE_H = 16
    PAD = 10

    def __init__(self) -> None:
        self._entries: deque[DebugEntry] = deque(maxlen=self.MAX_ENTRIES)
        self._scroll_y = 0
        self._auto_scroll = True

    # ------------------------------------------------------------------
    # Ingestion — called from the main loop for every recv_q event
    # ------------------------------------------------------------------
    def record(self, event: dict) -> None:
        """Record an A2A event from the recv_q."""
        import time

        etype = event.get("type", "system")
        agent = event.get("agent", "")
        text = event.get("text", "")

        # Extract agent from status text if not explicit
        if not agent and etype == "status":
            from .maidens import detect_agent

            detected, remainder = detect_agent(text)
            if detected:
                agent = detected
                text = remainder

        if etype == "connected":
            agent = "hephaestus"
            text = f"Connected to {event.get('name', 'forge')}"
        elif etype == "disconnected":
            agent = "system"
            text = "Disconnected from forge"
        elif etype == "complete":
            elapsed = event.get("elapsed", 0.0)
            text = f"Pipeline complete in {elapsed:.1f}s"

        entry = DebugEntry(
            timestamp=time.time(),
            event_type=etype,
            agent=agent or "system",
            text=text,
        )
        self._entries.append(entry)

        # Write to logs/gui.log
        log = _get_file_logger()
        log.info("[%s] [%s] %s", etype.upper(), entry.agent, text)

        # Auto-scroll to bottom on new entry
        if self._auto_scroll:
            self._scroll_y = max(0, len(self._entries) * self.LINE_H - 200)

    def record_user(self, agent: str, text: str) -> None:
        """Record an outgoing user message."""
        import time

        entry = DebugEntry(
            timestamp=time.time(),
            event_type="user",
            agent=agent,
            text=f">> {text[:80]}{'...' if len(text) > 80 else ''}",
        )
        self._entries.append(entry)
        _get_file_logger().info("[SEND] [%s] %s", agent, text[:200])

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------
    def scroll(self, dy: int) -> None:
        self._auto_scroll = False
        max_scroll = max(0, len(self._entries) * self.LINE_H - 200)
        self._scroll_y = max(0, min(self._scroll_y + dy, max_scroll))
        # Re-enable auto-scroll if scrolled to bottom
        if self._scroll_y >= max_scroll - self.LINE_H:
            self._auto_scroll = True

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface, dialogue_rect: pygame.Rect) -> None:
        """Render the debug log panel in the top-right of the dialogue area."""
        if not self._entries:
            return

        panel_w = min(520, dialogue_rect.width - 20)
        max_panel_h = int(dialogue_rect.height * 0.45)
        # Content height is entry count * line height + header + padding
        content_h = len(self._entries) * self.LINE_H
        panel_h = min(max_panel_h, content_h + 40)
        panel_h = max(panel_h, 60)

        panel_x = dialogue_rect.right - panel_w - 8
        panel_y = dialogue_rect.top + 8

        # Semi-transparent panel background
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 6, 4, 220), panel.get_rect(), border_radius=6)
        pygame.draw.rect(panel, (*theme.gold_dim, 100), panel.get_rect(), 1, border_radius=6)

        # Header
        FONT_AGENT.render_to(panel, (self.PAD, 6), "DEBUG LOG", theme.gold_dim)
        entry_count = f"{len(self._entries)} events"
        FONT_TITLE.render_to(panel, (panel_w - 80, 8), entry_count, theme.dim_white)
        pygame.draw.line(
            panel,
            (*theme.gold_dim, 80),
            (self.PAD, 22),
            (panel_w - self.PAD, 22),
            1,
        )

        # Scrollable content area
        content_top = 26
        visible_h = panel_h - content_top - 4
        visible_lines = visible_h // self.LINE_H

        # Calculate visible range from scroll position
        total_lines = len(self._entries)
        start_idx = max(0, self._scroll_y // self.LINE_H)
        # Clamp to show the last visible_lines entries if auto-scrolling
        if self._auto_scroll:
            start_idx = max(0, total_lines - visible_lines)
            self._scroll_y = start_idx * self.LINE_H

        end_idx = min(total_lines, start_idx + visible_lines)

        y = content_top
        entries_list = list(self._entries)  # snapshot for thread safety
        for i in range(start_idx, end_idx):
            entry = entries_list[i]
            self._draw_entry(panel, entry, y, panel_w)
            y += self.LINE_H

        # Scrollbar
        if total_lines > visible_lines:
            ratio = visible_lines / total_lines
            bar_h = max(20, int(visible_h * ratio))
            scroll_ratio = start_idx / max(1, total_lines - visible_lines)
            bar_y = content_top + int(scroll_ratio * (visible_h - bar_h))
            pygame.draw.rect(
                panel,
                (*theme.gold_dim, 120),
                pygame.Rect(panel_w - 5, bar_y, 3, bar_h),
                border_radius=2,
            )

        screen.blit(panel, (panel_x, panel_y))

    def _draw_entry(
        self,
        surf: pygame.Surface,
        entry: DebugEntry,
        y: int,
        panel_w: int,
    ) -> None:
        """Render a single debug log line."""
        # Timestamp
        FONT_TITLE.render_to(surf, (self.PAD, y + 2), entry.wall_time, theme.dim_white)

        # Event type badge
        badge = _TYPE_LABELS.get(entry.event_type, entry.event_type[:4].upper())
        badge_color = _TYPE_COLORS.get(entry.event_type)
        if badge_color is None:
            # Use agent color
            agent_info = AGENTS.get(entry.agent, {})
            badge_color = agent_info.get("color", theme.gold_dim)
        FONT_TITLE.render_to(surf, (62, y + 2), badge, badge_color)

        # Agent name (abbreviated)
        agent_info = AGENTS.get(entry.agent, {})
        agent_color = agent_info.get("color", theme.dim_white)
        agent_label = entry.agent[:4].upper()
        FONT_TITLE.render_to(surf, (100, y + 2), agent_label, agent_color)

        # Message text (truncated to fit)
        text_x = 138
        max_text_w = panel_w - text_x - self.PAD
        max_chars = max(1, max_text_w // 7)
        text = entry.text
        if len(text) > max_chars:
            text = text[: max_chars - 3] + "..."
        FONT_TITLE.render_to(surf, (text_x, y + 2), text, theme.dim_white)
