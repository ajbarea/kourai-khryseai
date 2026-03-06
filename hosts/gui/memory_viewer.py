"""Memory viewer panel for Kourai Khryseai GUI.

A scrollable overlay that displays player memories, affinity tiers,
alignment history, active romances, and achievements. Includes
export/import controls and memory management.

Opened via F4 hotkey or from the settings panel.
"""

from __future__ import annotations

import pygame

from hosts.gui.constants import (
    FONT_AGENT,
    FONT_BODY,
    FONT_NAME,
    theme,
)

PANEL_W = 600
PANEL_H = 520
SECTION_PAD = 16
LINE_H = 20
CORNER_R = 10

# Affinity tier colors
TIER_COLORS = {
    "stranger": (120, 120, 120),
    "acquaintance": (160, 160, 100),
    "companion": (100, 180, 100),
    "bonded": (200, 160, 60),
}

# Romance stage colors
ROMANCE_COLORS = {
    "none": (120, 120, 120),
    "spark": (255, 180, 100),
    "kindling": (255, 140, 80),
    "flame": (255, 80, 60),
    "bonfire": (255, 50, 30),
}


class MemoryViewerPanel:
    """Scrollable overlay panel for viewing player state and memories.

    Displays:
      - Player identity summary
      - Per-agent affinity tiers
      - Active romances
      - Recent memories (last 20)
      - Achievements (unlocked)
      - Export/Import buttons (placeholder)
    """

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.active = False
        self.alpha = 0.0

        self.panel_rect = pygame.Rect(
            (screen_w - PANEL_W) // 2,
            (screen_h - PANEL_H) // 2,
            PANEL_W,
            PANEL_H,
        )

        # Cached data (refreshed when panel opens)
        self._profile_data: dict | None = None
        self._affinities: dict[str, dict] = {}
        self._memories: list[dict] = []
        self._achievements: list[dict] = []
        self._romances: list[dict] = []

        # Scroll
        self._scroll_y = 0.0
        self._content_h = 0.0

    def toggle(self) -> None:
        self.active = not self.active
        if self.active:
            self._refresh_data()
            self._scroll_y = 0.0

    def _refresh_data(self) -> None:
        """Load current player data for display."""
        try:
            from kourai_common.player import (
                get_active_romances,
                get_all_affinities,
                get_memories,
                load_profile,
            )

            profile = load_profile()
            self._profile_data = {
                "display_name": profile.display_name,
                "tts_name": profile.tts_name,
                "title": profile.title,
                "role": profile.role,
                "pronouns": profile.pronouns,
                "sovereignty": profile.sovereignty,
                "devotion": profile.devotion,
                "total_sessions": profile.total_sessions,
            }
            self._affinities = get_all_affinities(profile.player_id)
            self._memories = get_memories(profile.player_id, limit=20)
            self._romances = get_active_romances(profile.player_id)
        except Exception:
            self._profile_data = None
            self._affinities = {}
            self._memories = []
            self._romances = []

        try:
            from kourai_common.achievements import get_achievement_progress

            if self._profile_data:
                from kourai_common.player import load_profile

                profile = load_profile()
                self._achievements = [
                    a for a in get_achievement_progress(profile) if a.get("unlocked")
                ]
        except Exception:
            self._achievements = []

    def update(self, dt: float) -> None:
        target = 255.0 if self.active else 0.0
        self.alpha += (target - self.alpha) * min(dt * 8, 1.0)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active or self.alpha < 10:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.panel_rect.collidepoint(event.pos):
                return True
            # Click outside to close
            self.active = False
            return True

        if event.type == pygame.MOUSEWHEEL and self.panel_rect.collidepoint(pygame.mouse.get_pos()):
            self._scroll_y = max(0, self._scroll_y - event.y * 30)
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.active = False
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if self.alpha <= 1.0:
            return

        alpha_int = int(self.alpha)

        # Dim backdrop
        dim = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, min(alpha_int, 140)))
        screen.blit(dim, (0, 0))

        # Scrollable content surface (larger than panel for scroll)
        content_h = max(PANEL_H, int(self._content_h) + 40)
        content_surf = pygame.Surface((PANEL_W, content_h), pygame.SRCALPHA)

        # Panel background
        bg = (*theme.panel_bg, min(alpha_int, 240))
        pygame.draw.rect(content_surf, bg, (0, 0, PANEL_W, content_h), border_radius=CORNER_R)

        y = SECTION_PAD
        y = self._draw_identity_section(content_surf, y, alpha_int)
        y = self._draw_affinities_section(content_surf, y, alpha_int)
        y = self._draw_romances_section(content_surf, y, alpha_int)
        y = self._draw_memories_section(content_surf, y, alpha_int)
        y = self._draw_achievements_section(content_surf, y, alpha_int)

        self._content_h = y

        # Clip and blit with scroll offset
        visible_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        visible_surf.blit(content_surf, (0, -self._scroll_y))

        # Border on visible surface
        border = (*theme.gold, min(alpha_int, 150))
        pygame.draw.rect(
            visible_surf, border, (0, 0, PANEL_W, PANEL_H), width=2, border_radius=CORNER_R
        )

        screen.blit(visible_surf, self.panel_rect.topleft)

    def _draw_identity_section(self, surf: pygame.Surface, y: int, alpha: int) -> int:
        """Draw player identity summary."""
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (SECTION_PAD, y), "📋 Player Identity", title_color)
        y += 28

        if not self._profile_data:
            dim_color = (*theme.dim_white, alpha)
            FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), "No profile found", dim_color)
            return y + LINE_H + SECTION_PAD

        p = self._profile_data
        text_color = (*theme.white, alpha)
        dim_color = (*theme.dim_white, alpha)

        name_line = f"Name: {p['display_name']}"
        if p["tts_name"] != p["display_name"]:
            name_line += f"  (TTS: {p['tts_name']})"
        FONT_BODY.render_to(surf, (SECTION_PAD + 8, y), name_line, text_color)
        y += LINE_H

        if p["title"]:
            FONT_BODY.render_to(surf, (SECTION_PAD + 8, y), f"Title: {p['title']}", text_color)
            y += LINE_H

        info_line = f"Role: {p['role']}  •  Pronouns: {p['pronouns'] or 'not set'}"
        FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), info_line, dim_color)
        y += LINE_H

        sov_line = f"🔴 Sovereignty: {p['sovereignty']}/100    🔵 Devotion: {p['devotion']}/100"
        FONT_BODY.render_to(surf, (SECTION_PAD + 8, y), sov_line, text_color)
        y += LINE_H

        sessions_line = f"Sessions: {p['total_sessions']}"
        FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), sessions_line, dim_color)
        y += LINE_H + SECTION_PAD

        return y

    def _draw_affinities_section(self, surf: pygame.Surface, y: int, alpha: int) -> int:
        """Draw per-agent affinity tiers."""
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (SECTION_PAD, y), "💛 Agent Affinities", title_color)
        y += 28

        if not self._affinities:
            dim_color = (*theme.dim_white, alpha)
            FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), "No interactions yet", dim_color)
            return y + LINE_H + SECTION_PAD

        for agent_name, data in sorted(self._affinities.items()):
            score = data.get("affinity_score", 0.0)
            count = data.get("interaction_count", 0)
            tier = self._score_to_tier(score)
            tier_color = TIER_COLORS.get(tier, (160, 160, 160))

            name_color = (*theme.white, alpha)
            FONT_BODY.render_to(surf, (SECTION_PAD + 8, y), f"{agent_name.title()}", name_color)

            tier_c = (*tier_color, alpha)
            FONT_AGENT.render_to(
                surf,
                (SECTION_PAD + 120, y + 2),
                f"{tier.title()} ({score:.0%}) — {count} interactions",
                tier_c,
            )
            y += LINE_H

        y += SECTION_PAD
        return y

    def _draw_romances_section(self, surf: pygame.Surface, y: int, alpha: int) -> int:
        """Draw active romances."""
        if not self._romances:
            return y

        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (SECTION_PAD, y), "💕 Romances", title_color)
        y += 28

        for rom in self._romances:
            agent = rom.get("agent_name", "unknown")
            stage = rom.get("romance_stage", "none")
            stage_color = ROMANCE_COLORS.get(stage, (160, 160, 160))

            name_color = (*theme.white, alpha)
            FONT_BODY.render_to(surf, (SECTION_PAD + 8, y), f"💕 {agent.title()}", name_color)

            sc = (*stage_color, alpha)
            FONT_AGENT.render_to(surf, (SECTION_PAD + 140, y + 2), stage.title(), sc)
            y += LINE_H

        y += SECTION_PAD
        return y

    def _draw_memories_section(self, surf: pygame.Surface, y: int, alpha: int) -> int:
        """Draw recent player memories."""
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (SECTION_PAD, y), "🧠 Recent Memories", title_color)
        y += 28

        if not self._memories:
            dim_color = (*theme.dim_white, alpha)
            FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), "No memories yet", dim_color)
            return y + LINE_H + SECTION_PAD

        for mem in self._memories[:15]:
            content = mem.get("content", "")
            agent = mem.get("agent_name", "system")
            category = mem.get("category", "")

            # Truncate long memories
            if len(content) > 60:
                content = content[:57] + "..."

            prefix_color = (*theme.gold_dim, alpha)
            text_color = (*theme.white, alpha)

            prefix = f"[{agent}·{category}]"
            FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), prefix, prefix_color)
            FONT_AGENT.render_to(
                surf, (SECTION_PAD + 8 + len(prefix) * 7, y), f" {content}", text_color
            )
            y += LINE_H

        y += SECTION_PAD
        return y

    def _draw_achievements_section(self, surf: pygame.Surface, y: int, alpha: int) -> int:
        """Draw unlocked achievements."""
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (SECTION_PAD, y), "🏆 Achievements", title_color)
        y += 28

        if not self._achievements:
            dim_color = (*theme.dim_white, alpha)
            FONT_AGENT.render_to(surf, (SECTION_PAD + 8, y), "None unlocked yet", dim_color)
            return y + LINE_H + SECTION_PAD

        for ach in self._achievements[:10]:
            name = ach.get("name", "???")
            desc = ach.get("description", "")

            name_color = (*theme.gold, alpha)
            FONT_BODY.render_to(surf, (SECTION_PAD + 8, y), f"✦ {name}", name_color)
            y += LINE_H

            if desc:
                desc_color = (*theme.dim_white, alpha)
                FONT_AGENT.render_to(surf, (SECTION_PAD + 24, y), desc, desc_color)
                y += LINE_H

        y += SECTION_PAD
        return y

    @staticmethod
    def _score_to_tier(score: float) -> str:
        if score >= 0.7:
            return "bonded"
        if score >= 0.4:
            return "companion"
        if score >= 0.15:
            return "acquaintance"
        return "stranger"
