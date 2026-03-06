"""Agent Scratchpad UI overlay.

Provides a persistent view of the current agent's TODO list and reasoning
(Chain-of-Thought) sent back from the forge during task execution.
"""

from __future__ import annotations

import pygame

from .constants import FONT_AGENT, FONT_BODY, theme


class Scratchpad:
    """Overlay panel displaying the selected agent's active plan/TODO list."""

    PAD = 14
    LINE_H = 20

    def __init__(self) -> None:
        self.is_open = False
        self._content_by_agent: dict[str, list[str]] = {}
        self._active_agent = "hephaestus"
        self._scroll_y = 0
        self._rendered_h = 0
        self.rect = pygame.Rect(0, 0, 0, 0)

    def toggle(self) -> None:
        """Toggle the visibility of the scratchpad overlay."""
        self.is_open = not self.is_open

    def set_agent(self, agent: str) -> None:
        """Switch the scratchpad to display a specific agent's context."""
        if self._active_agent != agent:
            self._active_agent = agent
            self._scroll_y = 0

    def append(self, agent: str, text: str) -> None:
        """Append text to an agent's scratchpad."""
        if agent not in self._content_by_agent:
            self._content_by_agent[agent] = []
        self._content_by_agent[agent].append(text)

        # Auto-scroll if currently viewing this agent
        if agent == self._active_agent and self.rect.height > 0:
            self.scroll_to_bottom()

    def clear(self, agent: str) -> None:
        """Clear an agent's scratchpad."""
        if agent in self._content_by_agent:
            self._content_by_agent[agent].clear()
            self._scroll_y = 0

    def scroll(self, dy: int) -> None:
        max_scroll = max(0, self._rendered_h - (self.rect.height - self.PAD * 2 - 40))
        self._scroll_y = max(0, min(self._scroll_y + dy, max_scroll))

    def scroll_to_bottom(self) -> None:
        self._scroll_y = max(0, self._rendered_h - (self.rect.height - self.PAD * 2 - 40))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process mouse events. Returns True if event was consumed."""
        if not self.is_open:
            return False

        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll(-event.y * 40)
            return True

        # Consume clicks inside the overlay so they don't hit underlying UI
        return bool(event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos))

    def draw(self, screen: pygame.Surface, target_rect: pygame.Rect) -> None:
        """Render the scratchpad sliding out over the target area."""
        if not self.is_open:
            return

        self.rect = target_rect

        # Semi-transparent background
        overlay = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (*theme.dark_bg, 240), overlay.get_rect())

        # Right border separating it from the portrait panel (if we draw it fullscreen-ish)
        # Assumes target_rect begins at DIALOGUE_X
        pygame.draw.line(overlay, theme.gold, (0, 0), (0, self.rect.height), 2)

        # Draw Title
        title = f"{self._active_agent.upper()} SCRATCHPAD"
        FONT_AGENT.render_to(overlay, (self.PAD * 2, self.PAD), title, theme.gold)

        pygame.draw.line(
            overlay,
            theme.gold_dim,
            (self.PAD * 2, self.PAD + 25),
            (self.rect.width - self.PAD * 2, self.PAD + 25),
            1,
        )

        content = self._content_by_agent.get(self._active_agent, [])
        if not content:
            msg = "No plans documented yet..."
            FONT_BODY.render_to(overlay, (self.PAD * 2, self.PAD + 40), msg, theme.dim_white)
            screen.blit(overlay, self.rect.topleft)
            return

        # Render text block into an inner surface for scrolling
        text_surf_w = self.rect.width - (self.PAD * 4)

        # Calculate full height of content
        import textwrap

        all_lines = []
        for block in content:
            for paragraph in block.split("\n"):
                wrapped = textwrap.wrap(paragraph or " ", width=max(1, text_surf_w // 9))
                all_lines.extend(wrapped or [" "])
            all_lines.append("")  # spacer between blocks

        self._rendered_h = len(all_lines) * self.LINE_H

        # Create clipping surface
        clip_h = self.rect.height - (self.PAD * 2 + 35)
        clip_rect = pygame.Rect(self.PAD * 2, self.PAD + 30, text_surf_w, clip_h)
        clip_surf = pygame.Surface((clip_rect.width, clip_rect.height), pygame.SRCALPHA)

        # Draw visible text
        start_idx = max(0, self._scroll_y // self.LINE_H)
        max_visible_lines = (clip_h // self.LINE_H) + 2

        for i in range(start_idx, min(len(all_lines), start_idx + max_visible_lines)):
            y_pos = (i * self.LINE_H) - self._scroll_y
            line = all_lines[i]

            # Simple markdown highlighting for bullet points and headers
            color = theme.white
            if line.startswith("- ") or line.startswith("* ") or line.lstrip().startswith("1. "):
                color = theme.dim_white
            elif "[x]" in line or "TODO" in line:
                color = theme.gold

            FONT_BODY.render_to(clip_surf, (0, y_pos + 4), line, color)

        overlay.blit(clip_surf, clip_rect.topleft)

        # Draw Scrollbar
        if self._rendered_h > clip_h:
            ratio = clip_h / self._rendered_h
            bar_h = max(30, int(clip_h * ratio))
            bar_y = clip_rect.top + int((self._scroll_y / self._rendered_h) * clip_h)
            pygame.draw.rect(
                overlay,
                theme.scrollbar,
                pygame.Rect(self.rect.width - self.PAD - 4, bar_y, 4, bar_h),
                border_radius=2,
            )

        screen.blit(overlay, self.rect.topleft)
