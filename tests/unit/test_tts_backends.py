"""Unit tests for TTS voice config + agent → voice mapping.

The Kokoro/Edge backend test classes lived alongside these until M19
Phase 3 retired the ``TTSBackend`` ABC. The voice-config primitives stay
(both ``RealtimeTTSEngine`` and the agent map import them).
"""

import pytest

from kourai_common.tts_backend import (
    _DEFAULT_EXPRESSION,
    AGENT_EXPRESSION_MAP,
    AGENT_VOICE_MAP,
    ChatterboxExpression,
    TTSVoiceConfig,
    get_expression_for_agent,
)


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


class TestChatterboxExpression:
    """Per-maiden Chatterbox exaggeration/cfg_weight cast (M6 step 3).

    Derived from each maiden's documented register in
    ``tools/voice-lab/VOICE_CASTING_PLAN.md`` (ElevenLabs ``style`` → Chatterbox
    ``exaggeration``) and her Kokoro ``speed`` (→ ``cfg_weight`` pacing). Values
    are by-ear-tunable starting points; these tests pin the *principle*, not the
    exact numbers, so AJ can retune without churning the suite.
    """

    def test_every_voiced_agent_has_an_expression(self):
        # No maiden silently falls back to a flat default when Chatterbox is on.
        assert set(AGENT_EXPRESSION_MAP) == set(AGENT_VOICE_MAP)

    def test_expressions_within_chatterbox_natural_band(self):
        # Valid Chatterbox ranges are exaggeration 0.25-2.0, cfg_weight 0.0-1.0,
        # but the casting plan says "avoid cartoon extremes" — stay in-band.
        for name, e in AGENT_EXPRESSION_MAP.items():
            assert 0.30 <= e.exaggeration <= 0.80, name
            assert 0.30 <= e.cfg_weight <= 0.70, name

    def test_expression_follows_casting_principle(self):
        # VOICE_CASTING_PLAN: "more expressive for Puck and Kallos, calmer for
        # Aletheia and Aidos."
        exp = AGENT_EXPRESSION_MAP
        for expressive in ("kallos", "puck", "cupid"):
            for calm in ("aidos", "aletheia"):
                assert exp[expressive].exaggeration > exp[calm].exaggeration, (expressive, calm)

    def test_cfg_weight_preserves_per_maiden_pacing(self):
        # Chatterbox has no Kokoro-style speed; cfg_weight is its pacing lever
        # (lower = quicker). Deliberate maidens stay slower than animated ones.
        exp = AGENT_EXPRESSION_MAP
        assert exp["aidos"].cfg_weight > exp["kallos"].cfg_weight
        assert exp["dokimasia"].cfg_weight > exp["puck"].cfg_weight

    def test_get_expression_for_agent_resolves_and_defaults(self):
        assert get_expression_for_agent("KALLOS") == AGENT_EXPRESSION_MAP["kallos"]
        assert get_expression_for_agent(None) == _DEFAULT_EXPRESSION
        assert get_expression_for_agent("nonexistent") == _DEFAULT_EXPRESSION

    def test_chatterbox_expression_rejects_out_of_range(self):
        with pytest.raises(ValueError, match="exaggeration"):
            ChatterboxExpression(exaggeration=2.5, cfg_weight=0.5)
        with pytest.raises(ValueError, match="cfg_weight"):
            ChatterboxExpression(exaggeration=0.5, cfg_weight=1.5)
