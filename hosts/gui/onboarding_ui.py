"""GUI onboarding overlay for Kourai Khryseai.

First-run experience where the player sets up their identity:
- Puck-led intro handoff to the forge
- Focused vs gamified session style
- Metrics consent (affinity / virtues)
- Name entry with TTS pronunciation preview
- Title selection (divine/mortal/custom)
- Pronoun selection
- Welcome greeting from Hephaestus

Built as a full-screen overlay that blocks other UI until complete.
"""

from __future__ import annotations

import pygame

from hosts.gui.constants import (
    FONT_AGENT,
    FONT_BODY,
    FONT_INPUT,
    FONT_NAME,
    theme,
)

# Onboarding steps
STEP_PUCK_INTRO = 0
STEP_MODE = 1
STEP_METRICS = 2
STEP_NAME = 3
STEP_PRONUNCIATION = 4
STEP_TITLE = 5
STEP_PRONOUNS = 6
STEP_WELCOME = 7
STEP_DONE = 8

# Role options (role_id, display_label, description)
ROLE_OPTIONS = [
    ("divine", "As a God among mortals", "Divine honorifics, reverent tone"),
    ("mortal", "As a fellow artisan", "Casual, warm, collaborative"),
    ("hero", "As a proven champion", "Comradely respect, earned trust"),
    ("devoted", "As their beloved master", "Devoted, formal, adoring"),
    ("name_only", "Just by name", "Natural, no special treatment"),
]

# Pronoun options
PRONOUN_OPTIONS = ["he/him", "she/her", "they/them", ""]

EXPERIENCE_OPTIONS = [
    ("focused", "Focused — minimal game mechanics, terminal-first coding flow"),
    ("gamified", "Gamified — full forge systems, relationship progression, and lore"),
]


def _puck_handoff_line(role: str) -> str:
    """Role-sensitive Puck handoff line before meeting Hephaestus."""
    if role in {"divine", "hero"}:
        return "Heh. Royal energy. Try not to grin when the Forge King glares."
    if role in {"mortal", "name_only"}:
        return "Stay behind me a step. He's intimidating, but fair."
    return "Easy now. Hephaestus respects those who can hold steady."


PANEL_W = 600
PANEL_H = 530
BUTTON_W = 260
BUTTON_H = 44
BUTTON_PAD = 8
INPUT_W = 400
INPUT_H = 40


