# ruff: noqa: E402
from __future__ import annotations

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.tts_engine import AGENT_VOICES, VOICE_ROSTER, VoiceConfig


class TestVoiceConfig:
    def test_init(self):
        vc = VoiceConfig("Test", "en-US-TestNeural")
        assert vc.name == "Test"
        assert vc.edge_id == "en-US-TestNeural"
        assert vc.speed == 1.0
        assert vc.pitch == 1.0
        assert vc.emotion == "default"

    def test_custom_values(self):
        vc = VoiceConfig("Custom", "en-US-JennyNeural", speed=0.9, pitch=1.2, emotion="cheerful")
        assert vc.speed == 0.9
        assert vc.pitch == 1.2
        assert vc.emotion == "cheerful"


class TestVoiceRoster:
    def test_roster_has_voices(self):
        assert len(VOICE_ROSTER) >= 5
        assert "aria" in VOICE_ROSTER
        assert "jenny" in VOICE_ROSTER

    def test_all_agents_have_voices(self):
        for agent, voice_key in AGENT_VOICES.items():
            assert voice_key in VOICE_ROSTER, f"Agent {agent} maps to unknown voice {voice_key}"

    def test_agent_voices_complete(self):
        expected = {"hephaestus", "metis", "kallos", "mneme", "techne", "dokimasia"}
        assert expected.issubset(set(AGENT_VOICES.keys()))


class TestAudioManagerGenerateWave:
    """Test the pure-logic _generate_ambient_wave method without mixer init."""

    def test_generate_ambient_wave(self):
        from hosts.gui.audio_manager import AudioManager

        # Bypass singleton + mixer init
        am = object.__new__(AudioManager)
        wav_data = am._generate_ambient_wave()
        assert isinstance(wav_data, bytes)
        assert len(wav_data) > 44
