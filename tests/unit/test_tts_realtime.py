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

    def test_init_stores_static_on_word_under_trampoline(self, mock_realtimetts):
        """Constructor-time on_word now layers under the per-call trampoline
        (M20 sub-task 2 Tier 1) — TextToAudioStream gets the trampoline,
        the static handler is preserved on the engine for the dispatcher
        to invoke alongside any per-call handler.
        """
        from kourai_common.tts_realtime import RealtimeTTSEngine

        cb = MagicMock()
        engine = RealtimeTTSEngine(on_word=cb)
        assert engine._on_word_static is cb

    def test_init_wires_audio_start_trampoline(self, mock_realtimetts):
        """M20 sub-task 2 Tier 2: TextToAudioStream must receive the engine's
        stable trampoline at construction so per-call handlers attached via
        speak()'s on_audio_start can dispatch through it.
        """
        _, _, mock_stream_cls, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        kwargs = mock_stream_cls.call_args.kwargs
        wired = kwargs.get("on_audio_stream_start")
        assert wired is not None, "on_audio_stream_start must be wired at construction"
        # Bound methods compare equal when bound to same instance + function.
        assert wired == engine._dispatch_audio_start

    def test_init_wires_on_word_trampoline(self, mock_realtimetts):
        """M20 sub-task 2 Tier 1: on_word trampoline at construction so
        per-call handlers attached via speak()'s on_word can dispatch.
        """
        _, _, mock_stream_cls, _ = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        kwargs = mock_stream_cls.call_args.kwargs
        wired = kwargs.get("on_word")
        assert wired is not None, "on_word must be wired at construction"
        assert wired == engine._dispatch_on_word

    def test_init_static_on_word_layered_under_per_call(self, mock_realtimetts):
        """Constructor-time on_word stays installed; the trampoline fires
        BOTH the static handler and any per-call handler set by speak().
        """
        from kourai_common.tts_realtime import RealtimeTTSEngine

        static_cb = MagicMock(name="static")
        engine = RealtimeTTSEngine(on_word=static_cb)
        per_call_cb = MagicMock(name="per_call")
        engine._on_word_current = per_call_cb

        word = MagicMock(word="hello")
        engine._dispatch_on_word(word)

        static_cb.assert_called_once_with(word)
        per_call_cb.assert_called_once_with(word)

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


