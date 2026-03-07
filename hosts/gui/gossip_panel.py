"""Gossip side panel for Kourai Khryseai GUI.

Renders an animated overlay panel showing gossip conversations between
idle agents. Displays messages as dialogue bubbles with clickable response
options when available.
"""

from __future__ import annotations

from typing import Protocol

import pygame

from hosts.gui.constants import (
    FONT_AGENT,
    FONT_BODY,
    FONT_NAME,
    theme,
)

# Gossip panel layout
GOSSIP_PANEL_W = 340
GOSSIP_PAD = 10
GOSSIP_MSG_PAD = 8
GOSSIP_BUBBLE_R = 6
OPTION_H = 36
OPTION_PAD = 4


class _WrapFont(Protocol):
    def get_rect(self, *args: object, **kwargs: object) -> pygame.Rect: ...


class GossipMessage:
    """A rendered gossip message for display."""

    def __init__(self, agent_name: str, text: str, is_player: bool = False) -> None:
        self.agent_name = agent_name
        self.text = text
        self.is_player = is_player
        self.alpha = 0.0  # Fade-in animation


class GossipResponseButton:
    """A clickable response option in the gossip panel."""

    def __init__(self, index: int, emoji: str, label: str, preview: str) -> None:
        self.index = index
        self.emoji = emoji
        self.label = label
        self.preview = preview
        self.rect = pygame.Rect(0, 0, 0, 0)  # Set during draw
        self.hovered = False


