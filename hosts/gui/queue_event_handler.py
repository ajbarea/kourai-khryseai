"""Queue event handler — routes recv_q messages to typed handlers.

Each A2A event type (connected, disconnected, status, result, complete,
error) has its own method, making the logic testable and the main loop readable.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from .dialogue import DialogueEntry
from .emote_sfx import play_emote_sfx
from .maidens import (
    AGENTS,
    HANDOFF_GENERIC,
    HANDOFF_LINES,
    VICTORY_LINES,
    detect_agent,
)
from .message_classifier import is_scratchpad_content, is_system_status
from .tts_gui_integration import extract_speakable
from .tts_helper import speak_async

if TYPE_CHECKING:
    from kourai_common.audio import AudioManager

    from .debug_log import DebugLog
    from .dialogue import DialogueHistory
    from .flash_effect import FlashEffect
    from .gui_components_integration import GUIComponentsIntegration
    from .gui_state import GUIState
    from .input_bar import InputBar
    from .portrait import PortraitPanel
    from .tts_gui_integration import TTSGUIManager
    from .typewriter import TypewriterManager

logger = logging.getLogger(__name__)


class QueueEventHandler:
    """Routes recv_q messages to per-type handlers."""

    def __init__(
        self,
        state: GUIState,
        history: DialogueHistory,
        portrait: PortraitPanel,
        input_bar: InputBar,
        typewriter: TypewriterManager,
        flash: FlashEffect,
        tts_manager: TTSGUIManager,
        gui_integration: GUIComponentsIntegration,
        audio_manager: AudioManager,
        debug_log: DebugLog,
    ) -> None:
        self.state = state
        self.history = history
        self.portrait = portrait
        self.input_bar = input_bar
        self.typewriter = typewriter
        self.flash = flash
        self.tts_manager = tts_manager
        self.gui_integration = gui_integration
        self.audio_manager = audio_manager
        self.debug_log = debug_log

    # -- public entry point --------------------------------------------------

    def process_event(self, q_event: dict) -> None:
        """Dispatch a single recv_q event to the appropriate handler."""
        etype = q_event.get("type")
        logger.debug("recv_q event: %s", etype)

        # Every A2A event goes to the debug log
        self.debug_log.record(q_event)

        if etype == "connected":
            self._handle_connected(q_event)
        elif etype == "disconnected":
            self._handle_disconnected()
        elif etype == "status":
            self._handle_status(q_event)
        elif etype == "result":
            self._handle_result(q_event)
        elif etype == "complete":
            self._handle_complete(q_event)
        elif etype == "error":
            self._handle_error(q_event)
        elif etype == "user":
            # Scripted-demo affordance — real user input is injected by
            # pygame_event_handler when the player types into the input bar,
            # so a "user" event never arrives from the real A2A client.
            # Harmless for production.
            self._handle_user(q_event)

    # -- private handlers ----------------------------------------------------

    def _handle_connected(self, event: dict) -> None:
        self.state.connected = True
        self.gui_integration.status_bubbles.add_status_message(
            f"[system] Connected to {event.get('name', 'Hephaestus')}"
        )
        greeting = "The forge is hot. What are we building?"
        self.history.add(DialogueEntry("hephaestus", greeting))
        self.history.scroll_to_bottom()
        speak_async(greeting, "hephaestus", self.tts_manager)

    def _handle_disconnected(self) -> None:
        self.state.connected = False

    def _handle_status(self, event: dict) -> None:
        raw = event["text"]
        agent, text = detect_agent(raw)
        if not text:
            return

        if "INPUT_REQUIRED:" in text:
            self._handle_input_required(agent, text)
            return

        effective_agent = agent or self.state.current_agent

        if agent:
            self._maybe_handoff(agent)
            self.state.track_specialist(agent)

        self._route_status_text(effective_agent, text)
        self.history.scroll_to_bottom()

    def _handle_input_required(self, agent: str | None, text: str) -> None:
        question = text.split("INPUT_REQUIRED:", 1)[1].strip()
        speaking_agent = agent or self.state.current_agent
        self.input_bar.waiting_for_agent = speaking_agent
        self.input_bar.processing = False
        self._add_with_typewriter(DialogueEntry(speaking_agent, question))
        self.history.scroll_to_bottom()
        # WHY force=True: INPUT_REQUIRED questions must be heard even if TTS is off
        speak_async(question, speaking_agent, self.tts_manager, force=True)

    def _maybe_handoff(self, new_agent: str) -> None:
        """Handle agent switch with handoff chatter and portrait flash."""
        if new_agent == self.state.current_agent:
            return

        # Handoff line from the outgoing agent
        key = (self.state.current_agent, new_agent)
        lines = HANDOFF_LINES.get(key) or HANDOFF_GENERIC.get(self.state.current_agent)
        if lines:
            handoff_line = random.choice(lines)  # noqa: S311
            self._add_with_typewriter(DialogueEntry(self.state.current_agent, handoff_line))
            play_emote_sfx(handoff_line, self.state.current_agent, self.audio_manager)

        self.portrait.switch_to(new_agent)
        self.flash.trigger()
        agent_quotes = AGENTS.get(new_agent, {}).get("quotes", [])
        self.portrait.current_quote = (
            random.choice(agent_quotes) if agent_quotes else ""  # noqa: S311
        )
        self.state.switch_agent(new_agent)
        self.tts_manager.set_current_agent(new_agent)
        self.gui_integration.get_scratchpad().set_active_agent(new_agent)

    def _route_status_text(self, agent: str, text: str) -> None:
        """Classify and route a status message to the right subsystem."""
        if is_system_status(text):
            self.gui_integration.status_bubbles.add_status_message(f"[{agent}] {text}")
        elif is_scratchpad_content(text):
            self.gui_integration.get_scratchpad().add_plan(text, agent)
        else:
            self._add_with_typewriter(DialogueEntry(agent, text))
            play_emote_sfx(text, agent, self.audio_manager)
            speakable = extract_speakable(text)
            if speakable:
                speak_async(speakable, agent, self.tts_manager)

    def _handle_result(self, event: dict) -> None:
        text = event["text"]
        self._add_with_typewriter(DialogueEntry(self.state.result_agent, text, is_result=True))
        self.history.scroll_to_bottom()
        speakable = extract_speakable(text)
        if speakable:
            speak_async(speakable, self.state.result_agent, self.tts_manager)

    def _handle_complete(self, event: dict) -> None:
        elapsed = event.get("elapsed", 0.0)
        self.input_bar.processing = False

        vlines = VICTORY_LINES.get(self.state.last_agent, [])
        if vlines:
            victory_text = random.choice(vlines)  # noqa: S311
            self._add_with_typewriter(DialogueEntry(self.state.last_agent, victory_text))
            play_emote_sfx(victory_text, self.state.last_agent, self.audio_manager)
            speak_async(victory_text, self.state.last_agent, self.tts_manager)

        self.gui_integration.status_bubbles.add_status_message(
            f"[system] * Completed in {elapsed:.1f}s"
        )
        self.history.scroll_to_bottom()

    def _handle_error(self, event: dict) -> None:
        logger.error("Pipeline error: %s", event.get("text", "unknown"))
        self.history.add(DialogueEntry("hephaestus", event["text"], is_error=True))
        self.input_bar.processing = False
        self.history.scroll_to_bottom()

    def _handle_user(self, event: dict) -> None:
        """Append a user-attributed dialogue entry.

        Only the scripted demo client emits this — the real A2A stream
        never puts `user` events on recv_q (user text enters via send_q
        and is rendered directly by the pygame event handler).
        """
        text = event.get("text", "")
        if not text:
            return
        self.history.add(DialogueEntry("user", text, is_user=True))
        self.history.scroll_to_bottom()

    # -- typewriter helper ---------------------------------------------------

    def _add_with_typewriter(self, entry: DialogueEntry) -> None:
        """Add a dialogue entry, animating it with the typewriter effect."""
        try:
            logger.debug("Adding dialogue: %s | %s...", entry.agent, entry.text[:50])
            # Finalize any in-progress typewriter entry before starting a new one
            if self.typewriter.active or self.state.typewriter_full_text:
                self.history.update_last_text(self.state.typewriter_full_text)
                self.typewriter.reset()
            self.state.typewriter_full_text = entry.text
            if not entry.is_system and not entry.is_user:
                entry.text = ""  # start empty; typewriter fills it in
                self.history.add(entry)
                self.typewriter.start(self.state.typewriter_full_text)
            else:
                self.history.add(entry)
                self.state.typewriter_full_text = ""
        except Exception as e:
            logger.exception("Error adding dialogue entry: %s", e)
