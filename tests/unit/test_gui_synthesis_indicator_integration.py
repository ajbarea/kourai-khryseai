"""GUI synthesis indicator wiring — `QueueEventHandler` ↔ `TypewriterManager`.

The CLI surface ships a pre-rendered indicator before `await tts.speak(...)`
(see `hosts/cli/streaming.py` + `synthesis_indicator` helper). The GUI
equivalent uses `TypewriterManager.set_pending_audio` so the dialogue
panel renders a single-ellipsis placeholder during the ~3s Kokoro
synthesis-wait window.

These tests pin the wiring at the seam: `QueueEventHandler` calls
`set_pending_audio()` after `start_word_paced(...)` so the placeholder
appears, and clears it from `_on_tts_audio_start` so the dialogue body
returns to its real state the moment the engine begins playback.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hosts.gui.queue_event_handler import QueueEventHandler


def _make_handler(typewriter: MagicMock) -> QueueEventHandler:
    """Minimal handler — the synthesis-indicator wiring only touches
    typewriter, history, state, gui_integration."""
    history = MagicMock()
    state = MagicMock()
    state.typewriter_full_text = ""
    state.last_agent = "hephaestus"
    state.result_agent = "hephaestus"
    return QueueEventHandler(
        state=state,
        history=history,
        portrait=MagicMock(),
        input_bar=MagicMock(),
        typewriter=typewriter,
        flash=MagicMock(),
        tts_manager=MagicMock(),
        gui_integration=MagicMock(),
        audio_manager=MagicMock(),
        debug_log=MagicMock(),
    )


def test_on_tts_audio_start_clears_pending_audio():
    """When the engine signals playback start, the placeholder must be
    wiped so the dialogue body returns to the real (empty until
    on_word fires) typewriter state."""
    typewriter = MagicMock()
    handler = _make_handler(typewriter)

    handler._on_tts_audio_start()

    typewriter.clear_pending_audio.assert_called_once()


def test_word_paced_typewriter_sets_pending_audio_after_start():
    """`_add_with_word_paced_typewriter` must arm the placeholder
    immediately after `start_word_paced(...)` so the dialogue panel
    shows feedback during synthesis."""
    typewriter = MagicMock()
    typewriter.active = False  # forces the start-fresh branch
    handler = _make_handler(typewriter)

    from hosts.gui.dialogue import DialogueEntry

    entry = DialogueEntry("hephaestus", "Hello world from the forge")
    handler._add_with_word_paced_typewriter(entry)

    # Both calls fired — and `set_pending_audio` came AFTER
    # `start_word_paced` so the typewriter is already in word-paced
    # mode when the indicator arms.
    typewriter.start_word_paced.assert_called_once_with("Hello world from the forge")
    typewriter.set_pending_audio.assert_called_once()
    # Order check: start_word_paced must precede set_pending_audio in
    # the call list (otherwise set_pending_audio would no-op because
    # _word_paced is still False).
    method_calls = [c[0] for c in typewriter.method_calls]
    start_idx = method_calls.index("start_word_paced")
    pending_idx = method_calls.index("set_pending_audio")
    assert start_idx < pending_idx, (
        f"set_pending_audio must follow start_word_paced; got {method_calls}"
    )


def test_legacy_typewriter_does_not_set_pending_audio():
    """The time-based `_add_with_typewriter` is the instant-mode /
    non-TTS path — no synthesis-wait gap to fill, so the placeholder
    must NOT arm there (would leak into instant-mode renders)."""
    typewriter = MagicMock()
    typewriter.active = False
    handler = _make_handler(typewriter)

    from hosts.gui.dialogue import DialogueEntry

    entry = DialogueEntry("hephaestus", "Status: building tests")
    handler._add_with_typewriter(entry)

    typewriter.start.assert_called_once_with("Status: building tests")
    typewriter.set_pending_audio.assert_not_called()
