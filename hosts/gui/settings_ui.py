"""Settings Overlay UI for Kourai Khryseai.

Implements March 2026 UI/UX best practices:
- "Quiet Intelligence" aesthetic (clean, frosted glass/overlay).
- Progressive disclosure.
- Easy to tap/click toggles for accessibility settings.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame
import pygame.freetype

from hosts.gui.gui_components_integration import GUIComponentsIntegration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hosts.gui.audio_manager import AudioManager as _AM


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
        gold = palette.get("gold", (218, 165, 32))
        track_y = self.rect.centery
        # Track background
        pygame.draw.line(
            surf, (50, 45, 40),
            (self.rect.x + self._knob_radius, track_y),
            (self.rect.right - self._knob_radius, track_y),
            3,
        )
        # Filled portion
        kx = int(self._knob_x())
        pygame.draw.line(
            surf, gold,
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
        bg_color = palette.get("gold", (218, 165, 32)) if self.state else (50, 45, 40)
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
        bg_color = palette.get("gold", (218, 165, 32)) if self.hovered else (50, 45, 40)
        pygame.draw.rect(surf, bg_color, self.rect, border_radius=6)
        pygame.draw.rect(surf, palette.get("gold", (218, 165, 32)), self.rect, 1, border_radius=6)

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


class SettingsOverlay:
    """The main settings overlay panel."""

    def __init__(self, width: int, height: int, gui_integration: GUIComponentsIntegration,
                 audio_manager: _AM | None = None):
        self.screen_w = width
        self.screen_h = height
        self.gui = gui_integration
        self.audio_manager = audio_manager
        self.active = False
        self.alpha = 0.0

        # Layout — taller panel to hold audio sliders
        self.panel_w = 400
        self.panel_h = 780
        self.panel_rect = pygame.Rect(
            (self.screen_w - self.panel_w) // 2,
            (self.screen_h - self.panel_h) // 2,
            self.panel_w,
            self.panel_h,
        )

        self.font_title = pygame.freetype.SysFont("segoeui, inter, arial", 24)
        self.font_label = pygame.freetype.SysFont("segoeui, inter, arial", 16)
        self.font_small = pygame.freetype.SysFont("segoeui, inter, arial", 12)

        self.on_quit_callback = None
        self._init_controls()

    def set_fullscreen_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for fullscreen toggle."""
        self.on_fullscreen_toggle = callback

    def set_quit_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for quit button."""
        self.on_quit_callback = callback

    def _init_controls(self):
        self.toggles = {}
        self.sliders: dict[str, dict] = {}

        # Starting Y for controls
        start_y = self.panel_rect.y + 80
        spacing = 48

        def make_toggle(key, label, y_offset, default=False):
            state = self.gui.settings.get(key, default)

            def on_toggle(new_state, k=key):
                self.gui.settings.set(k, new_state)
                # Apply immediate effects
                if k == "high_contrast":
                    if new_state:
                        self.gui.high_contrast.enable_high_contrast()
                    else:
                        self.gui.high_contrast.disable_high_contrast()
                elif k == "status_bubbles_collapsed":
                    # sync it
                    if self.gui.status_bubbles.is_collapsed() != new_state:
                        self.gui.status_bubbles.toggle_status_bubbles()
                elif k == "fullscreen" and hasattr(self, "on_fullscreen_toggle"):
                    # Trigger fullscreen toggle via callback
                    self.on_fullscreen_toggle(new_state)

                self.gui.save_all_settings()

            self.toggles[key] = {
                "label": label,
                "switch": ToggleSwitch(
                    self.panel_rect.right - 70, y_offset, 40, 24, state, on_toggle
                ),
                "y": y_offset,
            }

        make_toggle("high_contrast", "High Contrast Mode", start_y)
        make_toggle("reduce_motion", "Reduce Motion", start_y + spacing)
        make_toggle("auto_scroll_enabled", "Auto-Scroll Chat", start_y + spacing * 2, True)
        make_toggle("typewriter_enabled", "Typewriter Effect", start_y + spacing * 3, True)
        make_toggle(
            "status_bubbles_collapsed", "Collapse Status Bubbles", start_y + spacing * 4, False
        )
        make_toggle("fullscreen", "Fullscreen Mode", start_y + spacing * 5, False)

        # --- Audio section ---
        audio_section_y = start_y + spacing * 6 + 16
        self._audio_label_y = audio_section_y
        slider_start_y = audio_section_y + 28
        slider_spacing = 48
        slider_w = self.panel_w - 140  # leave room for label + value text

        audio_controls = [
            ("music_volume", "Music", 0.25),
            ("ambient_volume", "Ambient", 0.5),
            ("voice_volume", "Voice", 1.0),
            ("sfx_volume", "SFX", 0.8),
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

            y = slider_start_y + i * slider_spacing
            self.sliders[key] = {
                "label": label,
                "slider": VolumeSlider(
                    self.panel_rect.x + 100, y, slider_w, 20, vol, on_slide,
                ),
                "y": y,
            }

        # Quit button
        quit_y = slider_start_y + len(audio_controls) * slider_spacing + 12
        self.quit_button = Button(
            self.panel_rect.x + 30, quit_y, self.panel_w - 60, 40, "Quit", self._on_quit_clicked
        )

    def _on_quit_clicked(self) -> None:
        """Handle quit button click."""
        if self.on_quit_callback:
            self.on_quit_callback()

    def toggle(self):
        self.active = not self.active
        if self.active:
            # Re-sync toggle states
            for k, t in self.toggles.items():
                t["switch"].state = self.gui.settings.get(k, t["switch"].state)
                t["switch"].anim_t = 1.0 if t["switch"].state else 0.0
            # Re-sync slider values from settings
            for k, s in self.sliders.items():
                s["slider"].value = self.gui.settings.get(k, s["slider"].value)

    def update(self, dt: float):
        target_alpha = 255.0 if self.active else 0.0
        self.alpha += (target_alpha - self.alpha) * min(dt * 10, 1.0)

        # Update controls only while menu is actively open (not during close animation)
        if self.alpha > 1.0 and self.active:
            for t in self.toggles.values():
                t["switch"].update(dt)

            # Update button hover state
            mouse_pos = pygame.mouse.get_pos()
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

            # Check quit button
            if self.quit_button.handle_click(event.pos):
                return True

            for t in self.toggles.values():
                if t["switch"].handle_click(event.pos):
                    return True

            for s in self.sliders.values():
                if s["slider"].handle_mousedown(event.pos):
                    return True

            return True  # Consume all clicks on panel

        if event.type == pygame.MOUSEMOTION:
            for s in self.sliders.values():
                if s["slider"].handle_mousemotion(event.pos):
                    return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for s in self.sliders.values():
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
        gold = palette.get("gold", (218, 165, 32))

        pygame.draw.rect(overlay, panel_color, self.panel_rect, border_radius=12)
        pygame.draw.rect(overlay, border_color, self.panel_rect, 1, border_radius=12)

        # Title
        self.font_title.render_to(
            overlay, (self.panel_rect.x + 30, self.panel_rect.y + 30), "Settings", text_color
        )

        # Draw toggles with synchronized alpha
        for t in self.toggles.values():
            self.font_label.render_to(
                overlay, (self.panel_rect.x + 30, t["y"] + 4), t["label"], text_color
            )
            t["switch"].draw(overlay, palette)

        # --- Audio section divider + heading ---
        div_y = self._audio_label_y - 4
        pygame.draw.line(
            overlay,
            (*gold, int(self.alpha * 0.4)),
            (self.panel_rect.x + 30, div_y),
            (self.panel_rect.right - 30, div_y),
            1,
        )
        self.font_label.render_to(
            overlay, (self.panel_rect.x + 30, self._audio_label_y + 2), "Audio", text_color
        )

        # Draw volume sliders
        for s in self.sliders.values():
            self.font_small.render_to(
                overlay, (self.panel_rect.x + 30, s["y"] + 4), s["label"], dim_color
            )
            s["slider"].draw(overlay, palette)
            # Value percentage label
            pct = f"{int(s['slider'].value * 100)}%"
            self.font_small.render_to(
                overlay, (self.panel_rect.right - 48, s["y"] + 4), pct, dim_color
            )

        # Draw quit button
        self.quit_button.draw(overlay, self.font_label, palette)

        # Footer hint
        self.font_small.render_to(
            overlay,
            (self.panel_rect.x + 30, self.panel_rect.bottom - 40),
            "Press ESC or click outside to close",
            dim_color,
        )

        screen.blit(overlay, (0, 0))
