"""Captions toggle (#19) — host CLI gates dialogue rendering on settings.

When ``captions_enabled=False`` AND TTS is available AND the emission is
tagged ``KIND_DIALOGUE``, the visual comms-window render is suppressed so
the player gets an audio-only mode. Status / code / spec emissions and
the artifact-rendering block are unaffected. With no TTS engine, captions
fall back to ON to avoid silently dropping dialogue.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.types import Task, TaskState, TaskStatusUpdateEvent

from hosts.cli.streaming import send_and_stream
from kourai_common.messaging import KIND_DIALOGUE, KIND_STATUS, ContentKind, kind_message
from tests.conftest import make_stream_response


def _completed_task() -> MagicMock:
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status = MagicMock()
    task.status.state = TaskState.TASK_STATE_COMPLETED
    return task


def _status_event(text: str, kind: ContentKind) -> MagicMock:
    """Build a TaskStatusUpdateEvent whose inner message carries the given kind."""
    inner = kind_message(text, kind, context_id="ctx-1", task_id="task-1")
    event = MagicMock(spec=TaskStatusUpdateEvent)
    event.context_id = "ctx-1"
    event.task_id = "task-1"
    event.status = MagicMock()
    event.status.state = TaskState.TASK_STATE_WORKING
    event.status.message = inner
    return event


@pytest.fixture
def _captured(monkeypatch):
    """Capture every visual ``_echo`` call. Stub markdown render and the
    status-formatting helper so the captured string is easy to assert on.
    Accepts ``nl=`` kwarg for M20 sub-task 2 Tier 1 karaoke writes that
    use ``_echo(text, nl=False)`` to stream words without trailing
    newlines.
    """
    captured: list[str] = []

    def _capture(text: str = "", nl: bool = True) -> None:
        del nl  # _echo signature parity; only `text` matters for assertions
        captured.append(text)

    monkeypatch.setattr("hosts.cli.streaming._echo", _capture)
    # speak_with_karaoke lives in hosts.cli.rendering and references _echo
    # from that module's globals, so the karaoke open/word/close writes
    # need their own patch — streaming._echo is a separate binding.
    monkeypatch.setattr("hosts.cli.rendering._echo", _capture)
    monkeypatch.setattr("hosts.cli.streaming._render_markdown", lambda text: text)
    monkeypatch.setattr("hosts.cli.streaming._extract_artifact_text", lambda _: "")
    monkeypatch.setattr(
        "hosts.cli.streaming._maidenify_status",
        lambda text: (f"[FORMATTED] {text}", "kallos"),
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_status_text",
        lambda event: event.status.message.parts[0].text,
    )
    return captured


def _client_yielding(events) -> MagicMock:
    client = MagicMock()

    async def _events():
        for e in events:
            yield make_stream_response(e)

    client.send_message = MagicMock(return_value=_events())
    return client


@pytest.mark.asyncio
async def test_captions_off_with_tts_suppresses_dialogue_visual(_captured):
    """captions_enabled=False + tts set + KIND_DIALOGUE → no visual."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=False)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" not in visual
    tts.speak.assert_awaited()


@pytest.mark.asyncio
async def test_captions_on_with_tts_renders_dialogue_visual(_captured):
    """captions_enabled=True (default) + tts → visual still renders."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" in visual
    tts.speak.assert_awaited()


@pytest.mark.asyncio
async def test_captions_off_without_tts_still_renders_dialogue(_captured):
    """captions_enabled=False + tts=None → visual renders so dialogue
    isn't silently dropped (no engine to speak it)."""
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=None, captions_enabled=False)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" in visual