class GossipPanel:
    """Collapsible gossip side panel overlay.

    Slides in from the right edge when a gossip session is active.
    Shows agent dialogue bubbles and clickable response options.
    """

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.active = False
        self.slide_x = 0.0  # 0.0 = hidden, 1.0 = fully visible

        self.messages: list[GossipMessage] = []
        self.response_buttons: list[GossipResponseButton] = []
        self.selected_response: int | None = None  # Index of clicked response

        # Scroll state
        self._scroll_y = 0.0
        self._content_h = 0.0

        # Header agents
        self.agent_a = ""
        self.agent_b = ""
        self.is_complete = False

        # Panel rect (right-aligned)
        self._update_rect()

    def _update_rect(self) -> None:
        self.panel_rect = pygame.Rect(
            self.screen_w - GOSSIP_PANEL_W, 40, GOSSIP_PANEL_W, self.screen_h - 120
        )

    def start_session(self, agent_a: str, agent_b: str) -> None:
        """Begin a new gossip session display."""
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.messages.clear()
        self.response_buttons.clear()
        self.selected_response = None
        self.is_complete = False
        self.active = True
        self._scroll_y = 0.0

    def add_message(self, agent_name: str, text: str, is_player: bool = False) -> None:
        """Add a gossip message to the panel."""
        msg = GossipMessage(agent_name, text, is_player)
        self.messages.append(msg)
        # Auto-scroll to bottom
        self._scroll_y = max(0, self._content_h - self.panel_rect.height + 100)

    def set_response_options(self, options: list[dict[str, str]]) -> None:
        """Set clickable response options.

        Args:
            options: List of dicts with 'emoji', 'label', 'preview' keys.
        """
        self.response_buttons.clear()
        self.selected_response = None
        for i, opt in enumerate(options):
            btn = GossipResponseButton(
                index=i,
                emoji=opt.get("emoji", "💬"),
                label=opt.get("label", "Respond"),
                preview=opt.get("preview", ""),
            )
            self.response_buttons.append(btn)

    def end_session(self) -> None:
        """Mark the gossip session as complete."""
        self.is_complete = True
        self.response_buttons.clear()

    def dismiss(self) -> None:
        """Hide the panel."""
        self.active = False

    def update(self, dt: float) -> None:
        # Slide animation
        target = 1.0 if self.active else 0.0
        self.slide_x += (target - self.slide_x) * min(dt * 6.0, 1.0)

        # Message fade-in
        for msg in self.messages:
            if msg.alpha < 255.0:
                msg.alpha = min(255.0, msg.alpha + dt * 600)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.slide_x < 0.1:
            return False

        # Calculate actual panel position (may be sliding)
        offset_x = int((1.0 - self.slide_x) * GOSSIP_PANEL_W)
        actual_rect = self.panel_rect.move(offset_x, 0)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if actual_rect.collidepoint(event.pos):
                # Check response buttons
                for btn in self.response_buttons:
                    if btn.rect.collidepoint(event.pos):
                        self.selected_response = btn.index
                        return True
                return True  # Consume click inside panel

        if event.type == pygame.MOUSEMOTION:
            for btn in self.response_buttons:
                btn.hovered = btn.rect.collidepoint(event.pos)

        # Scroll inside panel
        if event.type == pygame.MOUSEWHEEL and actual_rect.collidepoint(pygame.mouse.get_pos()):
            self._scroll_y = max(0, self._scroll_y - event.y * 30)
            return True

        return False

    def get_selected_response(self) -> int | None:
        """Return and clear the selected response index, or None."""
        idx = self.selected_response
        self.selected_response = None
        return idx

    def draw(self, screen: pygame.Surface) -> None:
        if self.slide_x <= 0.01:
            return

        alpha_int = int(self.slide_x * 255)
        offset_x = int((1.0 - self.slide_x) * GOSSIP_PANEL_W)

        panel_surf = pygame.Surface((GOSSIP_PANEL_W, self.panel_rect.height), pygame.SRCALPHA)

        # Background
        bg_color = (*theme.panel_bg, min(alpha_int, 235))
        pygame.draw.rect(
            panel_surf,
            bg_color,
            (0, 0, GOSSIP_PANEL_W, self.panel_rect.height),
            border_radius=8,
        )

        # Border
        border_color = (*theme.gold_dim, min(alpha_int, 150))
        pygame.draw.rect(
            panel_surf,
            border_color,
            (0, 0, GOSSIP_PANEL_W, self.panel_rect.height),
            width=1,
            border_radius=8,
        )

        y = GOSSIP_PAD

        # Header
        header = f"💬 {self.agent_a.title()} & {self.agent_b.title()}"
        header_color = (*theme.gold, alpha_int)
        FONT_NAME.render_to(panel_surf, (GOSSIP_PAD, y), header, header_color)
        y += 28

        if self.is_complete:
            status_color = (*theme.dim_white, alpha_int)
            FONT_AGENT.render_to(panel_surf, (GOSSIP_PAD, y), "Session ended", status_color)
            y += 20

        # Separator
        sep_color = (*theme.gold_dim, min(alpha_int, 80))
        pygame.draw.line(panel_surf, sep_color, (GOSSIP_PAD, y), (GOSSIP_PANEL_W - GOSSIP_PAD, y))
        y += 8

        # Messages area (scrollable)
        msg_area_h = self.panel_rect.height - y - self._options_height() - 20
        msg_clip = pygame.Rect(0, y, GOSSIP_PANEL_W, msg_area_h)

        # Render messages
        msg_y = -self._scroll_y
        for msg in self.messages:
            msg_alpha = int(min(msg.alpha, float(alpha_int)))
            if msg_alpha <= 0:
                continue

            bubble_y = y + msg_y
            bubble_h = self._draw_message(panel_surf, int(bubble_y), msg, msg_alpha, msg_clip)
            msg_y += bubble_h + GOSSIP_MSG_PAD

        self._content_h = msg_y + self._scroll_y

        # Response options (below messages)
        options_y = self.panel_rect.height - self._options_height() - GOSSIP_PAD
        actual_x = self.panel_rect.x + offset_x
        for btn in self.response_buttons:
            btn_h = self._draw_option_button(panel_surf, options_y, btn, alpha_int, actual_x)
            options_y += btn_h + OPTION_PAD

        screen.blit(panel_surf, (self.panel_rect.x + offset_x, self.panel_rect.y))

    def _draw_message(
        self,
        surf: pygame.Surface,
        y: int,
        msg: GossipMessage,
        alpha: int,
        clip: pygame.Rect,
    ) -> int:
        """Draw a single gossip message bubble. Returns total height."""
        if y + 40 < clip.y or y > clip.y + clip.height:
            return 40  # Off-screen, return estimated height

        x = GOSSIP_PAD
        max_w = GOSSIP_PANEL_W - GOSSIP_PAD * 2

        # Agent name
        if msg.is_player:
            name_color = (*theme.gold_bright, alpha)
            name = "You"
        else:
            name_color = (*theme.gold, alpha)
            name = msg.agent_name.title()

        FONT_AGENT.render_to(surf, (x, y), name, name_color)
        y += 16

        # Message text (word-wrapped)
        text_color = (*theme.white, alpha)
        lines = _word_wrap(msg.text, FONT_BODY, max_w - 8)
        for line in lines:
            FONT_BODY.render_to(surf, (x + 4, y), line, text_color)
            y += 18

        return 16 + len(lines) * 18 + 4

    def _draw_option_button(
        self,
        surf: pygame.Surface,
        y: int,
        btn: GossipResponseButton,
        alpha: int,
        actual_x: int,
    ) -> int:
        """Draw a clickable response option. Returns height."""
        x = GOSSIP_PAD
        w = GOSSIP_PANEL_W - GOSSIP_PAD * 2
        h = OPTION_H

        # Update hit rect in screen coordinates
        btn.rect = pygame.Rect(actual_x + x, self.panel_rect.y + y, w, h)

        # Background
        if btn.hovered:
            bg_color = (*theme.gold_dim, min(alpha, 100))
        else:
            bg_color = (*theme.panel_bg, min(alpha, 150))
        pygame.draw.rect(surf, bg_color, (x, y, w, h), border_radius=4)

        # Border
        border_color = (*theme.gold_dim, min(alpha, 120))
        pygame.draw.rect(surf, border_color, (x, y, w, h), width=1, border_radius=4)

        # Text
        label_text = f"{btn.emoji} {btn.label}"
        label_color = (*theme.gold, alpha)
        FONT_BODY.render_to(surf, (x + 8, y + 10), label_text, label_color)

        return h

    def _options_height(self) -> int:
        """Calculate total height needed for response options."""
        if not self.response_buttons:
            return 0
        return len(self.response_buttons) * (OPTION_H + OPTION_PAD) + GOSSIP_PAD


def _word_wrap(text: str, font: _WrapFont, max_width: int) -> list[str]:
    """Simple word-wrap for pygame freetype fonts."""
    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        rect = font.get_rect(test_line)
        if rect.width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines or [""]
