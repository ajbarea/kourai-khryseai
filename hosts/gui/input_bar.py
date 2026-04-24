"""Text input bar — bottom of the GUI with cursor blink and agent-aware placeholder."""

from __future__ import annotations

import time

import pygame

from .constants import (
    FONT_BODY,
    FONT_INPUT,
    FONT_TITLE,
    GOLD,
    GOLD_DIM,
    INPUT_BG,
    INPUT_H,
    WHITE,
)
from .keyboard_shortcuts import KeyboardShortcuts
from .maidens import AGENTS


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
        self.shortcuts = KeyboardShortcuts()

    def update(self, dt: float) -> None:
        self._blink_acc += dt
        if self._blink_acc >= self.CURSOR_BLINK:
            self._cursor_on = not self._cursor_on
            self._blink_acc = 0.0

    def handle_key(self, event: pygame.event.Event) -> str | None:
        """Handle a KEYDOWN event. Returns the submitted text or None."""
        # Process shortcuts first (Ctrl+K, Ctrl+L, Up/Down arrows)
        action = self.shortcuts.handle_key(event, self.text)
        if action:
            if action["action"] == "focus":
                # Focus is handled by the caller/state, but we acknowledge it
                return None
            elif action["action"] == "clear":
                self.text = ""
                return None
            elif action["action"] == "navigate":
                self.text = action["text"]
                return None

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and not event.mod & pygame.KMOD_SHIFT:
            if self.text.strip() and not self.processing:
                submitted = self.text.strip()
                self.shortcuts.add_message(submitted)
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
        screen_w, screen_h = surf.get_size()
        rect = pygame.Rect(0, screen_h - INPUT_H, screen_w, INPUT_H)
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
            pygame.draw.line(
                surf, pulse_color, (0, screen_h - INPUT_H), (screen_w, screen_h - INPUT_H), 2
            )
        else:
            pygame.draw.line(
                surf, GOLD_DIM, (0, screen_h - INPUT_H), (screen_w, screen_h - INPUT_H), 1
            )

        # Forge mark (left icon)
        FONT_BODY.render_to(surf, (self.PAD, screen_h - INPUT_H + (INPUT_H - 18) // 2), ">", GOLD)

        # Input text area
        text_x = self.PAD + 28
        text_y = screen_h - INPUT_H + (INPUT_H - 18) // 2

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

        # Send hint — right-aligned via measured width so it stays on-screen
        # when FONT_TITLE scales up at higher zoom levels.
        hint = "[Enter] to send" if not (self.processing and not self.waiting_for_agent) else ""
        if hint:
            hint_rect = FONT_TITLE.get_rect(hint)
            FONT_TITLE.render_to(
                surf,
                (
                    screen_w - hint_rect.width - 16,
                    screen_h - INPUT_H + (INPUT_H - hint_rect.height) // 2,
                ),
                hint,
                GOLD_DIM,
            )
