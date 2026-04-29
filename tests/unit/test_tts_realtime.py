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
