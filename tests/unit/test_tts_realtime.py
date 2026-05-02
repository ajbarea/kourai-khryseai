"""Unit tests for kourai_common.tts_realtime.RealtimeTTSEngine.

The engine wraps RealtimeTTS's KokoroEngine + TextToAudioStream. Tests
monkeypatch both at the module level so PyAudio is never initialized
under pytest. ABI parity with the legacy hosts.gui.tts_engine.TTSEngine
is the explicit contract being enforced here — every public method the
CLI calls must keep the same shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("RealtimeTTS")


@pytest.fixture
def mock_realtimetts(monkeypatch):
    """Replace KokoroEngine + TextToAudioStream so PyAudio stays untouched."""
    mock_kokoro = MagicMock(name="KokoroEngineInstance")
    mock_kokoro_cls = MagicMock(name="KokoroEngineClass", return_value=mock_kokoro)

    mock_stream = MagicMock(name="TextToAudioStreamInstance")
    mock_stream_cls = MagicMock(name="TextToAudioStreamClass", return_value=mock_stream)

    monkeypatch.setattr("kourai_common.tts_realtime._KokoroEngine", mock_kokoro_cls)
    monkeypatch.setattr("kourai_common.tts_realtime._TextToAudioStream", mock_stream_cls)

    return mock_kokoro_cls, mock_kokoro, mock_stream_cls, mock_stream


# ===================================================================
# Init + ABI surface
# ===================================================================


class TestRealtimeTTSEngineInit:
    def test_init_default(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        assert engine.master_volume == 0.8
        assert engine.enable_effects is True
        assert engine.is_playing is False

    def test_init_custom_volume(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine(master_volume=0.5, enable_effects=False)
        assert engine.master_volume == 0.5
        assert engine.enable_effects is False

    def test_init_clamps_volume(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        assert RealtimeTTSEngine(master_volume=1.5).master_volume == 1.0
        assert RealtimeTTSEngine(master_volume=-0.5).master_volume == 0.0

    def test_init_constructs_kokoro_and_stream(self, mock_realtimetts):
        mock_kokoro_cls, _, mock_stream_cls, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()
        mock_kokoro_cls.assert_called_once()
        mock_stream_cls.assert_called_once()

    def test_init_passes_on_word_to_stream(self, mock_realtimetts):
        _, _, mock_stream_cls, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        cb = MagicMock()
        RealtimeTTSEngine(on_word=cb)
        kwargs = mock_stream_cls.call_args.kwargs
        assert kwargs.get("on_word") is cb

    def test_init_seeds_stream_volume(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine(master_volume=0.6, enable_effects=True)
        # Effects scale: 0.6 * 0.85 = 0.51
        mock_stream.set_volume.assert_called_with(pytest.approx(0.51))

    def test_init_seeds_stream_volume_no_effects(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine(master_volume=0.6, enable_effects=False)
        mock_stream.set_volume.assert_called_with(0.6)


# ===================================================================
# Volume + lifecycle hooks
# ===================================================================


class TestRealtimeTTSEngineVolume:
    def test_set_master_volume_updates_attr_and_stream(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        mock_stream.set_volume.reset_mock()
        engine.set_master_volume(0.6)
        assert engine.master_volume == 0.6
        mock_stream.set_volume.assert_called_once_with(pytest.approx(0.51))

    def test_set_master_volume_clamps(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine.set_master_volume(2.0)
        assert engine.master_volume == 1.0
        engine.set_master_volume(-1.0)
        assert engine.master_volume == 0.0

    def test_set_on_complete(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        cb = MagicMock()
        engine.set_on_complete(cb)
        assert engine._on_complete is cb


# ===================================================================
# speak() — the core dispatch
# ===================================================================


class TestRealtimeTTSEngineSpeak:
    @pytest.mark.asyncio
    async def test_speak_empty_text_skips(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak("")
        await engine.speak("   ")
        mock_stream.feed.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_resolves_agent_voice(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak("hello", agent_name="metis")
        # Metis voice config: af_sarah, speed=0.90
        mock_kokoro.set_voice.assert_called_with("af_sarah")
        mock_kokoro.set_speed.assert_called_with(0.90)
        mock_stream.feed.assert_called_once_with("hello")
        mock_stream.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_unknown_agent_uses_default(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak("hi", agent_name="not_a_real_agent")
        mock_kokoro.set_voice.assert_called_with("af_heart")

    @pytest.mark.asyncio
    async def test_speak_voice_key_overrides_agent(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak("hi", agent_name="metis", voice_key="af_bella")
        mock_kokoro.set_voice.assert_called_with("af_bella")

    @pytest.mark.asyncio
    async def test_speak_speed_override_wins(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak("hi", agent_name="metis", speed=1.5)
        mock_kokoro.set_speed.assert_called_with(1.5)

    @pytest.mark.asyncio
    async def test_speak_clears_is_playing_after_completion(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak("hello", agent_name="metis")
        assert engine.is_playing is False

    @pytest.mark.asyncio
    async def test_speak_handles_exception(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        mock_stream.feed.side_effect = RuntimeError("synthesis failed")
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        cb = MagicMock()
        engine.set_on_complete(cb)
        await engine.speak("hello")  # must not raise
        assert engine.is_playing is False
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_fires_on_complete_on_success(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        cb = MagicMock()
        engine.set_on_complete(cb)
        await engine.speak("hello", agent_name="metis")
        cb.assert_called_once()

    def test_speak_sync_runs_in_new_loop(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        with pytest.MonkeyPatch.context() as mp:
            mock_speak = AsyncMock()
            mp.setattr(engine, "speak", mock_speak)
            engine.speak_sync("hi", agent_name="hephaestus")
            mock_speak.assert_awaited_once()


# ===================================================================
# Stop + cleanup
# ===================================================================


class TestRealtimeTTSEngineStop:
    def test_stop_calls_stream_stop(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine.is_playing = True
        engine.stop()
        mock_stream.stop.assert_called_once()
        assert engine.is_playing is False

    def test_stop_swallows_stream_exception(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        mock_stream.stop.side_effect = RuntimeError("player gone")
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine.stop()  # must not raise
        assert engine.is_playing is False


class TestRealtimeTTSEngineCleanup:
    def test_cleanup_stops_and_shuts_down(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine.cleanup()
        mock_stream.stop.assert_called()
        mock_kokoro.shutdown.assert_called_once()

    def test_cleanup_swallows_shutdown_exception(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        mock_kokoro.shutdown.side_effect = RuntimeError("already gone")
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine.cleanup()  # must not raise


# ===================================================================
# Re-exports for parity with hosts.gui.tts_engine
# ===================================================================


class TestModuleReExports:
    def test_voice_roster_populated(self):
        from kourai_common.tts_realtime import VOICE_ROSTER

        assert "af_sarah" in VOICE_ROSTER
        assert "am_michael" in VOICE_ROSTER

    def test_agent_voices_populated(self):
        from kourai_common.tts_realtime import AGENT_VOICES

        assert AGENT_VOICES["metis"] == "af_sarah"
        assert AGENT_VOICES["hephaestus"] == "am_michael"

    def test_voice_config_alias(self):
        from kourai_common.tts_backend import TTSVoiceConfig
        from kourai_common.tts_realtime import VoiceConfig

        assert VoiceConfig is TTSVoiceConfig


# ===================================================================
# phonemizer 'words count mismatch' filter (#22)
# ===================================================================


class TestPhonemizerWordCountFilter:
    """Engine init must silence phonemizer's per-call words-count-mismatch spam."""

    @staticmethod
    def _our_filters() -> list:
        import logging

        from kourai_common.tts_realtime import _DropPhonemizerWordsCountMismatch

        return [
            f
            for f in logging.getLogger("phonemizer").filters
            if isinstance(f, _DropPhonemizerWordsCountMismatch)
        ]

    def test_engine_init_installs_filter(self, mock_realtimetts):
        import logging

        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()

        spam = logging.LogRecord(
            name="phonemizer",
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg="words count mismatch on 100.0%% of the lines (1/1)",
            args=(),
            exc_info=None,
        )
        installed = self._our_filters()
        assert installed, "RealtimeTTSEngine() must install the filter"
        assert all(f.filter(spam) is False for f in installed)

    def test_filter_preserves_other_phonemizer_warnings(self, mock_realtimetts):
        import logging

        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()

        unrelated = logging.LogRecord(
            name="phonemizer",
            level=logging.WARNING,
            pathname=__file__,
            lineno=0,
            msg="some other phonemizer message",
            args=(),
            exc_info=None,
        )
        installed = self._our_filters()
        assert installed
        assert all(f.filter(unrelated) is True for f in installed)

    def test_filter_install_is_idempotent(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()
        RealtimeTTSEngine()
        RealtimeTTSEngine()

        assert len(self._our_filters()) == 1


# ===================================================================
# Per-language Kokoro pre-warm (#23)
# ===================================================================


class TestKokoroLanguagePreWarm:
    """Engine init must call _get_pipeline once per unique agent lang_code.

    KokoroEngine ships with ``"a"`` (American English) cached for the
    default voice. Languages used by other agents (notably ``"b"`` for
    Techne's ``bf_emma``) lazily build on first ``set_voice`` call —
    a noticeable pause on first speech. Pre-warming pays that cost upfront.
    """

    def test_prewarms_unique_lang_codes_from_agent_voice_map(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        from kourai_common.tts_backend import AGENT_VOICE_MAP
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()

        called_lang_codes = {call.args[0] for call in mock_kokoro._get_pipeline.call_args_list}
        expected_lang_codes = {cfg.lang_code for cfg in AGENT_VOICE_MAP.values()}
        assert called_lang_codes == expected_lang_codes

    def test_prewarms_only_once_per_lang_code(self, mock_realtimetts):
        """Language pre-warm dedupes; voice pre-warm fans out per agent.

        ``_prewarm_agent_languages`` calls ``_get_pipeline`` once per
        unique lang_code (dedup against many ``"a"`` entries in
        AGENT_VOICE_MAP). The follow-up ``_prewarm_agent_voices`` then
        calls ``_get_pipeline(cfg.lang_code)`` once per agent voice,
        relying on KokoroEngine's idempotent cache to skip rebuilds.
        Net call count = unique lang_codes + len(AGENT_VOICE_MAP).
        """
        _, mock_kokoro, _, _ = mock_realtimetts
        from kourai_common.tts_backend import AGENT_VOICE_MAP
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()

        unique_langs = {cfg.lang_code for cfg in AGENT_VOICE_MAP.values()}
        expected_calls = len(unique_langs) + len(AGENT_VOICE_MAP)
        assert mock_kokoro._get_pipeline.call_count == expected_calls

    def test_prewarm_failure_does_not_raise(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        mock_kokoro._get_pipeline.side_effect = RuntimeError("model download failed")

        from kourai_common.tts_realtime import RealtimeTTSEngine

        # Init must succeed even when pre-warm raises — TTS warmup is
        # best-effort; the lazy path still works downstream.
        engine = RealtimeTTSEngine()
        assert engine is not None


# ===================================================================
# Per-agent Kokoro voice tensor pre-warm (M20 sub-task 1)
# ===================================================================


class TestKokoroVoicePreWarm:
    """Engine init must materialize each agent's voice tensor.

    KPipeline.load_single_voice downloads + parses a ~5-10MB .pt file
    on first call per voice, then caches the tensor. Pre-loading at
    init pays that cost once instead of stacking per-voice lag onto
    the first per-agent utterance.
    """

    def test_prewarms_every_agent_voice(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        from kourai_common.tts_backend import AGENT_VOICE_MAP
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()

        pipeline_mock = mock_kokoro._get_pipeline.return_value
        called_voice_ids = {call.args[0] for call in pipeline_mock.load_single_voice.call_args_list}
        expected_voice_ids = {cfg.voice_id for cfg in AGENT_VOICE_MAP.values()}
        assert called_voice_ids == expected_voice_ids

    def test_voice_prewarm_failure_does_not_raise(self, mock_realtimetts):
        _, mock_kokoro, _, _ = mock_realtimetts
        mock_kokoro._get_pipeline.return_value.load_single_voice.side_effect = RuntimeError(
            "voice download failed"
        )

        from kourai_common.tts_realtime import RealtimeTTSEngine

        # Init must succeed even when a single voice fails to materialize —
        # the lazy path inside synthesize() still works for that voice.
        engine = RealtimeTTSEngine()
        assert engine is not None


# ===================================================================
# synthesize_to_wav() — bytes-only path for vn_bridge
# ===================================================================


def _wire_chunked_play(mock_stream, chunks: list[bytes]) -> None:
    """Have ``mock_stream.play()`` invoke its ``on_audio_chunk`` callback
    with the supplied chunks, mirroring how RealtimeTTS feeds raw PCM
    out of KokoroEngine when ``muted=True``.
    """

    def _fake_play(*_args, **kwargs):
        cb = kwargs.get("on_audio_chunk")
        if cb is not None:
            for chunk in chunks:
                cb(chunk)

    mock_stream.play.side_effect = _fake_play


class TestRealtimeTTSEngineSynthesizeToWav:
    @pytest.mark.asyncio
    async def test_empty_text_returns_empty_bytes(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        assert await engine.synthesize_to_wav("") == b""
        assert await engine.synthesize_to_wav("   ") == b""

    @pytest.mark.asyncio
    async def test_resolves_agent_voice(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)  # paInt16
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.synthesize_to_wav("hello", agent_name="metis")
        mock_kokoro.set_voice.assert_called_with("af_sarah")
        mock_kokoro.set_speed.assert_called_with(0.90)
        mock_stream.feed.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_voice_key_overrides_agent(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00" * 8])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.synthesize_to_wav("hi", agent_name="metis", voice_key="af_bella")
        mock_kokoro.set_voice.assert_called_with("af_bella")

    @pytest.mark.asyncio
    async def test_speed_override_wins(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00" * 8])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.synthesize_to_wav("hi", agent_name="metis", speed=1.4)
        mock_kokoro.set_speed.assert_called_with(1.4)

    @pytest.mark.asyncio
    async def test_unknown_agent_uses_default(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00" * 8])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.synthesize_to_wav("hi", agent_name="not_a_real_agent")
        mock_kokoro.set_voice.assert_called_with("af_heart")

    @pytest.mark.asyncio
    async def test_play_invoked_with_muted_and_callback(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00" * 8])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.synthesize_to_wav("hello", agent_name="hephaestus")
        kwargs = mock_stream.play.call_args.kwargs
        assert kwargs.get("muted") is True
        assert callable(kwargs.get("on_audio_chunk"))

    @pytest.mark.asyncio
    async def test_returns_valid_wav_with_riff_and_wave_markers(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x01\x02" * 100, b"\x03\x04" * 100])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        wav = await engine.synthesize_to_wav("hi", agent_name="hephaestus")
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        # 44-byte canonical PCM header + 400 bytes payload
        assert len(wav) > 44

    @pytest.mark.asyncio
    async def test_wav_header_uses_engine_stream_info(self, mock_realtimetts):
        import io
        import wave

        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)  # paInt16
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 100])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        wav = await engine.synthesize_to_wav("hi", agent_name="hephaestus")
        with wave.open(io.BytesIO(wav), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getframerate() == 24000
            assert w.getsampwidth() == 2

    @pytest.mark.asyncio
    async def test_no_chunks_returns_empty(self, mock_realtimetts):
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        # play() returns without invoking on_audio_chunk
        mock_stream.play.side_effect = lambda *_a, **_k: None
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        assert await engine.synthesize_to_wav("hi", agent_name="hephaestus") == b""
