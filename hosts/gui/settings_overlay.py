"""Settings overlay panel for Kourai Khryseai Pygame GUI.

Implements March 2026 UI/UX best practices:
- "Quiet Intelligence" aesthetic (clean, frosted glass/overlay).
- Progressive disclosure.
- Easy to tap/click toggles for accessibility settings.
- Tabbed navigation (Display, Gameplay, Audio) for better organization.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame
import pygame.freetype

from hosts.gui.display_modes import DISPLAY_MODE_OPTIONS, normalize_display_mode
from hosts.gui.settings_widgets import (
    Button,
    CycleButton,
    TabButton,
    ToggleSwitch,
    VolumeSlider,
    _ensure_freetype_ready,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from hosts.gui.audio_manager import AudioManager as _AudioManager
    from hosts.gui.gui_components_integration import GUIComponentsIntegration


class SettingsOverlay:
    """The main settings overlay panel."""

    def __init__(
        self,
        width: int,
        height: int,
        gui_integration: GUIComponentsIntegration,
        audio_manager: _AudioManager | None = None,
    ):
        self.screen_w = width
        self.screen_h = height
        self.gui = gui_integration
        self.audio_manager = audio_manager
        self.active = False
        self.alpha = 0.0

        # Layout
        self.panel_w = 420
        self.panel_h = 520
        self.panel_rect = pygame.Rect(
            (self.screen_w - self.panel_w) // 2,
            (self.screen_h - self.panel_h) // 2,
            self.panel_w,
            self.panel_h,
        )

        _ensure_freetype_ready()
        self.font_title = pygame.freetype.SysFont("segoeui, inter, arial", 24)
        self.font_label = pygame.freetype.SysFont("segoeui, inter, arial", 16)
        self.font_small = pygame.freetype.SysFont("segoeui, inter, arial", 12)

        self.on_quit_callback: Callable[[], None] | None = None
        self._init_controls()

    def update_layout(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.panel_rect.centerx = screen_w // 2
        self.panel_rect.centery = screen_h // 2

        # Save necessary state
        old_tab = getattr(self, "active_tab", "display")

        self._init_controls()

        # Restore state
        self.active_tab = old_tab
        for t in self.tabs.values():
            t.active = t.tab_id == old_tab

        # Re-sync states from settings
        for category in self.toggles.values():
            for k, t in category.items():
                t["switch"].state = self.gui.settings.get(k, t["switch"].state)
                t["switch"].anim_t = 1.0 if t["switch"].state else 0.0
        for category in self.sliders.values():
            for k, s in category.items():
                s["slider"].value = self.gui.settings.get(k, s["slider"].value)

    def set_display_mode_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for display mode toggle."""
        self.on_display_mode_toggle = callback

    def set_quit_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for quit button."""
        self.on_quit_callback = callback

    def _init_controls(self):
        # Tabs
        self.active_tab = "display"
        self.tabs: dict[str, TabButton] = {}
        tab_width = (self.panel_w - 60) // 4

        def on_tab_click(tab_id: str):
            self.active_tab = tab_id
            for t in self.tabs.values():
                t.active = t.tab_id == tab_id

        tab_y = self.panel_rect.y + 70
        tab_x = self.panel_rect.x + 30
        for i, (tab_id, label) in enumerate(
            [
                ("display", "Display"),
                ("gameplay", "Gameplay"),
                ("audio", "Audio"),
                ("controls", "Controls"),
            ]
        ):
            self.tabs[tab_id] = TabButton(
                tab_x + tab_width * i, tab_y, tab_width - 5, 30, label, tab_id, on_tab_click
            )
        self.tabs["display"].active = True

        self.toggles: dict[str, dict] = {"display": {}, "gameplay": {}, "audio": {}, "controls": {}}
        self.sliders: dict[str, dict] = {"display": {}, "gameplay": {}, "audio": {}, "controls": {}}

        start_y = self.panel_rect.y + 130
        spacing = 48

        def make_toggle(tab, key, label, y_offset, default=False):
            state = self.gui.settings.get(key, default)

            def on_toggle(new_state, k=key):
                self.gui.settings.set(k, new_state)
                # Apply immediate effects
                if k == "high_contrast":
                    if new_state:
                        self.gui.high_contrast.enable_high_contrast()
                    else:
                        self.gui.high_contrast.disable_high_contrast()
                elif k == "fullscreen" and hasattr(self, "on_fullscreen_toggle"):
                    # Trigger fullscreen toggle via callback
                    self.on_fullscreen_toggle(new_state)

                self.gui.save_all_settings()

            self.toggles[tab][key] = {
                "label": label,
                "switch": ToggleSwitch(
                    self.panel_rect.right - 70, y_offset, 40, 24, state, on_toggle
                ),
                "y": y_offset,
            }

        # Display Controls
        make_toggle("display", "high_contrast", "High Contrast Mode", start_y)
        make_toggle("display", "reduce_motion", "Reduce Motion", start_y + spacing)

        # Display Mode Cycle Button
        display_mode_state = normalize_display_mode(
            self.gui.settings.get("display_mode", "Windowed")
        )

        def on_display_mode(new_mode: str):
            previous_mode = normalize_display_mode(
                self.gui.settings.get("display_mode", "Windowed")
            )
            normalized_mode = normalize_display_mode(new_mode)
            logger.debug(
                "Player selected display mode in settings overlay: %s -> %s",
                previous_mode,
                normalized_mode,
            )
            self.gui.settings.set("display_mode", normalized_mode)
            if hasattr(self, "on_display_mode_toggle"):
                self.on_display_mode_toggle(normalized_mode)
            self.gui.save_all_settings()

        self.display_mode_btn = CycleButton(
            self.panel_rect.right - 140,
            start_y + spacing * 2,
            110,
            24,
            DISPLAY_MODE_OPTIONS,
            display_mode_state,
            on_display_mode,
        )

        # Gameplay Toggles
        make_toggle("gameplay", "auto_scroll_enabled", "Auto-Scroll Chat", start_y, True)
        make_toggle("gameplay", "typewriter_enabled", "Typewriter Effect", start_y + spacing, True)
        make_toggle("gameplay", "show_debug_logs", "Show Debug Logs", start_y + spacing * 2, False)

        # Role selector (Gameplay tab)
        from kourai_common.player import PlayerProfile

        _profile = PlayerProfile.load()
        current_role = _profile.role if _profile else "mortal"
        role_options = ["divine", "mortal", "hero", "devoted", "name_only"]

        def on_role_change(new_role: str) -> None:
            profile = PlayerProfile.load()
            if profile:
                profile.role = new_role
                profile.save()

        self.role_btn = CycleButton(
            self.panel_rect.right - 140,
            start_y + spacing * 3,
            110,
            24,
            role_options,
            current_role,
            on_role_change,
        )

        # Audio Sliders
        slider_spacing = 48
        slider_w = self.panel_w - 140

        audio_controls = [
            ("music_volume", "Music", 0.65),
            ("ambient_volume", "Ambient", 0.50),
            ("voice_volume", "Voice", 1.0),
            ("sfx_volume", "SFX", 0.85),
        ]

        for i, (key, label, default) in enumerate(audio_controls):
            vol = self.gui.settings.get(key, default)

            def on_slide(value: float, k=key):
                self.gui.settings.set(k, round(value, 2))
                if self.audio_manager is not None:
                    setter = getattr(self.audio_manager, f"set_{k}", None)
                    if setter:
                        setter(value)
                self.gui.save_all_settings()

            y = start_y + i * slider_spacing
            self.sliders["audio"][key] = {
                "label": label,
                "slider": VolumeSlider(
                    self.panel_rect.x + 100,
                    y,
                    slider_w,
                    20,
                    vol,
                    on_slide,
                ),
                "y": y,
            }

        # Controls tab — static key map (read-only)
        self._keymap = [
            ("ESC", "Open / close settings"),
            ("TAB", "Toggle scratchpad"),
            ("F2", "Toggle alignment gauges"),
            ("F3", "Toggle gossip panel"),
            ("F4", "Toggle memory viewer"),
            ("Enter", "Send message"),
            ("Up / Down", "Message history"),
            ("Scroll", "Scroll chat"),
            ("Ctrl+K", "Focus input bar"),
            ("Ctrl+L", "Clear input bar"),
            ("Ctrl+Bksp", "Delete last word"),
            ("Right-click", "Copy message text"),
        ]

        # Buttons
        btn_y = self.panel_rect.bottom - 60
        btn_w = (self.panel_w - 90) // 2

        self.reset_button = Button(
            self.panel_rect.x + 30, btn_y, btn_w, 40, "Reset", self._on_reset_clicked
        )

        self.quit_button = Button(
            self.panel_rect.x + 60 + btn_w, btn_y, btn_w, 40, "Quit", self._on_quit_clicked
        )

    def _on_reset_clicked(self) -> None:
        """Handle reset defaults click."""
        if hasattr(self.gui.settings, "reset_to_defaults"):
            self.gui.settings.reset_to_defaults()

        # Apply immediate effects
        if self.gui.settings.get("high_contrast"):
            self.gui.high_contrast.enable_high_contrast()
        else:
            self.gui.high_contrast.disable_high_contrast()

        if hasattr(self, "on_display_mode_toggle"):
            logger.debug(
                "Settings reset restoring display mode to %s",
                normalize_display_mode(self.gui.settings.get("display_mode", "Windowed")),
            )
            self.on_display_mode_toggle(
                normalize_display_mode(self.gui.settings.get("display_mode", "Windowed"))
            )

        self.display_mode_btn.value = normalize_display_mode(
            self.gui.settings.get("display_mode", "Windowed")
        )

        # Re-sync toggles
        for category in self.toggles.values():
            for k, t in category.items():
                t["switch"].state = self.gui.settings.get(k, t["switch"].state)
                t["switch"].anim_t = 1.0 if t["switch"].state else 0.0

        # Re-sync sliders and audio
        for category in self.sliders.values():
            for k, s in category.items():
                val = self.gui.settings.get(k, s["slider"].value)
                s["slider"].value = val
                if self.audio_manager is not None:
                    setter = getattr(self.audio_manager, f"set_{k}", None)
                    if setter:
                        setter(val)

    def _on_quit_clicked(self) -> None:
        """Handle quit button click."""
        if self.on_quit_callback:
            self.on_quit_callback()

    def toggle(self):
        self.active = not self.active
        if self.active:
            # Re-sync toggle states
            for category in self.toggles.values():
                for k, t in category.items():
                    t["switch"].state = self.gui.settings.get(k, t["switch"].state)
                    t["switch"].anim_t = 1.0 if t["switch"].state else 0.0
            # Re-sync slider values from settings
            for category in self.sliders.values():
                for k, s in category.items():
                    s["slider"].value = self.gui.settings.get(k, s["slider"].value)

    def update(self, dt: float):
        target_alpha = 255.0 if self.active else 0.0
        self.alpha += (target_alpha - self.alpha) * min(dt * 10, 1.0)

        # Update controls only while menu is actively open (not during close animation)
        if self.alpha > 1.0 and self.active:
            mouse_pos = pygame.mouse.get_pos()
            for t in self.tabs.values():
                t.update(mouse_pos)

            for t in self.toggles[self.active_tab].values():
                t["switch"].update(dt)

            if self.active_tab == "display":
                self.display_mode_btn.update(mouse_pos)
            if self.active_tab == "gameplay":
                self.role_btn.update(mouse_pos)

            # Update button hover state
            self.reset_button.update(mouse_pos)
            self.quit_button.update(mouse_pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if event was consumed."""
        if not self.active:
            return False

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.toggle()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.panel_rect.collidepoint(event.pos):
                self.toggle()
                return True

            for t in self.tabs.values():
                if t.handle_click(event.pos):
                    return True

            # Check buttons
            if self.quit_button.handle_click(event.pos):
                return True
            if self.reset_button.handle_click(event.pos):
                return True

            for t in self.toggles[self.active_tab].values():
                if t["switch"].handle_click(event.pos):
                    return True

            if self.active_tab == "display" and self.display_mode_btn.handle_click(event.pos):
                return True

            if self.active_tab == "gameplay" and self.role_btn.handle_click(event.pos):
                return True

            for s in self.sliders[self.active_tab].values():
                if s["slider"].handle_mousedown(event.pos):
                    return True

            return True  # Consume all clicks on panel

        if event.type == pygame.MOUSEMOTION:
            for s in self.sliders[self.active_tab].values():
                if s["slider"].handle_mousemotion(event.pos):
                    return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for s in self.sliders[self.active_tab].values():
                s["slider"].handle_mouseup()

        return False

    def draw(self, screen: pygame.Surface):
        if self.alpha <= 1.0:
            return

        # Overlay background
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(self.alpha * 0.6)))

        # Panel
        palette = self.gui.high_contrast.get_color_palette()
        panel_color = (*palette.get("bubble_bg", (30, 22, 10)), int(self.alpha))
        border_color = (*palette.get("bubble_border", (218, 165, 32)), int(self.alpha))
        text_color = (*palette.get("text", (255, 255, 255)), int(self.alpha))
        dim_color = (*palette.get("scrollbar", (160, 155, 145)), int(self.alpha))
        palette.get("gold", (218, 165, 32))

        pygame.draw.rect(overlay, panel_color, self.panel_rect, border_radius=12)
        pygame.draw.rect(overlay, border_color, self.panel_rect, 1, border_radius=12)

        # Title
        self.font_title.render_to(
            overlay, (self.panel_rect.x + 30, self.panel_rect.y + 25), "Settings", text_color
        )

        # Tabs
        for t in self.tabs.values():
            t.draw(overlay, self.font_label, palette)

        # Draw toggles with synchronized alpha
        for t in self.toggles[self.active_tab].values():
            self.font_label.render_to(
                overlay, (self.panel_rect.x + 30, t["y"] + 4), t["label"], text_color
            )
            t["switch"].draw(overlay, palette)

        if self.active_tab == "display":
            self.font_label.render_to(
                overlay,
                (self.panel_rect.x + 30, self.display_mode_btn.rect.y + 4),
                "Display Mode",
                text_color,
            )
            self.display_mode_btn.draw(overlay, self.font_label, palette)

        if self.active_tab == "gameplay":
            self.font_label.render_to(
                overlay,
                (self.panel_rect.x + 30, self.role_btn.rect.y + 4),
                "Player Role",
                text_color,
            )
            self.role_btn.draw(overlay, self.font_label, palette)

        # Draw volume sliders
        for s in self.sliders[self.active_tab].values():
            self.font_small.render_to(
                overlay, (self.panel_rect.x + 30, s["y"] + 4), s["label"], dim_color
            )
            s["slider"].draw(overlay, palette)
            # Value percentage label
            pct = f"{int(s['slider'].value * 100)}%"
            self.font_small.render_to(
                overlay, (self.panel_rect.right - 48, s["y"] + 4), pct, dim_color
            )

        # Draw controls key map
        if self.active_tab == "controls":
            gold_color = (*palette.get("gold", (218, 165, 32)), int(self.alpha))
            km_y = self.panel_rect.y + 120
            row_h = 26
            key_col_x = self.panel_rect.x + 40
            desc_col_x = self.panel_rect.x + 160

            for key_label, description in self._keymap:
                # Key badge
                key_rect_w = self.font_small.get_rect(key_label).width + 16
                badge_rect = pygame.Rect(key_col_x, km_y - 2, key_rect_w, 20)
                pygame.draw.rect(overlay, (50, 45, 40), badge_rect, border_radius=4)
                pygame.draw.rect(overlay, gold_color, badge_rect, 1, border_radius=4)
                self.font_small.render_to(overlay, (key_col_x + 8, km_y + 2), key_label, gold_color)

                # Description
                self.font_small.render_to(overlay, (desc_col_x, km_y + 2), description, text_color)
                km_y += row_h

        # Draw buttons
        self.reset_button.draw(overlay, self.font_label, palette)
        self.quit_button.draw(overlay, self.font_label, palette)

        # Footer hint
        self.font_small.render_to(
            overlay,
            (self.panel_rect.centerx - 100, self.panel_rect.bottom - 15),
            "Press ESC or click outside to close",
            dim_color,
        )

        screen.blit(overlay, (0, 0))
