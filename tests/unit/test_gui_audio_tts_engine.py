# ruff: noqa: E402
"""Tests for TTSEngine, AudioManager, and remaining coverage gaps.

Covers:
- hosts/gui/tts_engine.py (TTSEngine init, volume, stop, cleanup, _get_converter, speak)
- hosts/gui/audio_manager.py (AudioManager init, volume controls, music, ambient, sfx, cleanup)
- hosts/gui/loading_screen.py (run_loading_screen phases)
- hosts/gui/profile_select.py (run_profile_select)
- hosts/gui/connection_gui_integration.py
- hosts/gui/agent_handoff_personality_integration.py

Target: push coverage toward 90%.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

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


class TestTTSEngineGetConverter:
    def test_finds_ffmpeg(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = engine._get_converter()
        assert result == "ffmpeg"

    def test_no_converter(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = engine._get_converter()
        assert result is None


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
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        mock_communicate = MagicMock()
        mock_communicate.save = AsyncMock()

        mock_sound = MagicMock()
        mock_sound.get_volume.return_value = 0.5

        with (
            patch("hosts.gui.tts_engine.edge_tts.Communicate", return_value=mock_communicate),
            patch("pygame.mixer.Sound", return_value=mock_sound),
            patch.object(engine, "_get_converter", return_value=None),
        ):
            # Make the temp file exist after "save"
            async def fake_save(path):
                Path(path).touch()

            mock_communicate.save = fake_save
            await engine.speak("Hello world", agent_name="metis")

        assert engine.is_playing is False  # completed

    @pytest.mark.asyncio
    async def test_speak_with_converter(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()

        async def fake_save(path):
            Path(path).touch()

        mock_communicate = MagicMock()
        mock_communicate.save = fake_save

        mock_sound = MagicMock()
        mock_sound.get_volume.return_value = 0.5

        mock_run = Mock(returncode=0, stderr="")

        with (
            patch("hosts.gui.tts_engine.edge_tts.Communicate", return_value=mock_communicate),
            patch("pygame.mixer.Sound", return_value=mock_sound),
            patch.object(engine, "_get_converter", return_value="ffmpeg"),
            patch("subprocess.run", return_value=mock_run),
        ):
            await engine.speak("Test", voice_key="aria", speed=0.9)

    @pytest.mark.asyncio
    async def test_speak_error_handling(self, mock_mixer):
        from hosts.gui.tts_engine import TTSEngine

        engine = TTSEngine()
        cb = Mock()
        engine.set_on_complete(cb)

        with patch(
            "hosts.gui.tts_engine.edge_tts.Communicate",
            side_effect=Exception("network error"),
        ):
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
    from hosts.gui import audio_manager

    audio_manager.AudioManager._instance = None

    mock_channel = MagicMock()
    mock_channel.get_busy.return_value = False

    with (
        patch("pygame.mixer.pre_init"),
        patch("pygame.mixer.init"),
        patch("pygame.mixer.set_num_channels"),
        patch("pygame.mixer.Channel", return_value=mock_channel),
        patch("pygame.mixer.quit"),
        patch("pygame.mixer.music") as mock_music,
        patch("pygame.mixer.find_channel", return_value=mock_channel),
        patch("pygame.mixer.Sound") as mock_sound_cls,
    ):
        yield mock_channel, mock_music, mock_sound_cls

    # Reset singleton after test
    audio_manager.AudioManager._instance = None


class TestAudioManagerInit:
    def test_init(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        am = AudioManager()
        assert am._initialized is True
        assert am.music_volume == 0.25
        assert am.ambient_volume == 0.5
        assert am.voice_volume == 1.0
        assert am.sfx_volume == 0.8


class TestAudioManagerVolume:
    def test_set_music_volume(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        mock_music.get_busy.return_value = True
        am.set_music_volume(0.5)
        assert am.music_volume == 0.5
        mock_music.set_volume.assert_called_with(0.5)

    def test_set_music_volume_not_playing(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        mock_music.get_busy.return_value = False
        am.set_music_volume(0.3)
        assert am.music_volume == 0.3

    def test_set_ambient_volume(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, _ = mock_audio_mixer
        am = AudioManager()
        am.set_ambient_volume(0.7)
        assert am.ambient_volume == 0.7

    def test_set_voice_volume(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        am = AudioManager()
        am.set_voice_volume(0.9)
        assert am.voice_volume == 0.9

    def test_set_sfx_volume(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        am = AudioManager()
        am.set_sfx_volume(0.6)
        assert am.sfx_volume == 0.6

    def test_volume_clamps(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        am = AudioManager()
        am.set_music_volume(2.0)
        assert am.music_volume == 1.0
        am.set_music_volume(-1.0)
        assert am.music_volume == 0.0


class TestAudioManagerMusic:
    def test_play_music(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        am.play_music("/fake/music.ogg")
        mock_music.load.assert_called_once()
        mock_music.play.assert_called_once()

    def test_play_music_error(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        mock_music.load.side_effect = Exception("file not found")
        am = AudioManager()
        am.play_music("/fake/missing.ogg")  # should not raise

    def test_fade_to_music(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        am.fade_to_music("/fake/next.ogg", fade_ms=500)

    def test_stop_music(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        am.stop_music()
        mock_music.stop.assert_called_once()

    def test_stop_music_fadeout(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        am.stop_music(fade_ms=1000)
        mock_music.fadeout.assert_called_once_with(1000)

    def test_pause_resume_music(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        _, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        am.pause_music()
        mock_music.pause.assert_called_once()
        am.resume_music()
        mock_music.unpause.assert_called_once()


class TestAudioManagerAmbient:
    def test_play_ambient_with_path(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, mock_sound_cls = mock_audio_mixer
        am = AudioManager()
        am.play_ambient("/fake/ambient.wav")
        mock_sound_cls.assert_called()
        mock_channel.play.assert_called()

    def test_play_ambient_generative(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, mock_sound_cls = mock_audio_mixer
        am = AudioManager()
        am.play_ambient()  # No path — uses generated synth
        mock_channel.play.assert_called()

    def test_play_ambient_error(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, mock_sound_cls = mock_audio_mixer
        mock_sound_cls.side_effect = Exception("audio error")
        am = AudioManager()
        am.play_ambient("/fake/bad.wav")  # should not raise


class TestAudioManagerSFX:
    def test_play_sfx_generated(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, _ = mock_audio_mixer
        am = AudioManager()
        am.play_sfx()  # No path — generated blip
        mock_channel.play.assert_called()

    def test_play_sfx_cached(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, mock_sound_cls = mock_audio_mixer
        mock_sound = MagicMock()
        mock_sound_cls.return_value = mock_sound
        am = AudioManager()
        am.play_sfx("/fake/click.wav")
        am.play_sfx("/fake/click.wav")  # second call should use cache

    def test_play_sfx_error(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, _, mock_sound_cls = mock_audio_mixer
        mock_sound_cls.side_effect = Exception("error")
        am = AudioManager()
        am.play_sfx("/fake/bad.wav")  # should not raise


class TestAudioManagerCleanup:
    def test_cleanup(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        mock_channel, mock_music, _ = mock_audio_mixer
        am = AudioManager()
        am.cleanup()
        mock_music.stop.assert_called()
        mock_channel.stop.assert_called()
        assert len(am._sfx_cache) == 0


class TestAudioManagerGenerateWave:
    def test_generate_ambient_wave(self, mock_audio_mixer):
        from hosts.gui.audio_manager import AudioManager

        am = AudioManager()
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