@pytest.mark.asyncio
async def test_captions_off_does_not_affect_status_events(_captured):
    """KIND_STATUS emissions render regardless of the captions toggle —
    captions controls dialogue visibility, not the whole UI."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    status = _status_event("Routing pipeline...", KIND_STATUS)
    client = _client_yielding([status, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=False)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" in visual
    # Status-tagged emissions never speak.
    tts.speak.assert_not_awaited()


@pytest.mark.asyncio
async def test_speak_invoked_with_audio_start_and_word_callbacks(_captured):
    """Both the Tier 2 (audio_start) and Tier 1 (on_word) per-call
    handlers must be passed to engine.speak() — the engine trampolines
    dispatch to them from RealtimeTTS's playback events.
    """
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    call_kwargs = tts.speak.await_args.kwargs
    assert "on_audio_start" in call_kwargs and callable(call_kwargs["on_audio_start"])
    assert "on_word" in call_kwargs and callable(call_kwargs["on_word"])


@pytest.mark.asyncio
async def test_dialogue_karaoke_reveals_words_progressively(_captured):
    """M20 sub-task 2 Tier 1: when TTS fires on_audio_start AND on_word
    during speak(), the dialogue surfaces as a single-line karaoke
    render (header → words → close) rather than the box. Each word
    appears in its own write so a player tailing stdout sees the
    progressive reveal.
    """

    async def _karaoke_speak(*args, on_audio_start=None, on_word=None, **kwargs):
        if on_audio_start is not None:
            on_audio_start()
        if on_word is not None:
            on_word(MagicMock(word="hello"))
            on_word(MagicMock(word="world"))
            on_word(MagicMock(word="."))

    tts = MagicMock()
    tts.speak = AsyncMock(side_effect=_karaoke_speak)
    dialogue = _status_event('"Hello world."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    # Karaoke uses _echo per word (no trailing newlines), then close.
    # Tier 2's `[FORMATTED]` box must NOT appear — Tier 1 took the path.
    visual = "\n".join(_captured)
    assert "[FORMATTED]" not in visual
    # Header opens the quote, words then appear, close ends with a quote+newline.
    assert any("hello" in line for line in _captured)
    assert any("world" in line for line in _captured)
    # Punctuation has no leading space — period attaches to "world".
    assert "." in _captured  # standalone punctuation echo


@pytest.mark.asyncio
async def test_dialogue_karaoke_falls_back_to_static_when_no_words_revealed(_captured):
    """If on_audio_start fires but on_word never does (Kokoro CPU engine,
    auto-muted path, etc.), the karaoke path falls back to rendering the
    full formatted dialogue text — otherwise the user sees a bare empty
    quote pair "" instead of the line.
    """

    async def _audio_only_speak(*args, on_audio_start=None, on_word=None, **kwargs):
        if on_audio_start is not None:
            on_audio_start()
        # No on_word call.

    tts = MagicMock()
    tts.speak = AsyncMock(side_effect=_audio_only_speak)
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    visual = "".join(_captured)
    # Karaoke started but no words: render the full formatted text so the
    # dialogue is visible rather than collapsing to an empty quote pair.
    assert "[FORMATTED]" in visual
    assert "Welcome back to the forge." in visual


@pytest.mark.asyncio
async def test_instant_mode_echoes_immediately_then_speaks(_captured):
    """M20 sub-task 4: when dialogue_sync_mode='instant', the legacy
    behavior returns — formatted text echoes immediately and TTS fires
    in parallel without on_audio_start / on_word callbacks. No karaoke
    deferral.
    """
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(
        client,
        "prompt",
        "ctx-1",
        tts=tts,
        captions_enabled=True,
        dialogue_sync_mode="instant",
    )

    # Visual echoed exactly once via the immediate-render path.
    visual_lines = [line for line in _captured if "[FORMATTED]" in line]
    assert len(visual_lines) == 1
    # speak() called WITHOUT the audio-led callbacks.
    tts.speak.assert_awaited_once()
    call_kwargs = tts.speak.await_args.kwargs
    assert "on_audio_start" not in call_kwargs
    assert "on_word" not in call_kwargs


@pytest.mark.asyncio
async def test_audio_led_mode_is_default_when_kwarg_omitted(_captured):
    """Backwards-compat — `dialogue_sync_mode` defaults to 'audio-led'
    so existing callers get the karaoke path without opting in."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    # No kwarg passed → default audio-led → karaoke path → on_word + on_audio_start present.
    call_kwargs = tts.speak.await_args.kwargs
    assert callable(call_kwargs.get("on_audio_start"))
    assert callable(call_kwargs.get("on_word"))


@pytest.mark.asyncio
async def test_dialogue_visual_falls_back_when_on_audio_start_never_fires(_captured):
    """If TTS auto-mute is on or the engine errors before audio starts,
    on_audio_start never fires and the finally-fallback echoes the
    dialogue so it isn't silently lost.
    """
    tts = MagicMock()
    tts.speak = AsyncMock()  # default: doesn't fire on_audio_start
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    visual_lines = [line for line in _captured if "[FORMATTED]" in line]
    assert len(visual_lines) == 1, "fallback echo must fire when callback didn't"
    tts.speak.assert_awaited()


