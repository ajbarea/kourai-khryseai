"""Unit tests for TTSBackend implementations (Kokoro + Edge-TTS).

Comprehensive coverage for voice config validation, both backends, and fallback behavior.
"""

import pytest

from kourai_common.tts_backend import AGENT_VOICE_MAP, TTSVoiceConfig

# ===================================================================
# TTSVoiceConfig Validation Tests
# ===================================================================


class TestTTSVoiceConfigValidation:
    """Test voice config parameter validation."""

    def test_valid_voice_config(self):
        """Valid voice config should not raise."""
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
        """Speed below 0.5 should raise ValueError."""
        with pytest.raises(ValueError, match=r"speed must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", speed=0.4)

    def test_invalid_speed_too_high(self):
        """Speed above 2.0 should raise ValueError."""
        with pytest.raises(ValueError, match=r"speed must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", speed=2.1)

    def test_invalid_pitch_too_low(self):
        """Pitch below 0.5 should raise ValueError."""
        with pytest.raises(ValueError, match=r"pitch must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", pitch=0.4)

    def test_invalid_pitch_too_high(self):
        """Pitch above 2.0 should raise ValueError."""
        with pytest.raises(ValueError, match=r"pitch must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Sarah", "af_sarah", pitch=2.1)

    def test_invalid_lang_code(self):
        """lang_code must be 'a' or 'b'."""
        with pytest.raises(ValueError, match=r"lang_code must be 'a'.*'b'"):
            TTSVoiceConfig("Sarah", "af_sarah", lang_code="c")

    def test_valid_speed_boundaries(self):
        """Speed at boundaries (0.5, 2.0) should be valid."""
        voice_slow = TTSVoiceConfig("Sarah", "af_sarah", speed=0.5)
        assert voice_slow.speed == 0.5

        voice_fast = TTSVoiceConfig("Sarah", "af_sarah", speed=2.0)
        assert voice_fast.speed == 2.0

    def test_valid_pitch_boundaries(self):
        """Pitch at boundaries (0.5, 2.0) should be valid."""
        voice_low = TTSVoiceConfig("Sarah", "af_sarah", pitch=0.5)
        assert voice_low.pitch == 0.5

        voice_high = TTSVoiceConfig("Sarah", "af_sarah", pitch=2.0)
        assert voice_high.pitch == 2.0


# ===================================================================
# KokoroBackend Tests
# ===================================================================


