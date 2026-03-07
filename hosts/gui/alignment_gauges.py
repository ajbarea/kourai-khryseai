"""Alignment gauge overlay for Kourai Khryseai GUI.

Renders dual Sovereignty (red) / Devotion (blue) gauges in a compact
panel that can be toggled from the UI. Shows current values, archetype,
and visual bar fills.
"""

from __future__ import annotations

import pygame

from hosts.gui.constants import (
    FONT_AGENT,
    FONT_BODY,
    FONT_NAME,
    theme,
)

# Alignment-specific colors
SOV_RED = (200, 50, 50)
SOV_RED_BRIGHT = (255, 80, 80)
SOV_RED_DIM = (120, 30, 30)
DEV_BLUE = (60, 120, 200)
DEV_BLUE_BRIGHT = (80, 160, 255)
DEV_BLUE_DIM = (30, 60, 120)
COMMANDER_PURPLE = (140, 80, 200)
COMMANDER_GOLD = (218, 180, 60)

PANEL_W = 280
PANEL_H = 200
GAUGE_H = 20
GAUGE_W = 220
GAUGE_PAD = 12
CORNER_R = 8


class AlignmentGaugePanel:
    """Compact alignment gauge overlay showing Sovereignty and Devotion bars.

    Positioned in the top-left corner above the portrait panel.
    Toggleable with a hotkey or button.
    """

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.active = False
        self.alpha = 0.0

        # Position: top-left, below banner
        self.panel_rect = pygame.Rect(8, 40, PANEL_W, PANEL_H)

        # Cached values (updated externally)
        self.sovereignty = 0
        self.devotion = 0
        self.archetype = "professional"

        # Animation targets for smooth gauge fills
        self._sov_display = 0.0
        self._dev_display = 0.0

    def update_layout(self, screen_w: int, screen_h: int) -> None:
        """Track the current window size for future layout decisions."""

        self.screen_w = screen_w
        self.screen_h = screen_h

    def toggle(self) -> None:
        self.active = not self.active

    def update_values(self, sovereignty: int, devotion: int, archetype: str) -> None:
        """Update gauge values (call from main loop when profile changes)."""
        self.sovereignty = sovereignty
        self.devotion = devotion
        self.archetype = archetype

    def update(self, dt: float) -> None:
        # Fade animation
        target_alpha = 255.0 if self.active else 0.0
        self.alpha += (target_alpha - self.alpha) * min(dt * 8, 1.0)

        # Smooth gauge fill animation
        sov_target = float(self.sovereignty)
        dev_target = float(self.devotion)
        lerp_speed = min(dt * 3.0, 1.0)
        self._sov_display += (sov_target - self._sov_display) * lerp_speed
        self._dev_display += (dev_target - self._dev_display) * lerp_speed

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active or self.alpha < 10:
            return False
        # Consume clicks inside the panel to prevent pass-through
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.panel_rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if self.alpha <= 1.0:
            return

        alpha_int = int(self.alpha)
        panel_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)

        # Panel background
        bg_color = (*theme.panel_bg, min(alpha_int, 230))
        pygame.draw.rect(panel_surf, bg_color, (0, 0, PANEL_W, PANEL_H), border_radius=CORNER_R)

        # Border
        border_color = (*theme.gold_dim, min(alpha_int, 180))
        pygame.draw.rect(
            panel_surf, border_color, (0, 0, PANEL_W, PANEL_H), width=1, border_radius=CORNER_R
        )

        y = GAUGE_PAD

        # Title
        title_color = (*theme.gold, alpha_int)
        FONT_NAME.render_to(panel_surf, (GAUGE_PAD, y), "⚖ Alignment", title_color)
        y += 28

        # Sovereignty gauge
        self._draw_gauge(
            panel_surf,
            y,
            "🔴 Sovereignty",
            self._sov_display,
            SOV_RED,
            SOV_RED_BRIGHT,
            SOV_RED_DIM,
            alpha_int,
        )
        y += GAUGE_H + 24

        # Devotion gauge
        self._draw_gauge(
            panel_surf,
            y,
            "🔵 Devotion",
            self._dev_display,
            DEV_BLUE,
            DEV_BLUE_BRIGHT,
            DEV_BLUE_DIM,
            alpha_int,
        )
        y += GAUGE_H + 24

        # Archetype label
        archetype_text = self.archetype.title()
        if self.sovereignty >= 80 and self.devotion >= 80:
            arch_color = (*COMMANDER_PURPLE, alpha_int)
            archetype_text = f"👑 {archetype_text}"
        elif self.sovereignty >= 60:
            arch_color = (*SOV_RED, alpha_int)
        elif self.devotion >= 60:
            arch_color = (*DEV_BLUE, alpha_int)
        else:
            arch_color = (*theme.dim_white, alpha_int)

        FONT_BODY.render_to(panel_surf, (GAUGE_PAD, y), archetype_text, arch_color)

        screen.blit(panel_surf, self.panel_rect.topleft)

    def _draw_gauge(
        self,
        surf: pygame.Surface,
        y: int,
        label: str,
        value: float,
        color: tuple[int, int, int],
        bright: tuple[int, int, int],
        dim: tuple[int, int, int],
        alpha: int,
    ) -> None:
        """Draw a single gauge bar with label and value."""
        x = GAUGE_PAD

        # Label
        label_color = (*theme.white, alpha)
        FONT_AGENT.render_to(surf, (x, y), label, label_color)

        # Value text
        val_text = f"{int(value)}/100"
        val_color = (*bright, alpha)
        FONT_AGENT.render_to(surf, (PANEL_W - GAUGE_PAD - 40, y), val_text, val_color)

        y += 16

        # Background track
        track_rect = pygame.Rect(x, y, GAUGE_W, GAUGE_H)
        track_color = (*dim, min(alpha, 80))
        pygame.draw.rect(surf, track_color, track_rect, border_radius=4)

        # Fill bar
        fill_w = int(GAUGE_W * (value / 100.0))
        if fill_w > 0:
            fill_rect = pygame.Rect(x, y, fill_w, GAUGE_H)
            fill_color = (*color, min(alpha, 200))
            pygame.draw.rect(surf, fill_color, fill_rect, border_radius=4)

            # Bright edge highlight
            if fill_w > 2:
                edge_rect = pygame.Rect(x + fill_w - 2, y, 2, GAUGE_H)
                edge_color = (*bright, min(alpha, 255))
                pygame.draw.rect(surf, edge_color, edge_rect)
