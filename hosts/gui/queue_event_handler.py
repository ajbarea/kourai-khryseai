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
        logger.info("Connected to %s", event.get("name", "Hephaestus"))
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

    def _route_status_text(self, agent: str, text: str) -> None:
        """Classify and route a status message to the right subsystem.

        System-status (`* Connected`, `* Completed`) and scratchpad-shaped
        (TODO / CoT bullets) messages used to feed dedicated GUI widgets
        that #173 pruned. Drop them silently here until the cross-host
        ``status_feed`` / ``scratchpad`` rebuilds land — same effective
        UX as pre-#173 (those widgets weren't actually rendered, just
        instantiated) and avoids the AttributeError that would otherwise
        fire on every classified message.
        """
        if is_scratchpad_content(text):
            # Cross-host scratchpad rebuild: route reasoning into the
            # shared kourai_common.scratchpad buffer. CLI's /scratchpad
            # slash command already reads from the same buffer; a GUI
            # overlay renderer can land later without further plumbing.
            from kourai_common.scratchpad import get_scratchpad

            get_scratchpad().add(agent, text)
            return
        if is_system_status(text):
            logger.debug("system status from %s: %r", agent, text[:60])
            return
        speakable = extract_speakable(text)
        if self._will_speak(speakable):
            # M20 sub-task 2 Tier 1 (audio-led): typewriter pace = TTS word events.
            self._add_with_word_paced_typewriter(DialogueEntry(agent, text))
            play_emote_sfx(text, agent, self.audio_manager)
            speak_async(
                speakable,
                agent,
                self.tts_manager,
                on_word=self._on_tts_word,
                on_audio_start=self._on_tts_audio_start,
            )
        else:
            # Time-based typewriter. M20 sub-task 4: in "instant"
            # mode TTS still fires (audio catches up to text);
            # legacy behavior for players who prefer text-first.
            self._add_with_typewriter(DialogueEntry(agent, text))
            play_emote_sfx(text, agent, self.audio_manager)
            if self._tts_unsynced_enabled(speakable):
                speak_async(speakable, agent, self.tts_manager)

    def _handle_result(self, event: dict) -> None:
        text = event["text"]
        speakable = extract_speakable(text)
        if self._will_speak(speakable):
            self._add_with_word_paced_typewriter(
                DialogueEntry(self.state.result_agent, text, is_result=True)
            )
            self.history.scroll_to_bottom()
            speak_async(
                speakable,
                self.state.result_agent,
                self.tts_manager,
                on_word=self._on_tts_word,
                on_audio_start=self._on_tts_audio_start,
            )
        else:
            self._add_with_typewriter(DialogueEntry(self.state.result_agent, text, is_result=True))
            self.history.scroll_to_bottom()
            if self._tts_unsynced_enabled(speakable):
                speak_async(speakable, self.state.result_agent, self.tts_manager)

    # -- Tier 1 callbacks (fire from TTS daemon thread) ----------------------

    def _on_tts_audio_start(self) -> None:
        """Drop the synthesis-indicator placeholder when the engine
        begins playback. The dialogue body returns to its real state
        (empty until the first ``on_word`` fires); the maiden's
        portrait + name were already visible from the moment the
        entry was added.
        """
        try:
            self.typewriter.clear_pending_audio()
        except Exception:
            logger.exception("on_tts_audio_start clear failed")

    def _on_tts_word(self, _word: object) -> None:
        """Advance the typewriter cursor by one source word. Called from
        the TTS daemon thread per spoken word — `displayed_chars` is a
        single int write, safe under the GIL for the pygame draw loop's
        intermittent reads.
        """
        try:
            self.typewriter.advance_word()
        except Exception:
            logger.exception("on_tts_word advance failed")

    def _handle_complete(self, event: dict) -> None:
        elapsed = event.get("elapsed", 0.0)
        self.input_bar.processing = False

        vlines = VICTORY_LINES.get(self.state.last_agent, [])
        if vlines:
            victory_text = random.choice(vlines)  # noqa: S311
            self._add_with_typewriter(DialogueEntry(self.state.last_agent, victory_text))
            play_emote_sfx(victory_text, self.state.last_agent, self.audio_manager)
            speak_async(victory_text, self.state.last_agent, self.tts_manager)

        logger.info("Pipeline completed in %.1fs", elapsed)
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

    def _add_with_word_paced_typewriter(self, entry: DialogueEntry) -> None:
        """M20 sub-task 2 Tier 1 GUI variant of :meth:`_add_with_typewriter`.

        Starts the typewriter in word-paced mode so the cursor only
        advances when ``advance_word()`` is called from the TTS engine's
        ``on_word`` trampoline. System / user entries fall back to
        instant render — those don't go through TTS.

        Note: if a NEW dialogue entry arrives while the OLD entry's TTS
        is still firing on_word, the reset below clears the old word-
        pace state and the stale callbacks become no-ops because the
        new typewriter state has either started fresh or finished.
        """
        try:
            logger.debug("Word-paced dialogue: %s | %s...", entry.agent, entry.text[:50])
            if self.typewriter.active or self.state.typewriter_full_text:
                self.history.update_last_text(self.state.typewriter_full_text)
                self.typewriter.reset()
            self.state.typewriter_full_text = entry.text
            if not entry.is_system and not entry.is_user:
                entry.text = ""
                self.history.add(entry)
                self.typewriter.start_word_paced(self.state.typewriter_full_text)
                # Arm the synthesis indicator: dialogue body renders
                # `…` until on_audio_start fires (~3s on Kokoro CPU)
                # so the player sees the agent is loading instead of
                # an empty panel below the portrait.
                self.typewriter.set_pending_audio()
            else:
                self.history.add(entry)
                self.state.typewriter_full_text = ""
        except Exception as e:
            logger.exception("Error adding word-paced dialogue entry: %s", e)

    def _will_speak(self, speakable: str) -> bool:
        """True iff TTS is wired AND enabled AND the player picked
        ``dialogue_sync_mode = "audio-led"`` (M20 sub-task 4). Gates
        the word-paced typewriter path; callers fall back to the
        time-based typewriter (and instant TTS, audio catches up to
        text) when this returns False.
        """
        if not speakable:
            return False
        engine = getattr(self.tts_manager, "tts_engine", None)
        if engine is None or not bool(getattr(self.tts_manager, "enable_tts", False)):
            return False
        return getattr(self.tts_manager, "dialogue_sync_mode", "audio-led") == "audio-led"

    def _tts_unsynced_enabled(self, speakable: str) -> bool:
        """True iff TTS should fire WITHOUT word-pace synchronization —
        the M20 sub-task 4 ``"instant"`` mode where audio catches up to
        an immediately-revealed text typewriter. Returns False when TTS
        is off entirely or when the player picked ``audio-led`` (which
        goes through ``_will_speak`` instead).
        """
        if not speakable:
            return False
        engine = getattr(self.tts_manager, "tts_engine", None)
        if engine is None or not bool(getattr(self.tts_manager, "enable_tts", False)):
            return False
        return getattr(self.tts_manager, "dialogue_sync_mode", "audio-led") != "audio-led"
