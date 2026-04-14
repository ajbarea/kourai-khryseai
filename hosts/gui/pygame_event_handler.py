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

    from .alignment_gauges import AlignmentGaugePanel
    from .audio_manager import AudioManager
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
    from .settings_ui import SettingsOverlay
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
        if not self.input_bar.processing:
            self.input_bar.handle_textinput(event)

    def _submit_text(self, text: str) -> None:
        """Process user text submission and route to the agent pipeline."""
        self.history.add(DialogueEntry("user", text, is_user=True))
        self.history.scroll_to_bottom()

        target = self.input_bar.waiting_for_agent or self.state.current_agent
        self.send_q.put((target, text))
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
        self.send_q.put((action.agent, payload))
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

    def _handle_resize(self, event: pygame.event.Event) -> None:
        screen_w, screen_h = self.display.handle_resize(
            event, settings=self.gui_integration.settings
        )
        self.sync_layout(screen_w, screen_h)
