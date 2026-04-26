"""Pygame event dispatcher — routes SDL events to subsystems and handlers.

Each event type (QUIT, KEYDOWN, TEXTINPUT, MOUSEMOTION, MOUSEWHEEL,
MOUSEBUTTONDOWN, resize) has its own method. Overlay dispatch is handled
first so active panels consume events before the main loop sees them.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

import pygame

from .dialogue import DialogueEntry
from .maidens import AGENTS

if TYPE_CHECKING:
    from collections.abc import Callable

    from kourai_common.audio import AudioManager

    from .alignment_gauges import AlignmentGaugePanel
    from .debug_log import DebugLog
    from .dialogue import DialogueHistory
    from .display_manager import DisplayManager
    from .gossip_panel import GossipPanel
    from .gui_components_integration import GUIComponentsIntegration
    from .gui_state import GUIState
    from .input_bar import InputBar
    from .memory_viewer import MemoryViewerPanel
    from .onboarding_ui import OnboardingOverlay
    from .portrait import PortraitPanel
    from .quick_actions import QuickActionBar
    from .settings_overlay import SettingsOverlay
    from .typewriter import TypewriterManager

logger = logging.getLogger(__name__)


class PygameEventDispatcher:
    """Routes pygame events to overlays, shortcuts, and subsystem handlers."""

    def __init__(
        self,
        state: GUIState,
        *,
        # Overlays
        onboarding: OnboardingOverlay,
        settings_overlay: SettingsOverlay,
        memory_viewer: MemoryViewerPanel,
        alignment_panel: AlignmentGaugePanel,
        gossip_panel: GossipPanel,
        gui_integration: GUIComponentsIntegration,
        # Input / display subsystems
        input_bar: InputBar,
        typewriter: TypewriterManager,
        history: DialogueHistory,
        portrait: PortraitPanel,
        quick_actions: QuickActionBar,
        debug_log: DebugLog,
        display: DisplayManager,
        audio_manager: AudioManager,
        # Data
        send_q,
        dialogue_rect: pygame.Rect,
        resize_events: set[int],
        # Callbacks
        on_quit: Callable[[], None],
        sync_layout: Callable[[int, int], None],
    ) -> None:
        self.state = state
        self.onboarding = onboarding
        self.settings_overlay = settings_overlay
        self.memory_viewer = memory_viewer
        self.alignment_panel = alignment_panel
        self.gossip_panel = gossip_panel
        self.gui_integration = gui_integration
        self.input_bar = input_bar
        self.typewriter = typewriter
        self.history = history
        self.portrait = portrait
        self.quick_actions = quick_actions
        self.debug_log = debug_log
        self.display = display
        self.audio_manager = audio_manager
        self.send_q = send_q
        self.dialogue_rect = dialogue_rect
        self.resize_events = resize_events
        self.on_quit = on_quit
        self.sync_layout = sync_layout
        # Alt+V image-paste holds captured clipboard images until the GUI's
        # send path can carry attachments.  Shape mirrors the CLI:
        # list[(base64_png, mime_type)].
        self._pending_images: list[tuple[str, str]] = []

    # -- public entry point --------------------------------------------------

    def dispatch(self, event: pygame.event.Event) -> None:
        """Route a single pygame event to the appropriate handler."""
        # Onboarding overlay consumes ALL events while active
        if self.onboarding.active:
            self._handle_onboarding(event)
            return

        # Active overlays get first crack at every event
        if self._dispatch_to_overlays(event):
            return

        if event.type == pygame.QUIT:
            self.on_quit()
        elif event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
        elif event.type == pygame.TEXTINPUT:
            self._handle_textinput(event)
        elif event.type == pygame.MOUSEMOTION:
            self.quick_actions.update(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            self._handle_mousewheel(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._handle_left_click(event)
            elif event.button == 3:
                self._handle_right_click(event)
        elif event.type in self.resize_events:
            self._handle_resize(event)

    # -- overlay dispatch ----------------------------------------------------

    def _handle_onboarding(self, event: pygame.event.Event) -> None:
        self.onboarding.handle_event(event)
        result = self.onboarding.get_result()
        if result:
            try:
                from kourai_common.player import PlayerProfile, set_active_profile

                profile = PlayerProfile()
                profile.display_name = result["display_name"]
                profile.tts_name = result["tts_name"]
                profile.title = result["title"]
                profile.role = result["role"]
                profile.pronouns = result["pronouns"]
                experience_mode = result.get("experience_mode", "focused")
                metrics_enabled = bool(result.get("metrics_tracking_enabled", False))
                profile.preferences["experience_mode"] = experience_mode
                profile.preferences["metrics_tracking_enabled"] = metrics_enabled
                profile.preferences["affinity_tracking_enabled"] = metrics_enabled
                profile.preferences["virtue_tracking_enabled"] = metrics_enabled
                profile.preferences["romance_nudges_enabled"] = True
                profile.preferences["gossip_nudges_enabled"] = True
                profile.romance_opted_out = True
                profile.jealousy_enabled = False
                profile.total_sessions = 1
                profile.save()
                set_active_profile(profile.player_id)
                self.alignment_panel.update_values(
                    profile.sovereignty, profile.devotion, profile.role
                )
            except Exception:
                logger.debug("Onboarding profile save/set failed")

    def _dispatch_to_overlays(self, event: pygame.event.Event) -> bool:
        """Let active overlays consume the event. Return True if consumed."""
        if self.settings_overlay.handle_event(event):
            return True
        if self.memory_viewer.handle_event(event):
            return True
        if self.alignment_panel.handle_event(event):
            return True
        if self.gossip_panel.handle_event(event):
            return True
        return self.gui_integration.get_scratchpad().handle_event(event)

    # -- keyboard ------------------------------------------------------------

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        mod = getattr(event, "mod", 0)
        ctrl = bool(mod & pygame.KMOD_CTRL)
        shift = bool(mod & pygame.KMOD_SHIFT)
        alt = bool(mod & pygame.KMOD_ALT)

        # Zoom shortcuts — Ctrl + / - / 0 match browser conventions.  Use
        # the existing FontScaler so values persist via settings.json.
        if ctrl and not shift and not alt:
            if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self._adjust_font_scale(+0.1)
                return
            if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self._adjust_font_scale(-0.1)
                return
            if event.key == pygame.K_0:
                self._set_font_scale(1.0)
                return

        # Ctrl+Shift+C — copy the dialogue entry under the mouse (or the
        # most recent one if the cursor is off the history panel) to the
        # system clipboard.  Mirrors the existing right-click semantics
        # but keyboard-driven.
        if ctrl and shift and not alt and event.key == pygame.K_c:
            self._copy_hovered_to_clipboard()
            return

        # Ctrl+V — paste clipboard text into the input bar.
        if ctrl and not shift and not alt and event.key == pygame.K_v:
            self._paste_text_from_clipboard()
            return

        # Alt+V — grab clipboard *image*, queue it as an attachment.
        # Mirrors the CLI's escape+v binding in hosts/cli/commands.py.
        if alt and not ctrl and not shift and event.key == pygame.K_v:
            self._paste_image_from_clipboard()
            return

        if event.key == pygame.K_ESCAPE:
            self.settings_overlay.toggle()
        elif event.key == pygame.K_TAB:
            self.gui_integration.get_scratchpad().toggle()
        elif event.key == pygame.K_F2:
            self.alignment_panel.toggle()
        elif event.key == pygame.K_F3:
            if self.gossip_panel.active:
                self.gossip_panel.dismiss()
            else:
                self.gossip_panel.active = True
        elif event.key == pygame.K_F4:
            self.memory_viewer.toggle()
        elif self.typewriter.active and not self.typewriter.is_complete():
            # Any key skips the typewriter to show full text
            self.typewriter.skip()
            self.history.update_last_text(self.typewriter.get_displayed_text())
        else:
            submitted = self.input_bar.handle_key(event)
            if submitted:
                self._submit_text(submitted)

    def _handle_textinput(self, event: pygame.event.Event) -> None:
        # SDL sometimes fires TEXTINPUT alongside KEYDOWN for Ctrl combos
        # (notably on X11 / WSLg), which would leak characters like "="
        # into the input bar when the user presses Ctrl+= to zoom.
        # Swallow any TEXTINPUT that arrives while Ctrl is held — the
        # KEYDOWN handler owns those shortcuts.
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            return
        if not self.input_bar.processing:
            self.input_bar.handle_textinput(event)

    def _submit_text(self, text: str) -> None:
        """Process user text submission and route to the agent pipeline."""
        # Drain any clipboard images queued via Alt+V before resetting the
        # input state — the placeholders ``[📎 image #N queued]`` already
        # appear in ``text`` so the user's bubble shows what they sent and
        # the agent sees a hint that images are riding alongside as parts.
        attachments = self._pending_images.copy()
        self._pending_images.clear()

        self.history.add(DialogueEntry("user", text, is_user=True, attachments=attachments or None))
        self.history.scroll_to_bottom()

        target = self.input_bar.waiting_for_agent or self.state.current_agent
        self.send_q.put((target, text, attachments))
        self.debug_log.record_user(target, text)
        self.input_bar.processing = True

        # Reset to Hephaestus for the incoming pipeline
        self.portrait.switch_to(self.input_bar.waiting_for_agent or "hephaestus")
        self.state.reset_for_input(self.input_bar.waiting_for_agent)
        self.input_bar.waiting_for_agent = None

        agent_quotes = AGENTS[self.state.current_agent].get("user_quotes", [])
        self.portrait.current_quote = (
            random.choice(agent_quotes) if agent_quotes else ""  # noqa: S311
        )

    # -- mouse ---------------------------------------------------------------

    def _handle_mousewheel(self, event: pygame.event.Event) -> None:
        # Ctrl + wheel = zoom (matches browser convention). Check this before
        # any panel-specific scroll routing so zoom works anywhere in the window.
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            if event.y > 0:
                self._adjust_font_scale(+0.1)
            elif event.y < 0:
                self._adjust_font_scale(-0.1)
            return

        # Route scroll to debug log if it's visible and mouse is near it
        if self.gui_integration.settings.get("show_debug_logs", False):
            mx, my = pygame.mouse.get_pos()
            panel_w = min(520, self.dialogue_rect.width - 20)
            debug_area = pygame.Rect(
                self.dialogue_rect.right - panel_w - 8,
                self.dialogue_rect.top + 8,
                panel_w,
                int(self.dialogue_rect.height * 0.45),
            )
            if debug_area.collidepoint(mx, my):
                self.debug_log.scroll(-event.y * 40)
                return
        self.history.scroll(-event.y * 40)

    def _handle_left_click(self, event: pygame.event.Event) -> None:
        if not self.input_bar.processing:
            action = self.quick_actions.handle_click(event.pos)
            if action:
                self._submit_quick_action(action)
                return

        clicked_agent = self.history.handle_click(event.pos, self.dialogue_rect)
        if clicked_agent and clicked_agent in AGENTS:
            self.portrait.switch_to(clicked_agent)
            agent_quotes = AGENTS.get(clicked_agent, {}).get("quotes", [])
            self.portrait.current_quote = (
                random.choice(agent_quotes) if agent_quotes else ""  # noqa: S311
            )

    def _submit_quick_action(self, action) -> None:
        """Process a quick-action button click."""
        self.history.add(DialogueEntry("user", action.display_text, is_user=True))
        self.history.scroll_to_bottom()

        payload = f"{action.display_text}\n\n{action.hidden_prompt}"
        self.send_q.put((action.agent, payload, []))
        self.debug_log.record_user(action.agent, action.display_text)
        self.input_bar.processing = True

        self.portrait.switch_to(action.agent)
        self.state.reset_for_input(action.agent)

        agent_quotes = AGENTS.get(self.state.current_agent, {}).get("user_quotes", [])
        self.portrait.current_quote = (
            random.choice(agent_quotes) if agent_quotes else ""  # noqa: S311
        )

    def _handle_right_click(self, event: pygame.event.Event) -> None:
        clicked_text = self.history.handle_right_click(event.pos, self.dialogue_rect)
        if clicked_text:
            try:
                pygame.scrap.put_text(clicked_text)
                self.audio_manager.play_sfx()
                self.history.add(
                    DialogueEntry(agent="system", text="Copied to clipboard.", is_system=True)
                )
            except Exception as e:
                logger.warning("Clipboard error: %s", e)

    # -- resize --------------------------------------------------------------

    # -- clipboard helpers ---------------------------------------------------

    def _copy_hovered_to_clipboard(self) -> None:
        """Ctrl+Shift+C — copy the dialogue entry under the cursor to the
        system clipboard.  If the cursor isn't over any entry, copy the
        most recent one as a fallback (most useful for screenshotting the
        latest agent speech).
        """
        mouse_pos = pygame.mouse.get_pos()
        text = self.history.handle_right_click(mouse_pos, self.dialogue_rect)

        if not text:
            # Fallback: most recent entry.  `_entries` is the private
            # list the history keeps; grabbing [-1] is cheap and always
            # the last thing the player saw.
            entries = getattr(self.history, "_entries", None)
            if entries:
                text = entries[-1].text

        if not text:
            return

        try:
            pygame.scrap.put_text(text)
            self.audio_manager.play_sfx()
            self.history.add(
                DialogueEntry(agent="system", text="Copied to clipboard.", is_system=True)
            )
            logger.debug("Ctrl+Shift+C copied %d chars to clipboard", len(text))
        except Exception as e:
            logger.warning("Clipboard error on Ctrl+Shift+C: %s", e)

    def _paste_text_from_clipboard(self) -> None:
        """Ctrl+V — pull text from the clipboard into the input bar.

        SDL's TEXTINPUT leak (see _handle_textinput) is already blocked
        when Ctrl is held, so this keydown handler owns the paste path.
        """
        if self.input_bar.processing:
            return
        try:
            text = pygame.scrap.get_text()
        except Exception as e:
            logger.warning("Clipboard read failed on Ctrl+V: %s", e)
            return

        if not text:
            return

        # Normalise line endings and strip trailing newline (most users
        # don't want the literal \n after a paste).
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = cleaned.removesuffix("\n")

        self.input_bar.text += cleaned
        logger.debug("Ctrl+V inserted %d chars from clipboard", len(cleaned))

    def _paste_image_from_clipboard(self) -> None:
        """Alt+V — grab a clipboard image and queue it as an attachment.

        Uses PIL.ImageGrab.grabclipboard() — the same path the CLI uses
        in hosts/cli/commands.py::_capture_image.  On success, the image
        is base64-encoded and appended to `self._pending_images`; an
        input-bar placeholder ``[📎 image #N queued]`` confirms capture.
        ``_submit_text`` drains the list at submit time and forwards it
        as the third slot of the ``send_q`` 3-tuple, so GuiClient builds
        a multi-part A2A ``Message`` (TextPart + FilePart) just like the
        CLI's ``send_and_stream``.
        """
        try:
            from PIL import ImageGrab  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("Alt+V failed: Pillow not installed (uv add Pillow)")
            self.input_bar.text += "[Pillow not installed]"
            return

        try:
            img = ImageGrab.grabclipboard()
        except Exception as e:
            logger.warning("Alt+V image grab failed: %s", e)
            self.input_bar.text += f"[image capture failed: {e}]"
            return

        if img is None:
            logger.debug("Alt+V: clipboard has no image.")
            self.input_bar.text += "[no image in clipboard]"
            return
        if isinstance(img, list):
            # On some platforms the clipboard contains file *paths*
            # rather than pixel data.  Mirror the CLI's behaviour.
            logger.debug("Alt+V: clipboard contains file paths, not pixel data.")
            self.input_bar.text += "[clipboard contains files, not an image]"
            return

        import base64
        import io as _io

        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        self._pending_images.append((b64, "image/png"))
        n = len(self._pending_images)
        placeholder = f"[\U0001f4ce image #{n} queued]"
        self.input_bar.text += placeholder
        logger.debug("Alt+V queued image #%d (%d base64 chars)", n, len(b64))

    # -- zoom helpers --------------------------------------------------------
    # VSCode-style: content scales, window stays fixed.  The FontScaler
    # value is read by the main loop in __main__.py, which renders to a
    # virtual surface sized ``screen_size / scale`` and smoothscales it up
    # to the real screen — Ctrl+= → virtual shrinks → upscale grows text.

    def _adjust_font_scale(self, delta: float) -> None:
        """Step the zoom factor (persists via settings; main loop reads it)."""
        scaler = self.gui_integration.get_font_scaler()
        self._set_font_scale(scaler.scale + delta)

    def _set_font_scale(self, scale: float) -> None:
        """Set absolute zoom factor.  Range clamped by FontScaler (0.8-2.0x).

        Pushes the new value through to the FontProxy registry in
        constants.py so every cached pygame.freetype.Font is dropped and
        the next frame re-rasterises at the new size — crisp, not scaled.
        """
        from .constants import set_font_scale as push_font_scale

        scaler = self.gui_integration.get_font_scaler()
        old = scaler.scale
        scaler.set_scale(scale)
        if scaler.scale != old:
            push_font_scale(scaler.scale)
            self.gui_integration.save_all_settings()
            logger.info("Zoom → %.2fx (was %.2fx)", scaler.scale, old)

    def _handle_resize(self, event: pygame.event.Event) -> None:
        screen_w, screen_h = self.display.handle_resize(
            event, settings=self.gui_integration.settings
        )
        self.sync_layout(screen_w, screen_h)
