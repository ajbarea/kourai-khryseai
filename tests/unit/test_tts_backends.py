"""Unit tests for TTS voice config + agent → voice mapping.

The Kokoro/Edge backend test classes lived alongside these until M19
Phase 3 retired the ``TTSBackend`` ABC. The voice-config primitives stay
(both ``RealtimeTTSEngine`` and the agent map import them).
"""

import pytest

from kourai_common.tts_backend import AGENT_VOICE_MAP, TTSVoiceConfig


class TestTTSVoiceConfigValidation:
    """Test voice config parameter validation."""

    def test_valid_voice_config(self):
        voice = TTSVoiceConfig(
            name="Sarah",
            voice_id="af_sarah",
            speed=1.0,
            pitch=1.0,
            lang_code="a",
        )
        assert voice.name == "Sarah"
        assert voice.voice_id == "af_sarah"

    def test_invalid_speed_too_low(self):
        with pytest.raises(ValueError, match=r"speed must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", speed=0.4)

    def test_invalid_speed_too_high(self):
        with pytest.raises(ValueError, match=r"speed must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", speed=2.1)

    def test_invalid_pitch_too_low(self):
        with pytest.raises(ValueError, match=r"pitch must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", pitch=0.4)

    def test_invalid_pitch_too_high(self):
        with pytest.raises(ValueError, match=r"pitch must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", pitch=2.1)

    def test_invalid_lang_code(self):
        with pytest.raises(ValueError, match=r"lang_code must be 'a'.*'b'"):
            TTSVoiceConfig("Sarah", "af_sarah", lang_code="c")

    def test_valid_speed_boundaries(self):
        assert TTSVoiceConfig("Sarah", "af_sarah", speed=0.5).speed == 0.5
        assert TTSVoiceConfig("Sarah", "af_sarah", speed=2.0).speed == 2.0

    def test_valid_pitch_boundaries(self):
        assert TTSVoiceConfig("Sarah", "af_sarah", pitch=0.5).pitch == 0.5
        assert TTSVoiceConfig("Sarah", "af_sarah", pitch=2.0).pitch == 2.0


class TestAgentVoiceMapping:
    """Tests for the agent → voice map and resolver."""

    def test_all_agents_have_voices(self):
        assert len(AGENT_VOICE_MAP) == 10
        expected_agents = {
            "hephaestus",
            "metis",
            "kallos",
            "mneme",
            "techne",
            "dokimasia",
            "puck",
            "cupid",
            "aidos",
            "aletheia",
        }
        assert set(AGENT_VOICE_MAP.keys()) == expected_agents

    def test_agent_voice_configs_valid(self):
        for voice_cfg in AGENT_VOICE_MAP.values():
            assert voice_cfg.voice_id
            assert voice_cfg.name
            assert 0.5 <= voice_cfg.speed <= 2.0
            assert 0.5 <= voice_cfg.pitch <= 2.0
            assert voice_cfg.lang_code in ("a", "b")

    def test_get_voice_for_agent_function(self):
        from kourai_common.tts_backend import get_voice_for_agent

        assert get_voice_for_agent("hephaestus").voice_id == "am_michael"
        assert get_voice_for_agent("metis").voice_id == "af_sarah"
        # Unknown agent and None both fall back to the default
        assert get_voice_for_agent("unknown_agent").voice_id == "af_heart"
        assert get_voice_for_agent(None).voice_id == "af_heart"