@pytest.mark.asyncio
async def test_synthesis_indicator_renders_before_speak(_captured):
    """M20 sub-task 2 polish: a per-agent indicator (`Name face …`) is
    echoed BEFORE `await tts.speak(...)` so the player has visible
    feedback during the ~3s Kokoro CPU synthesis-wait window. Without
    this the audio-led path shows nothing on stdout for several seconds
    after the agent decides to talk.
    """
    speak_call_index: list[int] = []

    async def _record_then_speak(*args, on_audio_start=None, on_word=None, **kwargs):
        # Record how many _echo calls happened before tts.speak() ran.
        speak_call_index.append(len(_captured))
        if on_audio_start is not None:
            on_audio_start()
        if on_word is not None:
            on_word(MagicMock(word="hi"))

    tts = MagicMock()
    tts.speak = AsyncMock(side_effect=_record_then_speak)
    dialogue = _status_event('"Hi."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    # At least one _echo call must precede speak().
    assert speak_call_index and speak_call_index[0] >= 1, (
        f"expected indicator echo before speak(); got {speak_call_index} pre-speak echoes"
    )
    pre_speak = _captured[: speak_call_index[0]]
    # Indicator carries the ellipsis glyph and the agent name; karaoke
    # header (post-clear) carries the opening italic-quote — distinct.
    indicator_line = next((s for s in pre_speak if "…" in s), None)
    assert indicator_line is not None, (
        f"expected indicator with ellipsis pre-speak; got {pre_speak!r}"
    )
    assert "Kallos" in indicator_line


@pytest.mark.asyncio
async def test_synthesis_indicator_cleared_when_audio_starts(_captured):
    """When `on_audio_start` fires, the indicator must be wiped (CR +
    erase-line) before the karaoke header opens — otherwise the player
    sees the ellipsis line stuck above the karaoke quote."""

    async def _karaoke_speak(*args, on_audio_start=None, on_word=None, **kwargs):
        if on_audio_start is not None:
            on_audio_start()
        if on_word is not None:
            on_word(MagicMock(word="hi"))

    tts = MagicMock()
    tts.speak = AsyncMock(side_effect=_karaoke_speak)
    dialogue = _status_event('"Hi."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    visual = "".join(_captured)
    # Erase-line ANSI present somewhere in the output.
    assert "\033[2K" in visual or "\x1b[2K" in visual, (
        f"expected indicator-clear ANSI in stream; got {visual!r}"
    )


@pytest.mark.asyncio
async def test_synthesis_indicator_cleared_when_tier2_fallback(_captured):
    """When neither `on_audio_start` nor `on_word` fires (auto-mute,
    engine init failure), the indicator still gets wiped before the
    Tier 2 box echoes — otherwise the box renders below a stuck
    ellipsis line.
    """
    tts = MagicMock()
    tts.speak = AsyncMock()  # silent: no callbacks fire
    dialogue = _status_event('"Hi."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    visual = "".join(_captured)
    # Indicator-clear must precede the [FORMATTED] box in the stream.
    clear_pos = visual.find("\033[2K")
    box_pos = visual.find("[FORMATTED]")
    assert clear_pos != -1, "indicator-clear ANSI missing in fallback path"
    assert box_pos != -1, "Tier 2 box missing in fallback path"
    assert clear_pos < box_pos, "indicator must be cleared before box renders"


@pytest.mark.asyncio
async def test_synthesis_indicator_skipped_when_captions_off_audio_only(_captured):
    """Audio-only mode (captions off + TTS on): no visual at all, so
    the indicator must NOT render either — no flash of "Kallos …" before
    silent audio playback.
    """
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Hi."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=False)

    visual = "".join(_captured)
    # Audio-only path: no [FORMATTED] box AND no indicator ellipsis.
    assert "[FORMATTED]" not in visual
    assert "…" not in visual, f"indicator leaked in audio-only mode: {visual!r}"
    tts.speak.assert_awaited()


@pytest.mark.asyncio
async def test_synthesis_indicator_skipped_in_instant_mode(_captured):
    """`dialogue_sync_mode='instant'` skips the audio-led path entirely;
    the indicator belongs to that path so it must NOT render — instant
    mode renders the box immediately with no synthesis-wait gap to fill.
    """
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Hi."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(
        client,
        "prompt",
        "ctx-1",
        tts=tts,
        captions_enabled=True,
        dialogue_sync_mode="instant",
    )

    visual = "".join(_captured)
    assert "…" not in visual, f"indicator leaked in instant mode: {visual!r}"
