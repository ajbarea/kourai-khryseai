"""Settings widget primitives for Kourai Khryseai Pygame GUI.

Contains the five reusable widget classes used by SettingsOverlay, plus the
freetype init guard shared across the settings module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pygame.freetype

if TYPE_CHECKING:
    from collections.abc import Callable


def _ensure_freetype_ready() -> None:
    """Initialize pygame.freetype on demand for test and app entrypoint safety."""
    if not pygame.freetype.get_init():
        pygame.freetype.init()


class TabButton:
    """A tab button for navigating sections."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
        tab_id: str,
        callback: Callable[[str], None],
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.label = label
        self.tab_id = tab_id
        self.callback = callback
        self.hovered = False
        self.active = False

    def update(self, mouse_pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surf: pygame.Surface, font: pygame.freetype.Font, palette: dict) -> None:
        if self.active:
            bg_color = palette.get("gold", (201, 148, 74))
            text_color = palette.get("bubble_bg", (30, 22, 10))
        elif self.hovered:
            bg_color = (70, 65, 60)
            text_color = palette.get("text", (255, 255, 255))
        else:
            bg_color = (40, 35, 30)
            text_color = palette.get("scrollbar", (160, 155, 145))

        pygame.draw.rect(surf, bg_color, self.rect, border_radius=6)

        text_rect = font.get_rect(self.label)
        font.render_to(
            surf,
            (self.rect.centerx - text_rect.width // 2, self.rect.centery - text_rect.height // 2),
            self.label,
            text_color,
        )

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self.callback(self.tab_id)
            return True
        return False


class VolumeSlider:
    """A horizontal volume slider with gold knob and value label."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        initial_value: float,
        callback: Callable[[float], None],
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.value = max(0.0, min(1.0, initial_value))
        self.callback = callback
        self.dragging = False
        self._knob_radius = height // 2

    def _knob_x(self) -> float:
        usable = self.rect.width - self._knob_radius * 2
        return self.rect.x + self._knob_radius + self.value * usable

    def _value_from_x(self, mx: int) -> float:
        usable = self.rect.width - self._knob_radius * 2
        rel = mx - (self.rect.x + self._knob_radius)
        return max(0.0, min(1.0, rel / max(usable, 1)))

    def draw(self, surf: pygame.Surface, palette: dict) -> None:
        gold = palette.get("gold", (201, 148, 74))
        track_y = self.rect.centery
        # Track background
        pygame.draw.line(
            surf,
            (50, 45, 40),
            (self.rect.x + self._knob_radius, track_y),
            (self.rect.right - self._knob_radius, track_y),
            3,
        )
        # Filled portion
        kx = int(self._knob_x())
        pygame.draw.line(
            surf,
            gold,
            (self.rect.x + self._knob_radius, track_y),
            (kx, track_y),
            3,
        )
        # Knob
        pygame.draw.circle(surf, (255, 255, 255), (kx, track_y), self._knob_radius)
        pygame.draw.circle(surf, gold, (kx, track_y), self._knob_radius, 1)

    def handle_mousedown(self, pos: tuple[int, int]) -> bool:
        # Expand hit area vertically for easier grabbing
        hit = pygame.Rect(self.rect.x, self.rect.y - 6, self.rect.width, self.rect.height + 12)
        if hit.collidepoint(pos):
            self.dragging = True
            self.value = self._value_from_x(pos[0])
            self.callback(self.value)
            return True
        return False

    def handle_mousemotion(self, pos: tuple[int, int]) -> bool:
        if self.dragging:
            self.value = self._value_from_x(pos[0])
            self.callback(self.value)
            return True
        return False

    def handle_mouseup(self) -> None:
        self.dragging = False


class ToggleSwitch:
    """A clean, modern toggle switch."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        initial_state: bool,
        callback: Callable[[bool], None],
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.state = initial_state
        self.callback = callback
        self.anim_t = 1.0 if initial_state else 0.0

    def update(self, dt: float):
        target = 1.0 if self.state else 0.0
        self.anim_t += (target - self.anim_t) * min(dt * 15, 1.0)

    def draw(self, surf: pygame.Surface, palette: dict):
        bg_color = palette.get("gold", (201, 148, 74)) if self.state else (50, 45, 40)
        pygame.draw.rect(surf, bg_color, self.rect, border_radius=self.rect.height // 2)

        # Knob
        knob_radius = self.rect.height // 2 - 2
        knob_x = (
            self.rect.x + 2 + knob_radius + self.anim_t * (self.rect.width - 4 - knob_radius * 2)
        )
        pygame.draw.circle(
            surf, (255, 255, 255), (int(knob_x), self.rect.y + self.rect.height // 2), knob_radius
        )

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self.state = not self.state
            self.callback(self.state)
            return True
        return False


class Button:
    """A simple clickable button."""

    def __init__(
        self, x: int, y: int, width: int, height: int, label: str, callback: Callable[[], None]
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.label = label
        self.callback = callback
        self.hovered = False

    def update(self, mouse_pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surf: pygame.Surface, font: pygame.freetype.Font, palette: dict) -> None:
        # Button background
        bg_color = palette.get("gold", (201, 148, 74)) if self.hovered else (50, 45, 40)
        pygame.draw.rect(surf, bg_color, self.rect, border_radius=6)
        pygame.draw.rect(surf, palette.get("gold", (201, 148, 74)), self.rect, 1, border_radius=6)

        # Button text
        text_color = palette.get("text", (255, 255, 255))
        font.render_to(
            surf, (self.rect.centerx - 20, self.rect.centery - 8), self.label, text_color
        )

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self.callback()
            return True
        return False


class CycleButton:
    """A button that cycles through a list of string options."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        options: list[str],
        initial_value: str,
        callback: Callable[[str], None],
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        if initial_value in options:
            self.index = options.index(initial_value)
        else:
            self.index = 0

        self.callback = callback
        self.hovered = False

    @property
    def value(self) -> str:
        return self.options[self.index]

    @value.setter
    def value(self, val: str) -> None:
        if val in self.options:
            self.index = self.options.index(val)

    def update(self, mouse_pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surf: pygame.Surface, font: pygame.freetype.Font, palette: dict) -> None:
        # Background
        bg_color = palette.get("gold", (201, 148, 74)) if self.hovered else (50, 45, 40)
        pygame.draw.rect(surf, bg_color, self.rect, border_radius=6)

        # Text
        text_color = (
            palette.get("bubble_bg", (30, 22, 10))
            if self.hovered
            else palette.get("text", (255, 255, 255))
        )
        text_rect = font.get_rect(self.value)

        font.render_to(
            surf,
            (self.rect.centerx - text_rect.width // 2, self.rect.centery - text_rect.height // 2),
            self.value,
            text_color,
        )

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self.index = (self.index + 1) % len(self.options)
            self.callback(self.value)
            return True
        return False
