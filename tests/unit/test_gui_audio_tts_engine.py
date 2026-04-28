"""Tests for TTSEngine, AudioManager, and remaining coverage gaps.

Covers:
- hosts/gui/tts_engine.py (TTSEngine init, volume, stop, cleanup, _get_converter, speak)
- shared/src/kourai_common/audio.py (AudioManager init, volume controls, music, ambient, sfx, cleanup)
- hosts/gui/loading_screen.py (run_loading_screen phases)
- hosts/gui/profile_select.py (run_profile_select)
- hosts/gui/connection_gui_integration.py
- hosts/gui/agent_handoff_personality_integration.py

"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Imported as a module reference so we always resolve ``AudioManager``
# against the live ``kourai_common.audio`` — ``test_audio_env.py``'s
# ``importlib.reload(audio)`` swaps in a fresh class object, and a
# top-level ``from kourai_common.audio import AudioManager`` would
# pin the stale class for the rest of this file's run, leaving the
# fixture resetting one class while the tests instantiated another.
# The fixture resolves ``audio.AudioManager`` at fixture time so it
# always sees whatever's current in the module.
from kourai_common import audio

pytest.importorskip("pygame")


# ===================================================================
# 1. TTSEngine — mock pygame.mixer to avoid hardware dependency
# ===================================================================


@pytest.fixture
def mock_mixer():
    """Patch pygame.mixer so TTSEngine can init without audio hardware."""
    mock_channel = MagicMock()
    mock_channel.get_busy.return_value = False

    with (
        patch("pygame.mixer.init"),
        patch("pygame.mixer.set_num_channels"),
        patch("pygame.mixer.Channel", return_value=mock_channel),
        patch("pygame.mixer.quit"),
        patch("pygame.mixer.get_busy", return_value=False),
        patch("pygame.mixer.Sound"),
        patch("pygame.mixer.music"),
        patch("pygame.mixer.find_channel", return_value=mock_channel),
    ):
        yield mock_channel


class TestTTSEngineInit:
    def test_init_default(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        assert engine.master_volume == 0.8
        assert engine.enable_effects is True
        assert engine.is_playing is False
        assert engine._mixer_initialized is True

    def test_init_custom_volume(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine(master_volume=0.5, enable_effects=False)
        assert engine.master_volume == 0.5
        assert engine.enable_effects is False

    def test_init_clamps_volume(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine(master_volume=1.5)
        assert engine.master_volume == 1.0
        engine2 = TTSEngine(master_volume=-0.5)
        assert engine2.master_volume == 0.0

    def test_init_custom_temp_dir(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        with tempfile.TemporaryDirectory() as td:
            engine = TTSEngine(temp_dir=Path(td))
            assert engine.temp_dir == Path(td)

    def test_init_mixer_already_init(self):
        """Test mixer init when it raises RuntimeError (already initialized)."""
        mock_channel = MagicMock()
        mock_channel.get_busy.return_value = False

        with (
            patch("pygame.mixer.init", side_effect=RuntimeError("already init")),
            patch("pygame.mixer.get_init", return_value=MagicMock()),
            patch("pygame.mixer.Channel", return_value=mock_channel),
        ):
            from hosts.gui.tts_engine import TTSEngine

            engine = TTSEngine()
            assert engine._mixer_initialized is True

    def test_init_mixer_channel_fails(self):
        """Test mixer init when Channel() also fails."""
        with (
            patch("pygame.mixer.init", side_effect=RuntimeError("already init")),
            patch("pygame.mixer.Channel", side_effect=Exception("no channels")),
        ):
            from hosts.gui.tts_engine import TTSEngine

            engine = TTSEngine()
            assert engine._tts_channel is None


class TestTTSEngineVolume:
    def test_set_master_volume(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        engine.set_master_volume(0.6)
        assert engine.master_volume == 0.6
        mock_mixer.set_volume.assert_called_with(0.6)

    def test_set_master_volume_clamps(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        engine.set_master_volume(2.0)
        assert engine.master_volume == 1.0
        engine.set_master_volume(-1.0)
        assert engine.master_volume == 0.0

    def test_set_on_complete(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        cb = Mock()
        engine.set_on_complete(cb)
        assert engine._on_complete is cb


class TestTTSEngineStop:
    def test_stop_playing(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        mock_mixer.get_busy.return_value = True
        engine.is_playing = True
        engine.stop()
        mock_mixer.stop.assert_called_once()
        assert engine.is_playing is False

    def test_stop_not_playing(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        mock_mixer.get_busy.return_value = False
        engine.stop()
        assert engine.is_playing is False


class TestTTSEngineCleanup:
    def test_cleanup(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        with tempfile.TemporaryDirectory() as td:
            engine = TTSEngine(temp_dir=Path(td))
            # Create fake temp files
            (Path(td) / "speech_123.mp3").touch()
            (Path(td) / "speech_123.wav").touch()
            engine.cleanup()
            assert not list(Path(td).glob("*.mp3"))
            assert not list(Path(td).glob("*.wav"))


class TestTTSEngineSpeak:
    @pytest.mark.asyncio
    async def test_speak_empty_text(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        await engine.speak("")  # should return early

    @pytest.mark.asyncio
    async def test_speak_generates_audio(self, mock_mixer):
        import io
        import wave

        import numpy as np

        from hosts.gui.tts_engine import TTSEngine
        from kourai_common.tts_backend import TTSBackend, TTSVoiceConfig

        engine = TTSEngine()

        # Mock backend to return valid WAV chunks
        class MockBackend(TTSBackend):
            async def synthesize(self, text: str, voice: TTSVoiceConfig) -> bytes:
                # Return a minimal WAV with ~100ms of silence
                sample_rate = 24000
                duration_ms = 100
                samples = int(sample_rate * duration_ms / 1000)
                silence = np.zeros(samples, dtype=np.int16)
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)
                    wav.writeframes(silence.tobytes())
                return buf.getvalue()

            async def stream_synthesize(self, text: str, voice: TTSVoiceConfig):
                audio = await self.synthesize(text, voice)
                yield audio

            def available_voices(self):
                return [TTSVoiceConfig("Test", "test_voice")]

        engine.backend = MockBackend()
        mock_sound = MagicMock()

        with patch("pygame.mixer.Sound", return_value=mock_sound):
            await engine.speak("Hello world", agent_name="metis")

        assert engine.is_playing is False  # completed

    @pytest.mark.asyncio
    async def test_speak_error_handling(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine
        from kourai_common.tts_backend import TTSBackend, TTSVoiceConfig

        engine = TTSEngine()
        cb = Mock()
        engine.set_on_complete(cb)

        # Mock backend that raises an error
        class FailingBackend(TTSBackend):
            async def synthesize(self, text: str, voice: TTSVoiceConfig) -> bytes:
                raise RuntimeError("network error")

            async def stream_synthesize(self, text: str, voice: TTSVoiceConfig):
                raise RuntimeError("network error")
                yield  # pragma: no cover

            def available_voices(self):
                return []

        engine.backend = FailingBackend()

        await engine.speak("Hello")

        assert engine.is_playing is False
        cb.assert_called_once()

    def test_speak_sync(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        with patch.object(engine, "speak", new_callable=AsyncMock) as mock_speak:
            engine.speak_sync("Hello", agent_name="hephaestus")
            mock_speak.assert_awaited_once()


# ===================================================================
# 2. AudioManager — mock pygame.mixer
# ===================================================================


@pytest.fixture
def mock_audio_mixer():
    """Patch pygame.mixer for AudioManager tests."""
    # Reset singleton
    from kourai_common import audio

    audio.AudioManager._instance = None

    mock_channel = MagicMock()
    mock_channel.get_busy.return_value = False

    with (
        patch("pygame.mixer.pre_init"),
        patch("pygame.mixer.init"),
        patch("pygame.mixer.set_num_channels"),
        patch("pygame.mixer.get_init", return_value=MagicMock()),
        patch("pygame.mixer.Channel", return_value=mock_channel),
        patch("pygame.mixer.quit"),
        patch("pygame.mixer.music") as mock_music,
        patch("pygame.mixer.find_channel", return_value=mock_channel),
        patch("pygame.mixer.Sound") as mock_sound_cls,
    ):
        yield mock_channel, mock_music, mock_sound_cls

    # Reset singleton after test
    audio.AudioManager._instance = None


class TestAudioManagerInit:
    def test_init(self, mock_audio_mixer):
        am = audio.AudioManager()
        assert am._initialized is True
        assert am.music_volume == 0.25
        assert am.ambient_volume == 0.5
        assert am.voice_volume == 1.0
        assert am.sfx_volume == 0.8


class TestAudioManagerVolume:
    def test_set_music_volume(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        mock_music.get_busy.return_value = True
        am.set_music_volume(0.5)
        assert am.music_volume == 0.5
        mock_music.set_volume.assert_called_with(0.5)

    def test_set_music_volume_not_playing(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        mock_music.get_busy.return_value = False
        am.set_music_volume(0.3)
        assert am.music_volume == 0.3

    def test_set_ambient_volume(self, mock_audio_mixer):
        mock_channel, _, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.set_ambient_volume(0.7)
        assert am.ambient_volume == 0.7

    def test_set_voice_volume(self, mock_audio_mixer):
        am = audio.AudioManager()
        am.set_voice_volume(0.9)
        assert am.voice_volume == 0.9

    def test_set_sfx_volume(self, mock_audio_mixer):
        am = audio.AudioManager()
        am.set_sfx_volume(0.6)
        assert am.sfx_volume == 0.6

    def test_volume_clamps(self, mock_audio_mixer):
        am = audio.AudioManager()
        am.set_music_volume(2.0)
        assert am.music_volume == 1.0
        am.set_music_volume(-1.0)
        assert am.music_volume == 0.0


class TestAudioManagerMusic:
    def test_play_music(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.play_music("/fake/music.ogg")
        mock_music.load.assert_called_once()
        mock_music.play.assert_called_once()

    def test_play_music_error(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        mock_music.load.side_effect = Exception("file not found")
        am = audio.AudioManager()
        am.play_music("/fake/missing.ogg")  # should not raise

    def test_fade_to_music(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.fade_to_music("/fake/next.ogg", fade_ms=500)

    def test_stop_music(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.stop_music()
        mock_music.stop.assert_called_once()

    def test_stop_music_fadeout(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.stop_music(fade_ms=1000)
        mock_music.fadeout.assert_called_once_with(1000)

    def test_pause_resume_music(self, mock_audio_mixer):
        _, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.pause_music()
        mock_music.pause.assert_called_once()
        am.resume_music()
        mock_music.unpause.assert_called_once()


class TestAudioManagerAmbient:
    def test_play_ambient_with_path(self, mock_audio_mixer):
        mock_channel, _, mock_sound_cls = mock_audio_mixer
        am = audio.AudioManager()
        am.play_ambient("/fake/ambient.wav")
        mock_sound_cls.assert_called()
        mock_channel.play.assert_called()

    def test_play_ambient_generative(self, mock_audio_mixer):
        mock_channel, _, mock_sound_cls = mock_audio_mixer
        am = audio.AudioManager()
        am.play_ambient()  # No path — uses generated synth
        mock_channel.play.assert_called()

    def test_play_ambient_error(self, mock_audio_mixer):
        mock_channel, _, mock_sound_cls = mock_audio_mixer
        mock_sound_cls.side_effect = Exception("audio error")
        am = audio.AudioManager()
        am.play_ambient("/fake/bad.wav")  # should not raise


class TestAudioManagerSFX:
    def test_play_sfx_generated(self, mock_audio_mixer):
        mock_channel, _, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.play_sfx()  # No path — generated blip
        mock_channel.play.assert_called()

    def test_play_sfx_cached(self, mock_audio_mixer):
        mock_channel, _, mock_sound_cls = mock_audio_mixer
        mock_sound = MagicMock()
        mock_sound_cls.return_value = mock_sound
        am = audio.AudioManager()
        am.play_sfx("/fake/click.wav")
        am.play_sfx("/fake/click.wav")  # second call should use cache

    def test_play_sfx_error(self, mock_audio_mixer):
        mock_channel, _, mock_sound_cls = mock_audio_mixer
        mock_sound_cls.side_effect = Exception("error")
        am = audio.AudioManager()
        am.play_sfx("/fake/bad.wav")  # should not raise


class TestAudioManagerCleanup:
    def test_cleanup(self, mock_audio_mixer):
        mock_channel, mock_music, _ = mock_audio_mixer
        am = audio.AudioManager()
        am.cleanup()
        mock_music.stop.assert_called()
        mock_channel.stop.assert_called()
        assert len(am._sfx_cache) == 0


class TestAudioManagerGenerateWave:
    def test_generate_ambient_wave(self, mock_audio_mixer):
        am = audio.AudioManager()
        wav = am._generate_ambient_wave()
        assert isinstance(wav, bytes)
        assert len(wav) > 44  # WAV header minimum


# ===================================================================
# 3. agent_handoff_personality_integration.py
# ===================================================================
class TestAgentHandoffPersonalityIntegration:
    def test_init(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        assert ahpi.gui is gui

    def test_handle_agent_handoff(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        ahpi.handle_agent_handoff("metis")
        assert ahpi.current_agent == "metis"

    def test_get_handoff_info(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        ahpi.handle_agent_handoff("kallos")
        info = ahpi.get_handoff_info()
        assert "current_agent" in info
        assert info["current_agent"] == "kallos"

    def test_get_current_agent_color(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        ahpi.handle_agent_handoff("metis")
        color = ahpi.get_current_agent_color()
        assert isinstance(color, tuple)
        assert len(color) == 3

    def test_get_current_agent_icon(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        ahpi.handle_agent_handoff("hephaestus")
        icon = ahpi.get_current_agent_icon()
        assert isinstance(icon, str)

    def test_get_current_agent_animation(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        ahpi.handle_agent_handoff("metis")
        anim = ahpi.get_current_agent_animation()
        assert isinstance(anim, str)

    def test_get_current_agent_description(self):
        from hosts.gui.agent_handoff_personality_integration import (
            AgentHandoffPersonalityIntegration,
        )
        from hosts.gui.agent_personality_indicators import AgentPersonalityIndicators

        gui = Mock()
        api = AgentPersonalityIndicators()
        ahpi = AgentHandoffPersonalityIntegration(gui, api)
        ahpi.handle_agent_handoff("mneme")
        desc = ahpi.get_current_agent_description()
        assert isinstance(desc, str)


# ===================================================================
# 4. connection_gui_integration.py
# ===================================================================
import pygame

pygame.init()


class TestConnectionStatusDisplay:
    def test_init(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        assert csd.manager is cm

    def test_get_status_text(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        text = csd.get_status_text()
        assert isinstance(text, str)

    def test_get_status_color(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        color = csd.get_status_color()
        assert isinstance(color, tuple)
        assert len(color) == 3

    def test_is_showing_reconnect_button(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        result = csd.is_showing_reconnect_button()
        assert isinstance(result, bool)

    def test_update_button_rect(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        csd.update_button_rect(10, 20, 100, 30)
        assert csd.reconnect_button_rect == pygame.Rect(10, 20, 100, 30)

    def test_handle_click_miss(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        csd.update_button_rect(10, 20, 100, 30)
        result = csd.handle_click((500, 500))
        assert result is False

    def test_draw(self):
        from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
        from hosts.gui.connection_manager import ConnectionManager

        cm = ConnectionManager()
        csd = ConnectionStatusDisplay(cm)
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        csd.draw(surf, 10, 10)


# ===================================================================
# AudioManager — playlist daemon thread (M16 follow-on, 2026-04-27)
# ===================================================================


class TestPlaylistLifecycle:
    """`play_playlist` was previously fire-and-forget — every call spawned
    a fresh daemon, and toggling Music OFF audibly resurrected on track 2
    because the daemon's 1s polling loop saw `is_music_playing=False`
    just as the fade completed and called `play_next_track`. The fix
    adds a `threading.Event` shutdown signal + idempotency guard.
    """

    def test_play_playlist_is_idempotent(self, mock_audio_mixer):
        """Second call while the first daemon is still alive must NOT
        spawn a second thread (the original bug raced two daemons).
        """

        am = audio.AudioManager()
        am._playlist = ["/dev/null/track1.ogg", "/dev/null/track2.ogg"]

        am.play_playlist()
        first_thread = am._playlist_thread
        assert first_thread is not None
        assert first_thread.is_alive()

        am.play_playlist()
        second_thread = am._playlist_thread
        assert second_thread is first_thread, "play_playlist spawned a second daemon"

        am.stop_playlist()

    def test_stop_playlist_signals_daemon_to_exit(self, mock_audio_mixer):
        """The daemon must exit within ~1 polling tick of the shutdown
        signal — the loop now uses `Event.wait(timeout=1.0)` which
        returns immediately when the event is set.
        """

        am = audio.AudioManager()
        am._playlist = ["/dev/null/track.ogg"]

        am.play_playlist()
        thread = am._playlist_thread
        assert thread is not None and thread.is_alive()

        am.stop_playlist(timeout=2.0)
        assert not thread.is_alive(), "daemon did not exit within timeout"
        assert am._playlist_thread is None

    def test_stop_playlist_when_not_running_is_noop(self, mock_audio_mixer):
        """Safe to call before any `play_playlist` — covers the
        `_apply_audio_settings` case where music was OFF at startup.
        """

        am = audio.AudioManager()
        am.stop_playlist()  # Should not raise
        assert am._playlist_thread is None

    def test_play_playlist_can_restart_after_stop(self, mock_audio_mixer):
        """Toggle OFF then ON must spawn a fresh daemon — a stale
        `_playlist_shutdown.set()` from the previous stop would block
        the new loop forever otherwise.
        """

        am = audio.AudioManager()
        am._playlist = ["/dev/null/track.ogg"]

        am.play_playlist()
        am.stop_playlist(timeout=2.0)

        am.play_playlist()
        new_thread = am._playlist_thread
        assert new_thread is not None
        assert new_thread.is_alive()

        am.stop_playlist()