@pytest.mark.asyncio
class TestKokoroBackend:
    """Unit tests for KokoroBackend."""

    @pytest.fixture
    def kokoro_backend(self):
        """Create a Kokoro backend instance."""
        import importlib.util

        if importlib.util.find_spec("kokoro") is None:
            pytest.skip("Kokoro not installed")

        from kourai_common.tts_kokoro import KokoroBackend

        return KokoroBackend()

    async def test_kokoro_synthesize_returns_wav_bytes(self, kokoro_backend):
        """Kokoro should return WAV bytes with RIFF header."""
        voice = TTSVoiceConfig("Sarah", "af_sarah")
        audio = await kokoro_backend.synthesize("Hello, world!", voice)

        assert len(audio) > 0
        assert audio[:4] == b"RIFF", "Audio should be WAV format with RIFF header"
        assert audio[8:12] == b"WAVE", "Audio should have WAVE format identifier"

    async def test_kokoro_empty_text_returns_empty_bytes(self, kokoro_backend):
        """Kokoro should return empty bytes for empty text."""
        voice = TTSVoiceConfig("Sarah", "af_sarah")

        audio = await kokoro_backend.synthesize("", voice)
        assert audio == b""

        audio = await kokoro_backend.synthesize("   ", voice)
        assert audio == b""

    async def test_kokoro_available_voices_not_empty(self, kokoro_backend):
        """Kokoro should list available voices."""
        voices = kokoro_backend.available_voices()

        assert len(voices) >= 23, "Kokoro should have at least 23 English voices"
        assert all(hasattr(v, "voice_id") for v in voices)
        assert all(hasattr(v, "name") for v in voices)

    async def test_kokoro_sample_rate_is_24khz(self, kokoro_backend):
        """Kokoro outputs 24kHz."""
        assert kokoro_backend.sample_rate == 24000

    async def test_kokoro_synthesize_with_speed_override(self, kokoro_backend):
        """Kokoro should respect speed parameter."""
        voice_normal = TTSVoiceConfig("Sarah", "af_sarah", speed=1.0)
        voice_fast = TTSVoiceConfig("Sarah", "af_sarah", speed=1.5)

        audio_normal = await kokoro_backend.synthesize("Test text", voice_normal)
        audio_fast = await kokoro_backend.synthesize("Test text", voice_fast)

        assert len(audio_normal) > 0
        assert len(audio_fast) > 0
        # Fast audio should be shorter (more compressed at 1.5x speed)
        assert len(audio_fast) < len(audio_normal)

    async def test_kokoro_synthesize_with_pitch_override(self, kokoro_backend):
        """Kokoro should respect pitch parameter."""
        voice_normal = TTSVoiceConfig("Sarah", "af_sarah", pitch=1.0)
        voice_high = TTSVoiceConfig("Sarah", "af_sarah", pitch=1.2)

        audio_normal = await kokoro_backend.synthesize("Test", voice_normal)
        audio_high = await kokoro_backend.synthesize("Test", voice_high)

        assert len(audio_normal) > 0
        assert len(audio_high) > 0

    async def test_kokoro_invalid_voice_id_raises_error(self, kokoro_backend):
        """Kokoro should handle invalid voice_id gracefully."""
        voice = TTSVoiceConfig("Invalid", "nonexistent_voice_id")

        with pytest.raises(RuntimeError):
            await kokoro_backend.synthesize("Test", voice)

    async def test_kokoro_invalid_speed_rejected_at_config(self):
        """TTSVoiceConfig should reject invalid speed."""
        with pytest.raises(ValueError, match=r"speed must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Test", "af_sarah", speed=3.0)

        with pytest.raises(ValueError, match=r"speed must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Test", "af_sarah", speed=0.2)

    async def test_kokoro_invalid_pitch_rejected_at_config(self):
        """TTSVoiceConfig should reject invalid pitch."""
        with pytest.raises(ValueError, match=r"pitch must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Test", "af_sarah", pitch=2.5)

        with pytest.raises(ValueError, match=r"pitch must be between 0\.5 and 2\.0"):
            TTSVoiceConfig("Test", "af_sarah", pitch=0.3)

    async def test_kokoro_invalid_lang_code_rejected_at_config(self):
        """TTSVoiceConfig should reject invalid lang_code."""
        with pytest.raises(
            ValueError, match=r"lang_code must be 'a' \(American\) or 'b' \(British\)"
        ):
            TTSVoiceConfig("Test", "af_sarah", lang_code="z")

    async def test_kokoro_valid_lang_codes_accepted(self):
        """TTSVoiceConfig should accept valid lang codes."""
        # Should not raise
        config_a = TTSVoiceConfig("Test", "af_sarah", lang_code="a")
        assert config_a.lang_code == "a"

        config_b = TTSVoiceConfig("Test", "bf_emma", lang_code="b")
        assert config_b.lang_code == "b"

    async def test_kokoro_synthesize_to_file(self, kokoro_backend, tmp_path):
        """TTSBackend.synthesize_to_file() should save WAV to disk."""
        voice = TTSVoiceConfig("Sarah", "af_sarah")
        output = tmp_path / "test_output.wav"

        result = await kokoro_backend.synthesize_to_file("Hello world", voice, output)

        assert output.exists()
        assert result == output
        assert output.read_bytes()[:4] == b"RIFF"


