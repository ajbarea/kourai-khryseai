"""Profile selection screen for Kourai Khryseai GUI.

Displayed after the title screen. Shows existing save profiles as clickable
cards and a "New Game" button. Selecting a profile activates it and returns
its ID; "New Game" returns None to trigger the onboarding flow.

Each profile card shows: name, role icon, alignment bars (mini), session count.
"""

from __future__ import annotations

import logging
from typing import Literal

import pygame
import pygame.freetype

from .constants import DARK_BG, GOLD, GOLD_BRIGHT, GOLD_DIM

logger = logging.getLogger(__name__)

# Layout
CARD_W = 480
CARD_H = 80
CARD_PAD = 12
CARD_R = 8
MAX_VISIBLE = 5
NEW_GAME_H = 50

# Colors
SOV_RED = (200, 50, 50)
DEV_BLUE = (60, 120, 200)
CARD_BG = (22, 18, 14)
CARD_HOVER = (35, 28, 20)
CARD_ACTIVE = (45, 35, 22)
DELETE_RED = (180, 50, 40)
DELETE_HOVER = (220, 70, 50)


def run_profile_select(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    profiles: list[dict],
) -> dict | None | Literal[False]:
    """Run the profile selection screen.

    Args:
        screen: Pygame display surface.
        clock: Pygame clock.
        profiles: List of profile summary dicts from ``list_profiles()``.

    Returns:
        The selected profile dict, or ``None`` for "New Game".
        Returns ``False`` if the user quit.
    """
    screen_w, screen_h = screen.get_size()

    name_font = pygame.freetype.SysFont("inter,segoeui,arial", 18)
    detail_font = pygame.freetype.SysFont("inter,segoeui,arial", 12)
    title_font = pygame.freetype.SysFont("inter,segoeui,arial", 26)
    prompt_font = pygame.freetype.SysFont("inter,segoeui,arial", 13)
    btn_font = pygame.freetype.SysFont("inter,segoeui,arial", 16)

    # Sort profiles: active first, then by last_seen descending
    sorted_profiles = sorted(
        profiles,
        key=lambda p: (not p.get("is_active", False), p.get("last_seen", "") or ""),
        reverse=False,
    )

    scroll_offset = 0
    hovered_card = -1
    hovered_new_game = False
    hovered_delete = -1
    fade_in = 0.0
    confirm_delete_idx = -1  # Index of profile pending delete confirmation

    while True:
        dt = clock.tick(60) / 1000.0
        fade_in = min(1.0, fade_in + dt * 3.0)
        alpha = int(fade_in * 255)

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # Escape during delete confirmation cancels it
                if confirm_delete_idx >= 0:
                    confirm_delete_idx = -1
                    continue

            if event.type == pygame.MOUSEMOTION:
                hovered_card = -1
                hovered_new_game = False
                hovered_delete = -1
                mx, my = event.pos
                # Check profile cards
                for i in range(len(sorted_profiles)):
                    card_rect = _card_rect(
                        screen_w, screen_h, i, scroll_offset, len(sorted_profiles)
                    )
                    if card_rect and card_rect.collidepoint(mx, my):
                        # Check if hovering the delete button area (right edge)
                        delete_area = pygame.Rect(
                            card_rect.right - 40, card_rect.y, 40, card_rect.height
                        )
                        if delete_area.collidepoint(mx, my):
                            hovered_delete = i
                        else:
                            hovered_card = i
                        break
                # Check New Game button
                ng_rect = _new_game_rect(screen_w, screen_h, len(sorted_profiles), scroll_offset)
                if ng_rect and ng_rect.collidepoint(mx, my):
                    hovered_new_game = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # Delete confirmation click
                if confirm_delete_idx >= 0:
                    confirm_rect = _confirm_delete_rect(screen_w, screen_h)
                    yes_rect = pygame.Rect(confirm_rect.x + 20, confirm_rect.bottom - 50, 100, 36)
                    no_rect = pygame.Rect(
                        confirm_rect.right - 120, confirm_rect.bottom - 50, 100, 36
                    )
                    if yes_rect.collidepoint(mx, my):
                        # Actually delete
                        profile_to_delete = sorted_profiles[confirm_delete_idx]
                        try:
                            from kourai_common.player import delete_profile

                            delete_profile(profile_to_delete["player_id"])
                        except Exception:
                            logger.debug("Failed to delete profile", exc_info=True)
                        sorted_profiles.pop(confirm_delete_idx)
                        confirm_delete_idx = -1
                        continue
                    if no_rect.collidepoint(mx, my) or not confirm_rect.collidepoint(mx, my):
                        confirm_delete_idx = -1
                        continue
                    continue

                # Check delete button clicks
                for i in range(len(sorted_profiles)):
                    card_rect = _card_rect(
                        screen_w, screen_h, i, scroll_offset, len(sorted_profiles)
                    )
                    if card_rect:
                        delete_area = pygame.Rect(
                            card_rect.right - 40, card_rect.y, 40, card_rect.height
                        )
                        if delete_area.collidepoint(mx, my):
                            confirm_delete_idx = i
                            break

                # Check profile card clicks
                for i in range(len(sorted_profiles)):
                    card_rect = _card_rect(
                        screen_w, screen_h, i, scroll_offset, len(sorted_profiles)
                    )
                    if card_rect and card_rect.collidepoint(mx, my):
                        return sorted_profiles[i]

                # Check New Game button
                ng_rect = _new_game_rect(screen_w, screen_h, len(sorted_profiles), scroll_offset)
                if ng_rect and ng_rect.collidepoint(mx, my):
                    return None

            if event.type == pygame.MOUSEWHEEL:
                max_scroll = max(0, len(sorted_profiles) - MAX_VISIBLE)
                scroll_offset = max(0, min(max_scroll, scroll_offset - event.y))

        # --- Draw ---
        screen.fill(DARK_BG)

        # Title
        title_str = "Select Profile"
        tr = title_font.get_rect(title_str)
        title_font.render_to(
            screen,
            ((screen_w - tr.width) // 2, 60),
            title_str,
            (*GOLD, alpha),
        )

        # Subtitle hint
        hint_str = "Choose your save file or start a new adventure"
        hr = prompt_font.get_rect(hint_str)
        prompt_font.render_to(
            screen,
            ((screen_w - hr.width) // 2, 95),
            hint_str,
            (*GOLD_DIM, min(alpha, 160)),
        )

        # Profile cards
        for i, profile in enumerate(sorted_profiles):
            card_rect = _card_rect(screen_w, screen_h, i, scroll_offset, len(sorted_profiles))
            if not card_rect:
                continue

            is_hovered = hovered_card == i
            is_active = profile.get("is_active", False)
            is_delete_hovered = hovered_delete == i

            _draw_profile_card(
                screen,
                card_rect,
                profile,
                name_font,
                detail_font,
                alpha,
                is_hovered,
                is_active,
                is_delete_hovered,
            )

        # New Game button
        ng_rect = _new_game_rect(screen_w, screen_h, len(sorted_profiles), scroll_offset)
        if ng_rect:
            _draw_new_game_button(screen, ng_rect, btn_font, alpha, hovered_new_game)

        # Delete confirmation overlay
        if confirm_delete_idx >= 0 and confirm_delete_idx < len(sorted_profiles):
            _draw_delete_confirmation(
                screen,
                screen_w,
                screen_h,
                sorted_profiles[confirm_delete_idx],
                btn_font,
                detail_font,
            )

        pygame.display.flip()


def _card_rect(
    screen_w: int,
    screen_h: int,
    index: int,
    scroll_offset: int,
    total: int,
) -> pygame.Rect | None:
    """Calculate the rect for a profile card by index."""
    visible_idx = index - scroll_offset
    if visible_idx < 0 or visible_idx >= MAX_VISIBLE:
        return None

    x = (screen_w - CARD_W) // 2
    start_y = 130
    y = start_y + visible_idx * (CARD_H + CARD_PAD)
    return pygame.Rect(x, y, CARD_W, CARD_H)


def _new_game_rect(
    screen_w: int, screen_h: int, num_profiles: int, scroll_offset: int
) -> pygame.Rect:
    """Calculate the rect for the New Game button."""
    visible_count = min(num_profiles, MAX_VISIBLE)
    start_y = 130
    y = start_y + visible_count * (CARD_H + CARD_PAD) + CARD_PAD
    x = (screen_w - CARD_W) // 2
    return pygame.Rect(x, y, CARD_W, NEW_GAME_H)


def _confirm_delete_rect(screen_w: int, screen_h: int) -> pygame.Rect:
    """Centered confirmation dialog rect."""
    w, h = 340, 160
    return pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)


def _draw_profile_card(
    screen: pygame.Surface,
    rect: pygame.Rect,
    profile: dict,
    name_font: pygame.freetype.Font,
    detail_font: pygame.freetype.Font,
    alpha: int,
    hovered: bool,
    is_active: bool,
    delete_hovered: bool,
) -> None:
    """Draw a single profile card."""
    card_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

    # Background
    if is_active:
        bg = (*CARD_ACTIVE, min(alpha, 220))
    elif hovered:
        bg = (*CARD_HOVER, min(alpha, 220))
    else:
        bg = (*CARD_BG, min(alpha, 200))
    pygame.draw.rect(card_surf, bg, (0, 0, rect.width, rect.height), border_radius=CARD_R)

    # Border (gold for active, dim otherwise)
    if is_active:
        border = (*GOLD, min(alpha, 200))
    else:
        border = (*GOLD_DIM, min(alpha, 100))
    pygame.draw.rect(
        card_surf, border, (0, 0, rect.width, rect.height), width=1, border_radius=CARD_R
    )

    # Role icon
    role = profile.get("role", "mortal")
    icon = {"divine": "⚡", "mortal": "🔨", "devoted": "💛"}.get(role, "👤")

    x, y = 12, 12

    # Name + role icon
    name = profile.get("display_name", "Unknown")
    name_text = f"{icon} {name}"
    name_color = (*GOLD_BRIGHT, alpha) if is_active else (*GOLD, alpha)
    name_font.render_to(card_surf, (x, y), name_text, name_color)

    # Active badge
    if is_active:
        badge_x = x + name_font.get_rect(name_text).width + 12
        detail_font.render_to(card_surf, (badge_x, y + 4), "● ACTIVE", (*GOLD_BRIGHT, alpha))

    y += 26

    # Details line: title, pronouns, sessions
    title = profile.get("title", "")
    pronouns = profile.get("pronouns", "")
    sessions = profile.get("total_sessions", 0)
    parts = []
    if title:
        parts.append(title)
    if pronouns:
        parts.append(pronouns)
    parts.append(f"{sessions} sessions")
    detail_text = "  •  ".join(parts)
    detail_font.render_to(card_surf, (x, y), detail_text, (*GOLD_DIM, min(alpha, 180)))

    y += 18

    # Mini alignment bars
    bar_w = 120
    bar_h = 8
    sov = profile.get("sovereignty", 0)
    dev = profile.get("devotion", 0)

    # Sovereignty bar
    sov_bg = (*SOV_RED, min(alpha, 40))
    sov_fill = (*SOV_RED, min(alpha, 180))
    pygame.draw.rect(card_surf, sov_bg, (x, y, bar_w, bar_h), border_radius=3)
    fill_w = int(bar_w * sov / 100)
    if fill_w > 0:
        pygame.draw.rect(card_surf, sov_fill, (x, y, fill_w, bar_h), border_radius=3)
    detail_font.render_to(card_surf, (x + bar_w + 6, y - 2), f"{sov}", (*SOV_RED, alpha))

    # Devotion bar
    dev_x = x + bar_w + 40
    dev_bg = (*DEV_BLUE, min(alpha, 40))
    dev_fill = (*DEV_BLUE, min(alpha, 180))
    pygame.draw.rect(card_surf, dev_bg, (dev_x, y, bar_w, bar_h), border_radius=3)
    fill_w = int(bar_w * dev / 100)
    if fill_w > 0:
        pygame.draw.rect(card_surf, dev_fill, (dev_x, y, fill_w, bar_h), border_radius=3)
    detail_font.render_to(card_surf, (dev_x + bar_w + 6, y - 2), f"{dev}", (*DEV_BLUE, alpha))

    # Delete button (right edge)
    del_x = rect.width - 36
    del_y = (rect.height - 24) // 2
    if delete_hovered:
        del_color = (*DELETE_HOVER, alpha)
    else:
        del_color = (*DELETE_RED, min(alpha, 100))
    detail_font.render_to(card_surf, (del_x, del_y), "✕", del_color)

    screen.blit(card_surf, rect.topleft)


def _draw_new_game_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    font: pygame.freetype.Font,
    alpha: int,
    hovered: bool,
) -> None:
    """Draw the New Game button."""
    btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

    bg = (*CARD_HOVER, min(alpha, 180)) if hovered else (*CARD_BG, min(alpha, 150))
    pygame.draw.rect(btn_surf, bg, (0, 0, rect.width, rect.height), border_radius=CARD_R)

    border = (*GOLD, min(alpha, 180)) if hovered else (*GOLD_DIM, min(alpha, 120))
    pygame.draw.rect(
        btn_surf, border, (0, 0, rect.width, rect.height), width=1, border_radius=CARD_R
    )

    text = "✦ New Game"
    tr = font.get_rect(text)
    text_color = (*GOLD_BRIGHT, alpha) if hovered else (*GOLD, alpha)
    font.render_to(
        btn_surf,
        ((rect.width - tr.width) // 2, (rect.height - tr.height) // 2),
        text,
        text_color,
    )

    screen.blit(btn_surf, rect.topleft)


def _draw_delete_confirmation(
    screen: pygame.Surface,
    screen_w: int,
    screen_h: int,
    profile: dict,
    btn_font: pygame.freetype.Font,
    detail_font: pygame.freetype.Font,
) -> None:
    """Draw a modal delete confirmation dialog."""
    # Dim backdrop
    dim = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 160))
    screen.blit(dim, (0, 0))

    rect = _confirm_delete_rect(screen_w, screen_h)
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

    # Background
    pygame.draw.rect(panel, (*CARD_BG, 240), (0, 0, rect.width, rect.height), border_radius=10)
    pygame.draw.rect(
        panel, (*DELETE_RED, 180), (0, 0, rect.width, rect.height), width=2, border_radius=10
    )

    # Text
    name = profile.get("display_name", "Unknown")
    btn_font.render_to(panel, (20, 20), "Delete this save?", (*DELETE_RED, 255))
    detail_font.render_to(
        panel, (20, 50), f'"{name}" and all their memories will be lost.', (*GOLD_DIM, 220)
    )
    detail_font.render_to(panel, (20, 70), "This cannot be undone.", (*DELETE_RED, 180))

    # Yes/No buttons
    yes_rect = pygame.Rect(20, rect.height - 50, 100, 36)
    no_rect = pygame.Rect(rect.width - 120, rect.height - 50, 100, 36)

    pygame.draw.rect(panel, (*DELETE_RED, 180), yes_rect, border_radius=6)
    btn_font.render_to(panel, (yes_rect.x + 22, yes_rect.y + 8), "Delete", (*GOLD_BRIGHT, 255))

    pygame.draw.rect(panel, (*GOLD_DIM, 100), no_rect, border_radius=6)
    btn_font.render_to(panel, (no_rect.x + 22, no_rect.y + 8), "Cancel", (*GOLD, 255))

    screen.blit(panel, rect.topleft)
