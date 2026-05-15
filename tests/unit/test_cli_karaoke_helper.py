"""Focused tests for `speak_with_karaoke` — the three-outcome state machine
that wraps `tts.speak(...)` with karaoke shell + fallback hooks.

The wider captions tests in `test_cli_streaming_captions.py` exercise the
helper through `send_and_stream`; these tests pin its contract directly so
future call sites can rely on the same three branches.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hosts.cli.rendering import speak_with_karaoke


@pytest.fixture
def _captured(monkeypatch):
    captured: list[str] = []

    def _capture(text: str = "", nl: bool = True) -> None:
        del nl
        captured.append(text)

    monkeypatch.setattr("hosts.cli.rendering._echo", _capture)
    return captured


def _make_tts(speak_side_effect):
    tts = MagicMock()
    tts.speak = AsyncMock(side_effect=speak_side_effect)
    return tts


@pytest.mark.asyncio
async def test_happy_path_opens_reveals_closes(_captured):
    """audio_start + on_word both fire — helper handles the full shell."""

    async def _speak(text, agent, *, on_audio_start, on_word):
        on_audio_start()
        on_word(MagicMock(word="hello"))
        on_word(MagicMock(word="world"))

    no_words = MagicMock()
    no_audio = MagicMock()

    await speak_with_karaoke(
        _make_tts(_speak),
        "hello world",
        "kallos",
        "(◕ᴗ◕✿)",
        on_no_words=no_words,
        on_no_audio=no_audio,
    )

    visual = "".join(_captured)
    assert "Kallos" in visual
    assert "hello" in visual and "world" in visual
    # Open quote + close quote both landed (close echoes `"\x1b[0m\n`).
    assert visual.count('"') >= 2
    no_words.assert_not_called()
    no_audio.assert_not_called()


@pytest.mark.asyncio
async def test_no_words_branch_invokes_on_no_words(_captured):
    """audio_start fires but on_word never does — caller's no-words hook runs."""

    async def _speak(text, agent, *, on_audio_start, on_word):
        on_audio_start()
        # No on_word call.

    no_words = MagicMock()
    no_audio = MagicMock()

    await speak_with_karaoke(
        _make_tts(_speak),
        "hello world",
        "kallos",
        "(◕ᴗ◕✿)",
        on_no_words=no_words,
        on_no_audio=no_audio,
    )

    visual = "".join(_captured)
    # Karaoke shell was opened (header + open quote landed).
    assert "Kallos" in visual
    no_words.assert_called_once()
    no_audio.assert_not_called()


@pytest.mark.asyncio
async def test_no_audio_branch_invokes_on_no_audio(_captured):
    """Neither callback fires — caller's no-audio hook runs, no karaoke shell."""

    async def _speak(text, agent, *, on_audio_start, on_word):
        # Silent: neither callback fires.
        return

    no_words = MagicMock()
    no_audio = MagicMock()

    await speak_with_karaoke(
        _make_tts(_speak),
        "hello world",
        "kallos",
        "(◕ᴗ◕✿)",
        on_no_words=no_words,
        on_no_audio=no_audio,
    )

    visual = "".join(_captured)
    # No karaoke open echoed.
    assert "Kallos" not in visual
    no_words.assert_not_called()
    no_audio.assert_called_once()


@pytest.mark.asyncio
async def test_before_open_fires_before_karaoke_shell(_captured):
    """before_open runs once, right before the karaoke shell echoes."""

    async def _speak(text, agent, *, on_audio_start, on_word):
        on_audio_start()
        on_word(MagicMock(word="hi"))

    order: list[str] = []

    def _before_open():
        order.append("before")

    def _on_no_words():
        order.append("no_words")  # should not be called on happy path

    def _on_no_audio():
        order.append("no_audio")  # should not be called on happy path

    await speak_with_karaoke(
        _make_tts(_speak),
        "hi",
        "kallos",
        "(◕ᴗ◕✿)",
        on_no_words=_on_no_words,
        on_no_audio=_on_no_audio,
        before_open=_before_open,
    )

    assert order == ["before"]
    # First capture is the before_open's side-effect-free no-op; the
    # karaoke open landed in _captured AFTER before_open ran.
    visual = "".join(_captured)
    assert "Kallos" in visual


@pytest.mark.asyncio
async def test_before_open_not_called_when_audio_never_starts(_captured):
    """before_open is tied to the karaoke shell opening; if audio_start
    never fires, the hook must not fire either."""

    async def _speak(text, agent, *, on_audio_start, on_word):
        return

    before = MagicMock()
    no_audio = MagicMock()

    await speak_with_karaoke(
        _make_tts(_speak),
        "hi",
        "kallos",
        "(◕ᴗ◕✿)",
        on_no_words=MagicMock(),
        on_no_audio=no_audio,
        before_open=before,
    )

    before.assert_not_called()
    no_audio.assert_called_once()


@pytest.mark.asyncio
async def test_empty_word_callback_is_ignored(_captured):
    """on_word with empty `.word` attribute is a no-op (RealtimeTTS sometimes
    fires sentinel events) — should not flip words_revealed."""

    async def _speak(text, agent, *, on_audio_start, on_word):
        on_audio_start()
        on_word(MagicMock(word=""))  # sentinel
        on_word(MagicMock(word=""))  # another sentinel
        # No real word.

    no_words = MagicMock()

    await speak_with_karaoke(
        _make_tts(_speak),
        "hello",
        "kallos",
        "(◕ᴗ◕✿)",
        on_no_words=no_words,
        on_no_audio=MagicMock(),
    )

    # Empty words shouldn't count, so no-words branch should still fire.
    no_words.assert_called_once()