@pytest.mark.asyncio
class TestEdgeTTSBackend:
    """Unit tests for EdgeTTSBackend."""

    @pytest.fixture
    def edge_backend(self):
        """Create an Edge-TTS backend instance."""
        try:
            from kourai_common.tts_edge import EdgeTTSBackend

            return EdgeTTSBackend()
        except ImportError:
            pytest.skip("edge-tts not installed")

    async def test_edge_tts_voice_mapping(self, edge_backend):
        """Edge-TTS should map Kokoro voice IDs to Edge Neural IDs."""
        voice = TTSVoiceConfig("Sarah", "af_sarah")  # Kokoro ID

        from unittest.mock import patch

        async def mock_stream():
            yield {"type": "audio", "data": b"dummy"}

        with patch("kourai_common.tts_edge.edge_tts.Communicate") as mock_comm:
            mock_comm.return_value.stream = mock_stream
            # Should succeed (internally maps to en-US-AriaNeural)
            audio = await edge_backend.synthesize("Test message", voice)
            assert len(audio) > 0
            mock_comm.assert_called_with(
                "Test message", voice="en-US-AriaNeural", rate="+0%", pitch="+0Hz"
            )

    async def test_edge_tts_returns_mp3_bytes(self, edge_backend):
        """Edge-TTS should return MP3 bytes."""
        voice = TTSVoiceConfig("Aria", "en-US-AriaNeural")

        from unittest.mock import patch

        async def mock_stream():
            yield {"type": "audio", "data": b"ID3\x04\x00\x00\x00\x00\x00"}

        with patch("kourai_common.tts_edge.edge_tts.Communicate") as mock_comm:
            mock_comm.return_value.stream = mock_stream
            audio = await edge_backend.synthesize("Hello", voice)

            assert len(audio) > 0
            # MP3 headers can be ID3 (ID3) or FF FA/FB (MPEG sync)
            is_id3 = audio[:3] == b"ID3"
            is_mpeg = audio[0:2] in (b"\xff\xfa", b"\xff\xfb")
            assert is_id3 or is_mpeg, "Audio should be MP3 format"

    async def test_edge_tts_empty_text_returns_empty(self, edge_backend):
        """Edge-TTS should return empty for empty text."""
        voice = TTSVoiceConfig("Aria", "en-US-AriaNeural")

        audio = await edge_backend.synthesize("", voice)
        assert audio == b""

    async def test_edge_tts_available_voices_not_empty(self, edge_backend):
        """Edge-TTS should list available voices."""
        voices = edge_backend.available_voices()

        assert len(voices) > 0
        assert all(hasattr(v, "voice_id") for v in voices)

    async def test_edge_tts_sample_rate_is_24khz(self, edge_backend):
        """Edge-TTS outputs 24kHz."""
        assert edge_backend.sample_rate == 24000


@pytest.mark.asyncio
class TestAgentVoiceMapping:
    """Unit tests for agent voice mapping."""

    async def test_all_agents_have_voices(self):
        """All 10 agents should have voice configs."""
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

    async def test_agent_voice_configs_valid(self):
        """All agent voices should be valid configs."""
        for voice_cfg in AGENT_VOICE_MAP.values():
            # Should not raise ValueError
            assert voice_cfg.voice_id
            assert voice_cfg.name
            assert 0.5 <= voice_cfg.speed <= 2.0
            assert 0.5 <= voice_cfg.pitch <= 2.0
            assert voice_cfg.lang_code in ("a", "b")

    async def test_get_voice_for_agent_function(self):
        """get_voice_for_agent() should resolve agent names."""
        from kourai_common.tts_backend import get_voice_for_agent

        # Test known agents
        voice = get_voice_for_agent("hephaestus")
        assert voice.voice_id == "am_michael"

        voice = get_voice_for_agent("metis")
        assert voice.voice_id == "af_sarah"

        # Test unknown agent (should use default)
        voice = get_voice_for_agent("unknown_agent")
        assert voice.voice_id == "af_heart"

        # Test None (should use default)
        voice = get_voice_for_agent(None)
        assert voice.voice_id == "af_heart"


@pytest.mark.asyncio
class TestBackendFallback:
    """Unit tests for backend fallback behavior."""

    async def test_create_default_backend_function(self):
        """_create_default_backend() should prefer Kokoro, fallback to edge-tts."""
        from hosts.gui.tts_engine import _create_default_backend

        backend = _create_default_backend()

        assert backend is not None
        backend_name = type(backend).__name__

        # Should be either Kokoro or Edge-TTS
        assert backend_name in ("KokoroBackend", "EdgeTTSBackend")
