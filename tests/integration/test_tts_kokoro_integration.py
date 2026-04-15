"""Full integration tests: Kokoro + Edge-TTS backends with audio validation."""

import io
import os
import wave

import pytest

from kourai_common.tts_backend import AGENT_VOICE_MAP, TTSVoiceConfig

_IN_CI = os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}


def _skip_or_fail_unavailable(reason: str) -> None:
    if _IN_CI:
        pytest.fail(reason)
    pytest.skip(reason)


def _read_wav_duration(wav_bytes: bytes) -> float:
    """Parse WAV bytes and return duration in seconds."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / rate if rate > 0 else 0.0
    except Exception:
        return 0.0


def _validate_wav(wav_bytes: bytes) -> bool:
    """Check if bytes are a valid WAV file."""
    return len(wav_bytes) >= 44 and wav_bytes[:4] == b"RIFF" and wav_bytes[8:12] == b"WAVE"


@pytest.mark.asyncio
@pytest.mark.integration
class TestKokoroIntegration:
    """Integration tests for Kokoro TTS backend."""

    @pytest.fixture
    def kokoro_backend(self):
        """Create a Kokoro backend instance."""
        try:
            from kourai_common.tts_kokoro import KokoroBackend

            return KokoroBackend()
        except ImportError:
            _skip_or_fail_unavailable("Kokoro not installed")

    async def test_kokoro_all_agent_voices_synthesize(self, kokoro_backend):
        """Synthesize speech for all 10 agents using Kokoro."""
        for agent_name, voice_cfg in AGENT_VOICE_MAP.items():
            text = f"Hello, I am {agent_name}."
            audio = await kokoro_backend.synthesize(text, voice_cfg)

            assert len(audio) > 0, f"{agent_name} produced no audio"
            assert _validate_wav(audio), f"{agent_name} audio is not valid WAV"

            duration = _read_wav_duration(audio)
            assert 0.5 < duration < 10.0, (
                f"{agent_name} duration {duration}s is unexpected (expected 0.5-10s)"
            )

    async def test_kokoro_prosody_variations_produce_different_audio(self, kokoro_backend):
        """Verify speed/pitch variations produce different audio."""
        voice_normal = TTSVoiceConfig("Sarah", "af_sarah", speed=1.0, pitch=1.0)
        voice_fast = TTSVoiceConfig("Sarah", "af_sarah", speed=1.5, pitch=1.0)
        voice_high = TTSVoiceConfig("Sarah", "af_sarah", speed=1.0, pitch=1.3)

        text = "The quick brown fox jumps over the lazy dog."

        audio_normal = await kokoro_backend.synthesize(text, voice_normal)
        audio_fast = await kokoro_backend.synthesize(text, voice_fast)
        audio_high = await kokoro_backend.synthesize(text, voice_high)

        # Different prosody should produce different byte sequences
        assert audio_normal != audio_fast
        assert audio_normal != audio_high

        # Fast should be shorter duration
        dur_normal = _read_wav_duration(audio_normal)
        dur_fast = _read_wav_duration(audio_fast)
        assert dur_fast < dur_normal * 0.8, (
            f"Fast duration {dur_fast}s should be <80% of normal {dur_normal}s"
        )

    async def test_kokoro_long_text_synthesizes_successfully(self, kokoro_backend):
        """Kokoro should handle longer text."""
        voice = TTSVoiceConfig("Sarah", "af_sarah")
        long_text = (
            "Imagine standing at the threshold of a grand forge, where sparks dance "
            "like golden fireflies and the air hums with possibility. The Golden Maidens "
            "wait within, each bearing the tools of their expertise."
        )

        audio = await kokoro_backend.synthesize(long_text, voice)

        assert len(audio) > 0
        assert _validate_wav(audio)

        duration = _read_wav_duration(audio)
        assert duration > 5.0, "Longer text should produce longer audio"

    async def test_kokoro_british_accent_voice(self, kokoro_backend):
        """Kokoro should support British English voices."""
        voice = TTSVoiceConfig("Emma", "bf_emma", lang_code="b")
        text = "How do you do? I'm from Britain."

        audio = await kokoro_backend.synthesize(text, voice)

        assert len(audio) > 0
        assert _validate_wav(audio)

    async def test_kokoro_american_accent_voice(self, kokoro_backend):
        """Kokoro should support American English voices."""
        voice = TTSVoiceConfig("Sarah", "af_sarah", lang_code="a")
        text = "Hey there! I'm from America."

        audio = await kokoro_backend.synthesize(text, voice)

        assert len(audio) > 0
        assert _validate_wav(audio)

    async def test_kokoro_multiple_agents_concurrent(self, kokoro_backend):
        """Kokoro should handle multiple agent voices without interference."""
        import asyncio

        async def synthesize_agent(agent_name: str, voice_cfg: TTSVoiceConfig):
            text = f"My name is {agent_name}."
            return agent_name, await kokoro_backend.synthesize(text, voice_cfg)

        # Synthesize 3 agents concurrently
        tasks = [
            synthesize_agent("hephaestus", AGENT_VOICE_MAP["hephaestus"]),
            synthesize_agent("metis", AGENT_VOICE_MAP["metis"]),
            synthesize_agent("kallos", AGENT_VOICE_MAP["kallos"]),
        ]

        results = await asyncio.gather(*tasks)

        for agent_name, audio in results:
            assert len(audio) > 0, f"{agent_name} produced no audio"
            assert _validate_wav(audio), f"{agent_name} audio is not valid WAV"


@pytest.mark.asyncio
@pytest.mark.integration
class TestEdgeTTSIntegration:
    """Integration tests for Edge-TTS backend."""

    @pytest.fixture
    def edge_backend(self):
        """Create an Edge-TTS backend instance."""
        try:
            from kourai_common.tts_edge import EdgeTTSBackend

            return EdgeTTSBackend()
        except ImportError:
            _skip_or_fail_unavailable("edge-tts not installed")

    async def test_edge_tts_voice_mapping_for_agents(self, edge_backend):
        """Edge-TTS should handle Kokoro voice IDs via mapping."""
        # Test a few agent voices map to Edge-specific IDs
        for agent_name in ["hephaestus", "metis", "kallos"]:
            voice = AGENT_VOICE_MAP[agent_name]
            audio = await edge_backend.synthesize(f"Test from {agent_name}", voice)

            assert len(audio) > 0, f"{agent_name} produced no audio via Edge-TTS"

    async def test_edge_tts_multiple_voices(self, edge_backend):
        """Edge-TTS should work with various voice IDs."""
        voice_configs = [
            TTSVoiceConfig("Aria", "en-US-AriaNeural"),
            TTSVoiceConfig("Guy", "en-US-GuyNeural"),
            TTSVoiceConfig("Sonia", "en-GB-SoniaNeural"),
        ]

        for voice_cfg in voice_configs:
            audio = await edge_backend.synthesize("Test message", voice_cfg)
            assert len(audio) > 0


@pytest.mark.asyncio
@pytest.mark.integration
class TestBackendInteroperability:
    """Integration tests for backend switching and fallback."""

    async def test_backend_fallback_to_edge_tts(self):
        """If Kokoro missing, should fallback to edge-tts."""
        from tts_engine import _create_default_backend

        backend = _create_default_backend()
        assert backend is not None

        voice = TTSVoiceConfig("Sarah", "af_sarah")
        audio = await backend.synthesize("Test fallback", voice)

        assert len(audio) > 0

    async def test_different_backends_same_voice_config(self):
        """Both backends should accept same voice config."""
        kokoro = None
        try:
            from kourai_common.tts_kokoro import KokoroBackend

            kokoro = KokoroBackend()
            has_kokoro = True
        except ImportError:
            has_kokoro = False

        edge = None
        try:
            from kourai_common.tts_edge import EdgeTTSBackend

            edge = EdgeTTSBackend()
            has_edge = True
        except ImportError:
            has_edge = False

        if not (has_kokoro or has_edge):
            _skip_or_fail_unavailable("Neither Kokoro nor Edge-TTS available")

        voice = TTSVoiceConfig("Sarah", "af_sarah")

        if has_kokoro and kokoro is not None:
            audio_kokoro = await kokoro.synthesize("Test", voice)
            assert len(audio_kokoro) > 0

        if has_edge and edge is not None:
            audio_edge = await edge.synthesize("Test", voice)
            assert len(audio_edge) > 0
