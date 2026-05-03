"""Unit tests for hosts.gui.tts_helper.speak_async.

Verifies the threading wrapper forwards M20 sub-task 2 callbacks
(on_audio_start + on_word) into RealtimeTTSEngine.speak_sync without
blocking the GUI's pygame loop.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from hosts.gui.tts_helper import speak_async


def _wait_for_thread(timeout: float = 1.0) -> None:
    """Give the daemon thread a moment to call speak_sync.

    Joins every non-main daemon thread that's currently alive so the
    assertion phase sees a stable engine state.
    """
    deadline = threading.current_thread()
    for t in list(threading.enumerate()):
        if t is deadline or not t.daemon:
            continue
        t.join(timeout=timeout)


def _make_manager(*, enable_tts: bool = True, engine: object | None = "default") -> MagicMock:
    mgr = MagicMock()
    if engine == "default":
        engine = MagicMock()
    mgr.tts_engine = engine
    mgr.enable_tts = enable_tts
    return mgr


def test_speak_async_noop_when_no_engine() -> None:
    mgr = _make_manager(engine=None)
    speak_async("hello", "hephaestus", mgr)
    # No engine → no thread spawned → nothing to assert beyond no-raise.


def test_speak_async_noop_when_tts_disabled_and_not_forced() -> None:
    mgr = _make_manager(enable_tts=False)
    speak_async("hello", "hephaestus", mgr)
    _wait_for_thread()
    mgr.tts_engine.speak_sync.assert_not_called()


def test_speak_async_calls_speak_sync_with_text_and_agent() -> None:
    mgr = _make_manager()
    speak_async("hello world", "hephaestus", mgr)
    _wait_for_thread()
    mgr.tts_engine.speak_sync.assert_called_once()
    args, kwargs = mgr.tts_engine.speak_sync.call_args
    assert args == ("hello world",)
    assert kwargs["agent_name"] == "hephaestus"


def test_speak_async_force_overrides_disabled_tts() -> None:
    mgr = _make_manager(enable_tts=False)
    speak_async("question", "metis", mgr, force=True)
    _wait_for_thread()
    mgr.tts_engine.speak_sync.assert_called_once()


def test_speak_async_forwards_on_audio_start_kwarg() -> None:
    """M20 sub-task 2 Tier 2: the audio-start callback must reach the
    engine's speak_sync so the typewriter / display can fire on playback start.
    """
    mgr = _make_manager()
    cb = MagicMock(name="audio_start")
    speak_async("hi", "hephaestus", mgr, on_audio_start=cb)
    _wait_for_thread()
    kwargs = mgr.tts_engine.speak_sync.call_args.kwargs
    assert kwargs["on_audio_start"] is cb


def test_speak_async_forwards_on_word_kwarg() -> None:
    """M20 sub-task 2 Tier 1: the on_word callback drives the word-paced
    typewriter — must reach speak_sync verbatim or word-by-word reveal breaks.
    """
    mgr = _make_manager()
    cb = MagicMock(name="word")
    speak_async("hi", "hephaestus", mgr, on_word=cb)
    _wait_for_thread()
    kwargs = mgr.tts_engine.speak_sync.call_args.kwargs
    assert kwargs["on_word"] is cb


def test_speak_async_default_kwargs_are_none() -> None:
    """Callers who don't opt into Tier 1/2 still get speak_sync called
    with explicit None for both kwargs (no positional drift)."""
    mgr = _make_manager()
    speak_async("hi", "hephaestus", mgr)
    _wait_for_thread()
    kwargs = mgr.tts_engine.speak_sync.call_args.kwargs
    assert kwargs["on_audio_start"] is None
    assert kwargs["on_word"] is None