class TestRealtimeTTSEngineMutedAutoDetect:
    """muted=None auto-detects via is_audio_output_available; explicit
    True/False overrides bypass detection. Defends the cross-platform
    fallback path AJ ships in 2026-05.
    """

    def test_muted_none_auto_mutes_when_no_audio(self, mock_realtimetts, monkeypatch, caplog):
        _, _, mock_stream_cls, _ = mock_realtimetts
        monkeypatch.setattr(
            "kourai_common.tts_realtime.is_audio_output_available",
            lambda: False,
        )
        from kourai_common.tts_realtime import RealtimeTTSEngine

        with caplog.at_level("WARNING"):
            RealtimeTTSEngine()  # muted defaults to None

        assert mock_stream_cls.call_args.kwargs["muted"] is True
        assert "auto-muted" in caplog.text.lower()

    def test_muted_none_unmutes_when_audio_available(self, mock_realtimetts, monkeypatch):
        _, _, mock_stream_cls, _ = mock_realtimetts
        monkeypatch.setattr(
            "kourai_common.tts_realtime.is_audio_output_available",
            lambda: True,
        )
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine()
        assert mock_stream_cls.call_args.kwargs["muted"] is False

    def test_explicit_muted_true_skips_detect(self, mock_realtimetts, monkeypatch):
        _, _, mock_stream_cls, _ = mock_realtimetts
        probe = MagicMock(name="is_audio_output_available")
        monkeypatch.setattr("kourai_common.tts_realtime.is_audio_output_available", probe)
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine(muted=True)
        assert mock_stream_cls.call_args.kwargs["muted"] is True
        probe.assert_not_called()

    def test_explicit_muted_false_skips_detect(self, mock_realtimetts, monkeypatch):
        _, _, mock_stream_cls, _ = mock_realtimetts
        probe = MagicMock(name="is_audio_output_available")
        monkeypatch.setattr("kourai_common.tts_realtime.is_audio_output_available", probe)
        from kourai_common.tts_realtime import RealtimeTTSEngine

        RealtimeTTSEngine(muted=False)
        assert mock_stream_cls.call_args.kwargs["muted"] is False
        probe.assert_not_called()


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
    async def test_speak_strips_ssml_before_feeding(self, mock_realtimetts):
        """M18 Phase 2: producers emit SSML, engine strips for Kokoro."""
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak('<speak>hello <break time="200ms"/>world</speak>')
        mock_stream.feed.assert_called_once_with("hello world")

    @pytest.mark.asyncio
    async def test_speak_skips_when_ssml_strips_to_empty(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.speak('<speak><break time="200ms"/></speak>')
        mock_stream.feed.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_fires_on_audio_start_via_trampoline(self, mock_realtimetts):
        """M20 sub-task 2 Tier 2: per-call on_audio_start callback dispatches
        through the engine's stable trampoline. The trampoline is wired into
        TextToAudioStream at construction; speak() sets the per-call handler
        and the dispatcher invokes it when RealtimeTTS reports audio start.
        """
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        callback = MagicMock()
        # Simulate RealtimeTTS firing on_audio_stream_start during play() —
        # use feed.side_effect (called inside speak) to invoke the trampoline.
        mock_stream.feed.side_effect = lambda _text: engine._dispatch_audio_start()

        await engine.speak("hello", agent_name="hephaestus", on_audio_start=callback)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_restores_prior_on_audio_start_after_call(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        cb1 = MagicMock(name="outer")
        cb2 = MagicMock(name="inner")
        engine._on_audio_start_current = cb1

        await engine.speak("hi", agent_name="hephaestus", on_audio_start=cb2)
        # After speak() returns, prior callback restored.
        assert engine._on_audio_start_current is cb1

    @pytest.mark.asyncio
    async def test_speak_without_on_audio_start_leaves_trampoline_idle(self, mock_realtimetts):
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        # Force dispatch — should be a noop because no per-call handler set.
        await engine.speak("hi", agent_name="hephaestus")
        # No exception raised by trampoline on missing handler.
        engine._dispatch_audio_start()  # should not raise

    @pytest.mark.asyncio
    async def test_dispatch_audio_start_swallows_callback_exceptions(self, mock_realtimetts):
        """A buggy display-flush callback must not break TTS playback."""
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine._on_audio_start_current = MagicMock(side_effect=RuntimeError("boom"))
        engine._dispatch_audio_start()  # should not raise

    @pytest.mark.asyncio
    async def test_speak_fires_on_word_via_trampoline(self, mock_realtimetts):
        """M20 sub-task 2 Tier 1: per-call on_word callback dispatches
        through the engine's stable trampoline. The trampoline wires
        TextToAudioStream's on_word at construction; speak() sets the
        per-call handler and the dispatcher invokes it for each TimingInfo
        RealtimeTTS emits while playing.
        """
        _, _, _, mock_stream = mock_realtimetts
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        callback = MagicMock(name="word_cb")
        word_a = MagicMock(word="hello")
        word_b = MagicMock(word="world")

        # Simulate RealtimeTTS firing on_word twice during play().
        def _simulate_play(_text: str) -> None:
            engine._dispatch_on_word(word_a)
            engine._dispatch_on_word(word_b)

        mock_stream.feed.side_effect = _simulate_play

        await engine.speak("hello world", agent_name="hephaestus", on_word=callback)

        assert callback.call_args_list == [
            ((word_a,),),
            ((word_b,),),
        ]

    @pytest.mark.asyncio
    async def test_speak_restores_prior_on_word_after_call(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        outer = MagicMock(name="outer")
        inner = MagicMock(name="inner")
        engine._on_word_current = outer

        await engine.speak("hi", agent_name="hephaestus", on_word=inner)
        assert engine._on_word_current is outer

    @pytest.mark.asyncio
    async def test_dispatch_on_word_swallows_callback_exceptions(self, mock_realtimetts):
        """A buggy karaoke-reveal callback must not break TTS playback."""
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        engine._on_word_current = MagicMock(side_effect=RuntimeError("boom"))
        word = MagicMock(word="hi")
        engine._dispatch_on_word(word)  # should not raise

    @pytest.mark.asyncio
    async def test_speak_handles_systemexit_from_realtimetts(self, mock_realtimetts):
        """RealtimeTTS calls exit(0) deep in stream_player.open_stream when
        no audio device. SystemExit isn't an Exception, so without the
        widened catch the asyncio loop dies and the CLI exits.
        """
        _, _, _, mock_stream = mock_realtimetts
        mock_stream.feed.side_effect = SystemExit(0)
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        cb = MagicMock()
        engine.set_on_complete(cb)
        await engine.speak("hello")  # must not bubble SystemExit
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
        """Language phase dedupes; voice phase calls _get_pipeline per agent (idempotent)."""
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
    """Engine init must call load_single_voice for every agent voice."""

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
    async def test_strips_ssml_before_feeding(self, mock_realtimetts):
        """M18 Phase 2: vn_bridge inherits the same SSML contract as CLI/GUI."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        await engine.synthesize_to_wav('<speak>hello <break time="200ms"/>world</speak>')
        mock_stream.feed.assert_called_once_with("hello world")

    @pytest.mark.asyncio
    async def test_returns_empty_when_ssml_strips_to_empty(self, mock_realtimetts):
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()
        result = await engine.synthesize_to_wav('<speak><break time="200ms"/></speak>')
        assert result == b""

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


# ===================================================================
# synthesize_to_wav() — TTS audio cache wiring (M6 sub-task 2)
# ===================================================================


class TestRealtimeTTSEngineCacheWiring:
    @pytest.mark.asyncio
    async def test_default_construction_does_not_cache(self, mock_realtimetts, tmp_path):
        """Without cache_dir, behavior is identical to pre-cache: every
        call hits Kokoro. Default keeps existing tests / production paths
        unchanged."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine()  # cache_dir defaults to None
        await engine.synthesize_to_wav("hi", agent_name="metis")
        await engine.synthesize_to_wav("hi", agent_name="metis")
        # Both calls drove Kokoro through play() — no cache short-circuit.
        assert mock_stream.play.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_dir_routes_second_call_through_cache(self, mock_realtimetts, tmp_path):
        """With cache_dir set, the second identical call returns cached
        bytes without re-driving Kokoro."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine(cache_dir=tmp_path)
        first = await engine.synthesize_to_wav("hi", agent_name="metis")
        second = await engine.synthesize_to_wav("hi", agent_name="metis")
        assert first == second
        # Only one synth invocation; the second call hit the cache.
        assert mock_stream.play.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_keys_include_speed_override(self, mock_realtimetts, tmp_path):
        """speed=1.0 vs speed=1.5 must produce distinct cache entries —
        otherwise a player toggle would silently re-use the wrong audio."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine(cache_dir=tmp_path)
        await engine.synthesize_to_wav("hi", agent_name="metis", speed=1.0)
        await engine.synthesize_to_wav("hi", agent_name="metis", speed=1.5)
        # Each speed got its own miss-fetch; both drove Kokoro.
        assert mock_stream.play.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_keys_include_voice_override(self, mock_realtimetts, tmp_path):
        """Different voice_key → different cache entry."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine(cache_dir=tmp_path)
        await engine.synthesize_to_wav("hi", agent_name="metis", voice_key="af_bella")
        await engine.synthesize_to_wav("hi", agent_name="metis", voice_key="af_sarah")
        assert mock_stream.play.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_synth_result_not_cached(self, mock_realtimetts, tmp_path):
        """If Kokoro returns no chunks (e.g., cold-start glitch), don't
        litter the cache with an empty WAV that would block real synth
        on the next call."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        # play() returns nothing — synthesize_to_wav returns b""
        mock_stream.play.side_effect = lambda *_a, **_k: None
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine(cache_dir=tmp_path)
        first = await engine.synthesize_to_wav("hi", agent_name="metis")
        assert first == b""
        # Cache dir should not have leaked an empty entry.
        wav_files = list(tmp_path.rglob("*.wav"))
        assert wav_files == []

    @pytest.mark.asyncio
    async def test_cache_writes_under_sharded_layout(self, mock_realtimetts, tmp_path):
        """The cache must use the spec'd `{key[:2]}/{key}.wav` layout so
        large caches don't blow up a single inode."""
        _, mock_kokoro, _, mock_stream = mock_realtimetts
        mock_kokoro.get_stream_info.return_value = (8, 1, 24000)
        _wire_chunked_play(mock_stream, [b"\x00\x01" * 12])
        from kourai_common.tts_realtime import RealtimeTTSEngine

        engine = RealtimeTTSEngine(cache_dir=tmp_path)
        await engine.synthesize_to_wav("hi", agent_name="metis")
        # Exactly one file, two-char shard prefix dir.
        wav_files = list(tmp_path.rglob("*.wav"))
        assert len(wav_files) == 1
        assert wav_files[0].parent.name == wav_files[0].stem[:2]