class OnboardingOverlay:
    """Full-screen onboarding overlay for first-run player setup.

    Blocks all other UI interaction until the player completes setup
    or skips. Results are returned via get_result().
    """

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.active = False
        self.alpha = 0.0
        self.step = STEP_PUCK_INTRO

        # Input state
        self.name_text = ""
        self.tts_text = ""  # Phonetic pronunciation override
        self.selected_title = ""
        self.selected_role = ""
        self.selected_pronouns = ""
        self.custom_title = ""
        self.experience_mode = "focused"
        self.metrics_tracking_enabled = False

        # UI state
        self._cursor_blink = 0.0
        self._active_field = "name"  # "name" or "tts" or "custom_title"
        self._hovered_option = -1
        self._button_rects: list[pygame.Rect] = []

        # Result
        self._result: dict | None = None

        # Panel rect (centered)
        self.panel_rect = pygame.Rect(
            (screen_w - PANEL_W) // 2,
            (screen_h - PANEL_H) // 2,
            PANEL_W,
            PANEL_H,
        )

    def update_layout(self, screen_w: int, screen_h: int) -> None:
        """Re-center the overlay for the current window size."""

        self.screen_w = screen_w
        self.screen_h = screen_h
        self.panel_rect.center = (screen_w // 2, screen_h // 2)

    def start(self) -> None:
        """Activate the onboarding overlay."""
        self.active = True
        self.step = STEP_PUCK_INTRO
        self._result = None

    def get_result(self) -> dict | None:
        """Return the completed onboarding result, or None if not done."""
        return self._result

    def update(self, dt: float) -> None:
        target = 255.0 if self.active else 0.0
        self.alpha += (target - self.alpha) * min(dt * 8, 1.0)
        self._cursor_blink += dt
        if self._cursor_blink > 1.0:
            self._cursor_blink -= 1.0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active or self.alpha < 10:
            return False

        if event.type == pygame.KEYDOWN:
            return self._handle_key(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos)

        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)

        return True  # Consume all events while onboarding is active

    def _handle_key(self, event: pygame.event.Event) -> bool:
        if self.step == STEP_PUCK_INTRO:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.step = STEP_MODE
            return True

        if self.step == STEP_METRICS and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            # Default recommendation:
            # Focused -> OFF, Gamified -> ON.
            self.metrics_tracking_enabled = self.experience_mode == "gamified"
            self.step = STEP_NAME
            return True

        if self.step == STEP_NAME:
            if event.key == pygame.K_RETURN and self.name_text.strip():
                self.tts_text = self.name_text  # Default TTS = display name
                self.step = STEP_PRONUNCIATION
            elif event.key == pygame.K_BACKSPACE:
                self.name_text = self.name_text[:-1]
            elif event.unicode and len(self.name_text) < 30:
                self.name_text += event.unicode
            return True

        if self.step == STEP_PRONUNCIATION:
            if event.key == pygame.K_RETURN:
                self.step = STEP_TITLE
            elif event.key == pygame.K_BACKSPACE:
                self.tts_text = self.tts_text[:-1]
            elif event.unicode and len(self.tts_text) < 40:
                self.tts_text += event.unicode
            return True

        if self.step == STEP_WELCOME:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._finalize()
            return True

        return True

    def _handle_click(self, pos: tuple[int, int]) -> bool:
        if self.step == STEP_PUCK_INTRO:
            for rect in self._button_rects:
                if rect.collidepoint(pos):
                    self.step = STEP_MODE
                    self._button_rects.clear()
                    return True

        if self.step == STEP_MODE:
            for i, rect in enumerate(self._button_rects):
                if rect.collidepoint(pos):
                    self.experience_mode = EXPERIENCE_OPTIONS[i][0]
                    self.step = STEP_METRICS
                    self._button_rects.clear()
                    return True

        if self.step == STEP_METRICS:
            for i, rect in enumerate(self._button_rects):
                if rect.collidepoint(pos):
                    self.metrics_tracking_enabled = i == 0
                    self.step = STEP_NAME
                    self._button_rects.clear()
                    return True

        if self.step == STEP_TITLE:
            for i, rect in enumerate(self._button_rects):
                if rect.collidepoint(pos):
                    role, _label, _desc = ROLE_OPTIONS[i]
                    self.selected_role = role
                    self.selected_title = _label
                    self.step = STEP_PRONOUNS
                    self._button_rects.clear()
                    return True

        if self.step == STEP_PRONOUNS:
            for i, rect in enumerate(self._button_rects):
                if rect.collidepoint(pos):
                    self.selected_pronouns = PRONOUN_OPTIONS[i]
                    self.step = STEP_WELCOME
                    self._button_rects.clear()
                    return True

        if self.step == STEP_WELCOME:
            self._finalize()
            return True

        return True

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_option = -1
        for i, rect in enumerate(self._button_rects):
            if rect.collidepoint(pos):
                self._hovered_option = i

    def _finalize(self) -> None:
        self._result = {
            "display_name": self.name_text.strip(),
            "tts_name": self.tts_text.strip() or self.name_text.strip(),
            "title": self.selected_title,
            "role": self.selected_role or "mortal",
            "pronouns": self.selected_pronouns,
            "experience_mode": self.experience_mode,
            "metrics_tracking_enabled": self.metrics_tracking_enabled,
        }
        self.active = False
        self.step = STEP_DONE

    def draw(self, screen: pygame.Surface) -> None:
        if self.alpha <= 1.0:
            return

        alpha_int = int(self.alpha)

        # Full-screen dim overlay
        dim = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, min(alpha_int, 180)))
        screen.blit(dim, (0, 0))

        # Panel
        panel = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        bg = (*theme.panel_bg, min(alpha_int, 245))
        pygame.draw.rect(panel, bg, (0, 0, PANEL_W, PANEL_H), border_radius=12)
        border = (*theme.gold, min(alpha_int, 150))
        pygame.draw.rect(panel, border, (0, 0, PANEL_W, PANEL_H), width=2, border_radius=12)

        if self.step == STEP_PUCK_INTRO:
            self._draw_puck_intro_step(panel, alpha_int)
        elif self.step == STEP_MODE:
            self._draw_mode_step(panel, alpha_int)
        elif self.step == STEP_METRICS:
            self._draw_metrics_step(panel, alpha_int)
        elif self.step == STEP_NAME:
            self._draw_name_step(panel, alpha_int)
        elif self.step == STEP_PRONUNCIATION:
            self._draw_pronunciation_step(panel, alpha_int)
        elif self.step == STEP_TITLE:
            self._draw_title_step(panel, alpha_int)
        elif self.step == STEP_PRONOUNS:
            self._draw_pronouns_step(panel, alpha_int)
        elif self.step == STEP_WELCOME:
            self._draw_welcome_step(panel, alpha_int)

        screen.blit(panel, self.panel_rect.topleft)

    def _draw_puck_intro_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 36
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "✨ Welcome to Kourai Khryseai ✨", title_color)
        y += 48

        puck_color = (*theme.gold_dim, alpha)
        FONT_BODY.render_to(surf, (30, y), "Puck:", puck_color)
        y += 26

        text_color = (*theme.white, alpha)
        lines = [
            "Come on, I'll guide you to Hephaestus.",
            "The forge is waiting.",
            "",
            "Let's choose how you want this session to feel.",
        ]
        for line in lines:
            FONT_BODY.render_to(surf, (30, y), line, text_color)
            y += 24

        self._button_rects.clear()
        btn_y = PANEL_H - 88
        rect = pygame.Rect(self.panel_rect.x + 30, self.panel_rect.y + btn_y, PANEL_W - 60, 48)
        self._button_rects.append(rect)

        local_rect = pygame.Rect(30, btn_y, PANEL_W - 60, 48)
        btn_bg = (*theme.gold_dim, min(alpha, 100))
        pygame.draw.rect(surf, btn_bg, local_rect, border_radius=6)
        btn_border = (*theme.gold, min(alpha, 170))
        pygame.draw.rect(surf, btn_border, local_rect, width=1, border_radius=6)
        FONT_BODY.render_to(surf, (50, btn_y + 15), "Continue", (*theme.gold, alpha))

    def _draw_mode_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 34
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "Choose your session style", title_color)
        y += 42

        sub_color = (*theme.dim_white, alpha)
        FONT_AGENT.render_to(
            surf,
            (30, y),
            "You can change game mechanics later in settings.",
            sub_color,
        )
        y += 36

        self._button_rects.clear()
        for i, (_mode, label) in enumerate(EXPERIENCE_OPTIONS):
            btn_y = y + i * (BUTTON_H + BUTTON_PAD)
            rect = pygame.Rect(
                self.panel_rect.x + 30, self.panel_rect.y + btn_y, PANEL_W - 60, BUTTON_H
            )
            self._button_rects.append(rect)

            local_rect = pygame.Rect(30, btn_y, PANEL_W - 60, BUTTON_H)
            if self._hovered_option == i:
                btn_bg = (*theme.gold_dim, min(alpha, 100))
            else:
                btn_bg = (*theme.panel_bg, min(alpha, 150))
            pygame.draw.rect(surf, btn_bg, local_rect, border_radius=6)

            btn_border = (*theme.gold_dim, min(alpha, 120))
            pygame.draw.rect(surf, btn_border, local_rect, width=1, border_radius=6)

            label_color = (*theme.gold, alpha)
            FONT_BODY.render_to(surf, (42, btn_y + 12), f"○ {label}", label_color)

    def _draw_metrics_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 34
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "Enable transparent metrics?", title_color)
        y += 42

        sub_color = (*theme.dim_white, alpha)
        recommendation = (
            "Recommended: ON for Gamified mode"
            if self.experience_mode == "gamified"
            else "Recommended: OFF for Focused mode"
        )
        FONT_AGENT.render_to(
            surf,
            (30, y),
            "Tracks affinity + virtues so you can see relationship progression.",
            sub_color,
        )
        y += 24
        FONT_AGENT.render_to(surf, (30, y), recommendation, sub_color)
        y += 40

        labels = ["Yes, enable metrics", "No, keep this session private"]
        self._button_rects.clear()
        for i, label in enumerate(labels):
            btn_y = y + i * (BUTTON_H + BUTTON_PAD)
            rect = pygame.Rect(
                self.panel_rect.x + 30, self.panel_rect.y + btn_y, PANEL_W - 60, BUTTON_H
            )
            self._button_rects.append(rect)

            local_rect = pygame.Rect(30, btn_y, PANEL_W - 60, BUTTON_H)
            if self._hovered_option == i:
                btn_bg = (*theme.gold_dim, min(alpha, 100))
            else:
                btn_bg = (*theme.panel_bg, min(alpha, 150))
            pygame.draw.rect(surf, btn_bg, local_rect, border_radius=6)

            btn_border = (*theme.gold_dim, min(alpha, 120))
            pygame.draw.rect(surf, btn_border, local_rect, width=1, border_radius=6)

            label_color = (*theme.gold, alpha)
            FONT_BODY.render_to(surf, (42, btn_y + 12), f"○ {label}", label_color)

    def _draw_name_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 40
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "What shall we call you?", title_color)
        y += 40

        sub_color = (*theme.dim_white, alpha)
        FONT_AGENT.render_to(surf, (30, y), "Enter your name — the maidens await~", sub_color)
        y += 50

        # Text input box
        self._draw_text_input(surf, 30, y, self.name_text, alpha, active=True)
        y += 60

        hint_color = (*theme.dim_white, min(alpha, 120))
        FONT_AGENT.render_to(surf, (30, y), "Press Enter to continue", hint_color)

    def _draw_pronunciation_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 40
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "How is it pronounced?", title_color)
        y += 40

        sub_color = (*theme.dim_white, alpha)
        FONT_AGENT.render_to(surf, (30, y), f'Display name: "{self.name_text}"', sub_color)
        y += 25
        FONT_AGENT.render_to(
            surf,
            (30, y),
            "Edit the phonetic spelling below until it sounds right:",
            sub_color,
        )
        y += 40

        label_color = (*theme.white, alpha)
        FONT_BODY.render_to(surf, (30, y), "Sounds like:", label_color)
        y += 30

        self._draw_text_input(surf, 30, y, self.tts_text, alpha, active=True)
        y += 60

        hint_color = (*theme.dim_white, min(alpha, 120))
        FONT_AGENT.render_to(
            surf,
            (30, y),
            "Tip: Spell it how it sounds (e.g., 'Shao Ming' for 'Xiaoming')",
            hint_color,
        )
        y += 20
        FONT_AGENT.render_to(surf, (30, y), "Press Enter to continue", hint_color)

    def _draw_title_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 30
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "How should they address you?", title_color)
        y += 50

        self._button_rects.clear()
        for i, (_role, label, desc) in enumerate(ROLE_OPTIONS):
            btn_y = y + i * (BUTTON_H + BUTTON_PAD)
            rect = pygame.Rect(
                self.panel_rect.x + 30,
                self.panel_rect.y + btn_y,
                PANEL_W - 60,
                BUTTON_H,
            )
            self._button_rects.append(rect)

            # Draw locally on panel surface
            local_rect = pygame.Rect(30, btn_y, PANEL_W - 60, BUTTON_H)
            if self._hovered_option == i:
                btn_bg = (*theme.gold_dim, min(alpha, 100))
            else:
                btn_bg = (*theme.panel_bg, min(alpha, 150))
            pygame.draw.rect(surf, btn_bg, local_rect, border_radius=6)

            btn_border = (*theme.gold_dim, min(alpha, 120))
            pygame.draw.rect(surf, btn_border, local_rect, width=1, border_radius=6)

            label_color = (*theme.gold, alpha)
            FONT_BODY.render_to(surf, (42, btn_y + 8), f"○ {label}", label_color)

            desc_color = (*theme.dim_white, min(alpha, 160))
            FONT_AGENT.render_to(surf, (60, btn_y + 26), desc, desc_color)

    def _draw_pronouns_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 40
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "Pronouns (optional)", title_color)
        y += 40

        sub_color = (*theme.dim_white, alpha)
        FONT_AGENT.render_to(
            surf, (30, y), "Helps the maidens speak about you naturally", sub_color
        )
        y += 50

        labels = ["he/him", "she/her", "they/them", "Skip"]
        self._button_rects.clear()
        for i, label in enumerate(labels):
            btn_y = y + i * (BUTTON_H + BUTTON_PAD)
            rect = pygame.Rect(
                self.panel_rect.x + 30,
                self.panel_rect.y + btn_y,
                BUTTON_W,
                BUTTON_H,
            )
            self._button_rects.append(rect)

            local_rect = pygame.Rect(30, btn_y, BUTTON_W, BUTTON_H)
            if self._hovered_option == i:
                btn_bg = (*theme.gold_dim, min(alpha, 100))
            else:
                btn_bg = (*theme.panel_bg, min(alpha, 150))
            pygame.draw.rect(surf, btn_bg, local_rect, border_radius=6)

            btn_border = (*theme.gold_dim, min(alpha, 120))
            pygame.draw.rect(surf, btn_border, local_rect, width=1, border_radius=6)

            label_color = (*theme.gold, alpha)
            FONT_BODY.render_to(surf, (42, btn_y + 12), f"○ {label}", label_color)

    def _draw_welcome_step(self, surf: pygame.Surface, alpha: int) -> None:
        y = 40
        title_color = (*theme.gold, alpha)
        FONT_NAME.render_to(surf, (30, y), "Welcome to the Forge", title_color)
        y += 50

        name = self.name_text.strip() or "traveler"
        title = self.selected_title or "artisan"
        role = self.selected_role or "mortal"
        mode = self.experience_mode

        text_color = (*theme.white, alpha)
        welcome_lines = [
            f"Puck: {_puck_handoff_line(role)}",
            "",
            f"Ah... so you're {name}. *nods slowly*",
            "",
            "The forge has been waiting for someone like you,",
            f"{title.lower()}.",
            "",
            "The maidens are eager to meet you.",
            "Each has their own... personality. You'll see~",
            "",
            f"*mode={mode} · metrics={'ON' if self.metrics_tracking_enabled else 'OFF'}*",
            "",
            "*turns back to the anvil*",
            "Let's begin.",
        ]

        for line in welcome_lines:
            if line.startswith("Puck:"):
                puck_color = (*theme.gold_dim, min(alpha, 190))
                FONT_AGENT.render_to(surf, (30, y), line, puck_color)
            elif line.startswith("*"):
                emote_color = (*theme.gold_dim, min(alpha, 180))
                FONT_AGENT.render_to(surf, (30, y), line, emote_color)
            else:
                FONT_BODY.render_to(surf, (30, y), line, text_color)
            y += 22

        y += 10
        hint_color = (*theme.dim_white, min(alpha, 120))
        FONT_AGENT.render_to(surf, (30, y), "Press Enter or click to begin", hint_color)

    def _draw_text_input(
        self,
        surf: pygame.Surface,
        x: int,
        y: int,
        text: str,
        alpha: int,
        active: bool = False,
    ) -> None:
        """Draw a text input field."""
        rect = pygame.Rect(x, y, INPUT_W, INPUT_H)

        # Background
        bg_color = (*theme.input_bg, min(alpha, 200))
        pygame.draw.rect(surf, bg_color, rect, border_radius=4)

        # Border
        if active:
            border_color = (*theme.gold, min(alpha, 200))
        else:
            border_color = (*theme.gold_dim, min(alpha, 100))
        pygame.draw.rect(surf, border_color, rect, width=1, border_radius=4)

        # Text
        text_color = (*theme.white, alpha)
        FONT_INPUT.render_to(surf, (x + 8, y + 10), text, text_color)

        # Cursor
        if active and self._cursor_blink < 0.5:
            cursor_x = x + 8 + FONT_INPUT.get_rect(text).width + 2
            cursor_color = (*theme.gold, alpha)
            pygame.draw.line(surf, cursor_color, (cursor_x, y + 8), (cursor_x, y + INPUT_H - 8))
