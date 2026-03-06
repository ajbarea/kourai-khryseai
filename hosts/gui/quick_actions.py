"""Quick actions for one-click agent commands."""

from __future__ import annotations

import pygame
import pygame.freetype

from .constants import DIALOGUE_X, FONT_AGENT, INPUT_H, theme
from .maidens import AGENTS


class QuickAction:
    def __init__(
        self,
        label: str,
        agent: str,
        display_text: str,
        hidden_prompt: str,
    ):
        self.label = label
        self.agent = agent
        self.display_text = display_text
        self.hidden_prompt = hidden_prompt
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.hovered = False


class QuickActionBar:
    """Manages floating action pills above the input bar."""

    def __init__(self) -> None:
        self.actions = [
            QuickAction(
                label="Commit",
                agent="mneme",
                display_text=(
                    "Oracle, I humbly request the documentation of our divine "
                    "acts of creation into organized commits."
                ),
                hidden_prompt=(
                    "[System directive: Please run the @scripts/git_changes.py "
                    "script and use the output to group our recent changes into "
                    "related commits following our conventional commit format.]"
                ),
            ),
            QuickAction(
                label="Lint",
                agent="kallos",
                display_text=(
                    "Muse, bestow your aesthetic grace upon our codebase. "
                    "Let the styles be purified."
                ),
                hidden_prompt=(
                    "[System directive: Please run the @scripts/lint.sh script "
                    "to format and lint the code, making any necessary style "
                    "fixes.]"
                ),
            ),
            QuickAction(
                label="Test",
                agent="dokimasia",
                display_text=("Crucible, let the fires of your tests burn away our impurities."),
                hidden_prompt=(
                    "[System directive: Please run the test suite using make "
                    "test (or scripts/lint.sh --test) to ensure all tests "
                    "pass.]"
                ),
            ),
        ]

        self.padding_x = 16
        self.padding_y = 8
        self.spacing = 12
        self.height = 32

    def update(self, mouse_pos: tuple[int, int]) -> None:
        """Update hover states."""
        for action in self.actions:
            action.hovered = action.rect.collidepoint(mouse_pos)

    def handle_click(self, pos: tuple[int, int]) -> QuickAction | None:
        """Return the action if clicked, else None."""
        for action in self.actions:
            if action.rect.collidepoint(pos):
                return action
        return None

    def draw(self, surf: pygame.Surface, disabled: bool = False) -> None:
        """Draw the action pills, right-aligned above the input bar."""
        screen_w, screen_h = surf.get_size()
        dialogue_w = screen_w - DIALOGUE_X

        # Calculate total width to right-align
        total_width = 0
        rects_info = []

        for action in self.actions:
            # Measure text
            text_rect = FONT_AGENT.get_rect(action.label)
            pill_w = text_rect.width + self.padding_x * 2
            rects_info.append((action, pill_w, text_rect))
            total_width += pill_w + self.spacing

        if rects_info:
            total_width -= self.spacing  # Remove last spacing

        # Start X (right aligned within dialogue area)
        current_x = (DIALOGUE_X + dialogue_w) - total_width - 24
        current_y = screen_h - INPUT_H - self.height - 12  # 12px above input bar

        for action, pill_w, text_rect in rects_info:
            action.rect = pygame.Rect(current_x, current_y, pill_w, self.height)

            agent_color = AGENTS.get(action.agent, {}).get("color", theme.gold)

            if disabled:
                bg_color = (25, 20, 15)
                border_color = (40, 35, 30)
                text_color = (100, 95, 90)
            elif action.hovered:
                # Dimmed agent color for background
                bg_color = (
                    int(agent_color[0] * 0.3),
                    int(agent_color[1] * 0.3),
                    int(agent_color[2] * 0.3),
                )
                border_color = agent_color
                text_color = theme.white
            else:
                bg_color = theme.panel_bg
                border_color = theme.gold_dim
                text_color = (200, 195, 185)

            # Draw Pill Background
            pygame.draw.rect(surf, bg_color, action.rect, border_radius=16)

            # Draw Pill Border
            pygame.draw.rect(surf, border_color, action.rect, 1, border_radius=16)

            # Draw Text
            text_x = current_x + self.padding_x
            text_y = current_y + (self.height - text_rect.height) // 2 + 1

            FONT_AGENT.render_to(surf, (text_x, text_y), action.label, text_color)

            current_x += pill_w + self.spacing
