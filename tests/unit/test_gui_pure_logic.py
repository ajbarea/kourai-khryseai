"""Comprehensive unit tests for GUI pure-logic modules.

Covers dialogue_pacing, emote_sfx, audio_utils, and maidens — all without
requiring pygame or any GUI toolkit.
"""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("numpy")

import numpy as np

# ---------------------------------------------------------------------------
# Module 3: audio_utils
# ---------------------------------------------------------------------------
from hosts.gui.audio_utils import (
    AGENT_PROFILES,
    AudioFadeEffect,
    AudioMetrics,
    AudioNormalizer,
    AudioVisualizer,
    PersonalityAudioProfile,
)

# ---------------------------------------------------------------------------
# Module 1: dialogue_pacing
# ---------------------------------------------------------------------------
from hosts.gui.dialogue_pacing import DialoguePacer, PacingConfig, PacingMode

# ---------------------------------------------------------------------------
# Module 2: emote_sfx
# ---------------------------------------------------------------------------
from hosts.gui.emote_sfx import extract_emotes, play_emote_sfx, resolve_sfx

# ---------------------------------------------------------------------------
# Module 4: maidens
# ---------------------------------------------------------------------------
from hosts.gui.maidens import (
    AGENTS,
    HANDOFF_LINES,
    VICTORY_LINES,
    detect_agent,
    get_avatar_path,
)


# ===================================================================
# 1. PacingMode enum
# ===================================================================
class TestPacingMode:
    """PacingMode enum coverage."""

    def test_instant_value(self) -> None:
        assert PacingMode.INSTANT.value == 0.0

    def test_fast_value(self) -> None:
        assert PacingMode.FAST.value == 0.5

    def test_normal_value(self) -> None:
        assert PacingMode.NORMAL.value == 1.5

    def test_slow_value(self) -> None:
        assert PacingMode.SLOW.value == 3.0

    def test_custom_value(self) -> None:
        assert PacingMode.CUSTOM.value == -1

    def test_all_members_present(self) -> None:
        names = {m.name for m in PacingMode}
        assert names == {"INSTANT", "FAST", "NORMAL", "SLOW", "CUSTOM"}


# ===================================================================
# 2. PacingConfig dataclass
# ===================================================================
class TestPacingConfig:
    """PacingConfig defaults and custom values."""

    def test_defaults(self) -> None:
        cfg = PacingConfig()
        assert cfg.mode == PacingMode.NORMAL
        assert cfg.custom_delay == 1.5
        assert cfg.min_chars_per_second == 50.0
        assert cfg.enable_thinking_pause is True
        assert cfg.thinking_pause_duration == 0.5

    def test_custom_values(self) -> None:
        cfg = PacingConfig(
            mode=PacingMode.FAST,
            custom_delay=2.0,
            min_chars_per_second=100.0,
            enable_thinking_pause=False,
            thinking_pause_duration=1.0,
        )
        assert cfg.mode == PacingMode.FAST
        assert cfg.custom_delay == 2.0
        assert cfg.min_chars_per_second == 100.0
        assert cfg.enable_thinking_pause is False
        assert cfg.thinking_pause_duration == 1.0

    def test_partial_override(self) -> None:
        cfg = PacingConfig(mode=PacingMode.SLOW)
        assert cfg.mode == PacingMode.SLOW
        # Other fields keep defaults
        assert cfg.custom_delay == 1.5
        assert cfg.enable_thinking_pause is True


# ===================================================================
# 3. DialoguePacer
# ===================================================================
class TestDialoguePacer:
    """DialoguePacer synchronous method tests."""

    def test_default_config(self) -> None:
        pacer = DialoguePacer()
        assert pacer.config.mode == PacingMode.NORMAL

    def test_custom_config(self) -> None:
        cfg = PacingConfig(mode=PacingMode.FAST)
        pacer = DialoguePacer(config=cfg)
        assert pacer.config.mode == PacingMode.FAST

    # --- get_delay_before_response ---

    def test_delay_before_response_with_thinking_pause(self) -> None:
        pacer = DialoguePacer(PacingConfig(enable_thinking_pause=True, thinking_pause_duration=0.5))
        assert pacer.get_delay_before_response() == 0.5

    def test_delay_before_response_without_thinking_pause(self) -> None:
        pacer = DialoguePacer(PacingConfig(enable_thinking_pause=False))
        assert pacer.get_delay_before_response() == 0.0

    def test_delay_before_response_custom_duration(self) -> None:
        pacer = DialoguePacer(PacingConfig(enable_thinking_pause=True, thinking_pause_duration=2.5))
        assert pacer.get_delay_before_response() == 2.5

    # --- get_delay_between_responses (all modes) ---

    def test_delay_between_responses_instant(self) -> None:
        pacer = DialoguePacer(PacingConfig(mode=PacingMode.INSTANT))
        assert pacer.get_delay_between_responses() == 0.0

    def test_delay_between_responses_fast(self) -> None:
        pacer = DialoguePacer(PacingConfig(mode=PacingMode.FAST))
        assert pacer.get_delay_between_responses() == 0.5

    def test_delay_between_responses_normal(self) -> None:
        pacer = DialoguePacer(PacingConfig(mode=PacingMode.NORMAL))
        assert pacer.get_delay_between_responses() == 1.5

    def test_delay_between_responses_slow(self) -> None:
        pacer = DialoguePacer(PacingConfig(mode=PacingMode.SLOW))
        assert pacer.get_delay_between_responses() == 3.0

    def test_delay_between_responses_custom(self) -> None:
        pacer = DialoguePacer(PacingConfig(mode=PacingMode.CUSTOM, custom_delay=7.0))
        assert pacer.get_delay_between_responses() == 7.0

    # --- get_character_display_duration ---

    def test_character_display_duration_normal(self) -> None:
        pacer = DialoguePacer(PacingConfig(min_chars_per_second=50.0))
        assert pacer.get_character_display_duration("Hello") == pytest.approx(0.1)

    def test_character_display_duration_empty(self) -> None:
        pacer = DialoguePacer()
        assert pacer.get_character_display_duration("") == 0.0

    def test_character_display_duration_long_text(self) -> None:
        pacer = DialoguePacer(PacingConfig(min_chars_per_second=100.0))
        text = "a" * 200
        assert pacer.get_character_display_duration(text) == pytest.approx(2.0)

    # --- set_mode ---

    def test_set_mode_changes_mode(self) -> None:
        pacer = DialoguePacer()
        pacer.set_mode(PacingMode.SLOW)
        assert pacer.config.mode == PacingMode.SLOW

    def test_set_mode_with_custom_delay(self) -> None:
        pacer = DialoguePacer()
        pacer.set_mode(PacingMode.CUSTOM, custom_delay=5.0)
        assert pacer.config.mode == PacingMode.CUSTOM
        assert pacer.config.custom_delay == 5.0

    def test_set_mode_without_custom_delay_preserves_old(self) -> None:
        pacer = DialoguePacer(PacingConfig(custom_delay=3.0))
        pacer.set_mode(PacingMode.CUSTOM)
        assert pacer.config.custom_delay == 3.0

    # --- set_thinking_pause ---

    def test_set_thinking_pause_disable(self) -> None:
        pacer = DialoguePacer()
        pacer.set_thinking_pause(False)
        assert pacer.config.enable_thinking_pause is False

    def test_set_thinking_pause_enable_with_duration(self) -> None:
        pacer = DialoguePacer(PacingConfig(enable_thinking_pause=False))
        pacer.set_thinking_pause(True, duration=1.0)
        assert pacer.config.enable_thinking_pause is True
        assert pacer.config.thinking_pause_duration == 1.0

    def test_set_thinking_pause_preserves_duration_when_none(self) -> None:
        pacer = DialoguePacer(PacingConfig(thinking_pause_duration=0.8))
        pacer.set_thinking_pause(True)
        assert pacer.config.thinking_pause_duration == 0.8


# ===================================================================
# 3b. DialoguePacer async methods
# ===================================================================
class TestDialoguePacerAsync:
    """Async method tests using real asyncio (with mocked sleep)."""

    @pytest.mark.asyncio
    async def test_wait_before_response_calls_sleep(self) -> None:
        from unittest.mock import AsyncMock

        pacer = DialoguePacer(PacingConfig(enable_thinking_pause=True, thinking_pause_duration=0.5))
        mock_sleep = AsyncMock()
        with patch("hosts.gui.dialogue_pacing.asyncio.sleep", mock_sleep):
            await pacer.wait_before_response()
            mock_sleep.assert_awaited_once_with(0.5)

    @pytest.mark.asyncio
    async def test_wait_before_response_skips_when_disabled(self) -> None:
        from unittest.mock import AsyncMock

        pacer = DialoguePacer(PacingConfig(enable_thinking_pause=False))
        mock_sleep = AsyncMock()
        with patch("hosts.gui.dialogue_pacing.asyncio.sleep", mock_sleep):
            await pacer.wait_before_response()
            mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wait_between_responses_calls_sleep(self) -> None:
        from unittest.mock import AsyncMock

        pacer = DialoguePacer(PacingConfig(mode=PacingMode.FAST))
        mock_sleep = AsyncMock()
        with patch("hosts.gui.dialogue_pacing.asyncio.sleep", mock_sleep):
            await pacer.wait_between_responses()
            mock_sleep.assert_awaited_once_with(0.5)

    @pytest.mark.asyncio
    async def test_wait_between_responses_skips_instant(self) -> None:
        from unittest.mock import AsyncMock

        pacer = DialoguePacer(PacingConfig(mode=PacingMode.INSTANT))
        mock_sleep = AsyncMock()
        with patch("hosts.gui.dialogue_pacing.asyncio.sleep", mock_sleep):
            await pacer.wait_between_responses()
            mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wait_for_display_normal_text(self) -> None:
        from unittest.mock import AsyncMock

        pacer = DialoguePacer(PacingConfig(min_chars_per_second=50.0))
        mock_sleep = AsyncMock()
        with patch("hosts.gui.dialogue_pacing.asyncio.sleep", mock_sleep):
            await pacer.wait_for_display("Hello")
            mock_sleep.assert_awaited_once_with(pytest.approx(0.1))

    @pytest.mark.asyncio
    async def test_wait_for_display_empty_text(self) -> None:
        """Empty text => duration 0 => sleep not called."""
        from unittest.mock import AsyncMock

        pacer = DialoguePacer()
        mock_sleep = AsyncMock()
        with patch("hosts.gui.dialogue_pacing.asyncio.sleep", mock_sleep):
            await pacer.wait_for_display("")
            mock_sleep.assert_not_awaited()


# ===================================================================
# 4. extract_emotes
# ===================================================================
class TestExtractEmotes:
    """Tests for emote_sfx.extract_emotes."""

    def test_single_emote(self) -> None:
        assert extract_emotes("*chuckles*") == ["chuckles"]

    def test_multiple_emotes(self) -> None:
        result = extract_emotes("*sighs* Well, that was something *laughs*")
        assert result == ["sighs", "laughs"]

    def test_no_emotes(self) -> None:
        assert extract_emotes("Just plain text with no asterisks") == []

    def test_empty_string(self) -> None:
        assert extract_emotes("") == []

    def test_nested_asterisks_are_not_matched(self) -> None:
        # *foo *bar* baz* should match 'foo *bar' because regex is non-greedy
        # Pattern [^*]+ means it won't cross asterisks
        result = extract_emotes("*foo*bar*")
        assert result == ["foo"]

    def test_emote_with_spaces(self) -> None:
        assert extract_emotes("*strikes anvil*") == ["strikes anvil"]

    def test_emote_in_sentence(self) -> None:
        result = extract_emotes("She said *grunts approvingly* and left.")
        assert result == ["grunts approvingly"]

    def test_adjacent_emotes(self) -> None:
        result = extract_emotes("*sigh**laugh*")
        assert result == ["sigh", "laugh"]

    def test_single_asterisks_no_match(self) -> None:
        # A lone * without a closing * yields nothing
        assert extract_emotes("hello * world") == []


# ===================================================================
# 5. resolve_sfx
# ===================================================================
class TestResolveSfx:
    """Tests for emote_sfx.resolve_sfx."""

    def test_unknown_emote_returns_none(self) -> None:
        assert resolve_sfx("does a backflip") is None

    def test_anvil_keyword_resolves_category(self) -> None:
        # Even if file doesn't exist, we can verify the logic by patching Path.exists
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("strikes anvil")
            assert result is not None
            assert "anvil_strike" in result.stem

    def test_hammer_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("sets hammer down")
            assert result is not None
            assert "hammer_thud" in result.stem

    def test_chuckle_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("chuckles")
            assert result is not None
            assert "chuckle" in result.stem

    def test_sigh_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("sighs deeply")
            assert result is not None
            assert "sigh" in result.stem

    def test_grunt_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("grunts")
            assert result is not None
            assert "grunt" in result.stem

    def test_scoff_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("scoffs at the idea")
            assert result is not None
            assert "scoff" in result.stem

    def test_snap_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("snaps fingers")
            assert result is not None
            assert "snap" in result.stem

    def test_whisper_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("whispers softly")
            assert result is not None
            assert "whisper" in result.stem

    def test_clears_throat_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("clears throat")
            assert result is not None
            assert "clear_throat" in result.stem

    def test_giggle_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("giggles")
            assert result is not None
            assert "giggle" in result.stem

    def test_laugh_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("laughs heartily")
            assert result is not None
            assert "laugh" in result.stem

    def test_hum_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("hums a tune")
            assert result is not None
            assert "hum" in result.stem

    def test_snicker_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("snickers")
            assert result is not None
            assert "snicker" in result.stem

    def test_knuckle_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("cracks knuckles")
            assert result is not None
            # Could be knuckle_crack
            assert "knuckle_crack" in result.stem

    def test_paper_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("slides blueprint across")
            assert result is not None
            assert "paper_slide" in result.stem

    def test_files_nails_keyword(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("files nails casually")
            assert result is not None
            assert "nail_file" in result.stem

    def test_agent_specific_path_preferred(self) -> None:
        """Per-agent override should be checked first."""
        calls = []

        def mock_exists(self_path: Path) -> bool:
            calls.append(str(self_path))
            # Return True for agent-specific path
            return "hephaestus" in str(self_path)

        with patch.object(Path, "exists", mock_exists):
            result = resolve_sfx("strikes anvil", agent_name="hephaestus")
            assert result is not None
            assert "hephaestus" in str(result)

    def test_falls_back_to_shared_when_agent_path_missing(self) -> None:
        call_count = 0

        def mock_exists(self_path: Path) -> bool:
            nonlocal call_count
            call_count += 1
            # Agent-specific doesn't exist (first call), shared does (second call)
            return "hephaestus" not in str(self_path)

        with patch.object(Path, "exists", mock_exists):
            result = resolve_sfx("strikes anvil", agent_name="hephaestus")
            assert result is not None
            assert "hephaestus" not in str(result)

    def test_no_match_returns_none_when_files_missing(self) -> None:
        """Even if keyword matches, if files don't exist, returns None."""
        with patch.object(Path, "exists", return_value=False):
            result = resolve_sfx("chuckles")
            assert result is None

    def test_case_insensitive(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("CHUCKLES")
            assert result is not None

    def test_whitespace_stripped(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            result = resolve_sfx("  chuckles  ")
            assert result is not None


# ===================================================================
# 6. play_emote_sfx
# ===================================================================
class TestPlayEmoteSfx:
    """Tests for emote_sfx.play_emote_sfx."""

    def test_text_with_emote_calls_play_sfx(self) -> None:
        audio_manager = Mock()
        with patch.object(Path, "exists", return_value=True):
            play_emote_sfx("*chuckles* hello", "hephaestus", audio_manager)
        audio_manager.play_sfx.assert_called_once()

    def test_text_without_emotes_no_call(self) -> None:
        audio_manager = Mock()
        play_emote_sfx("plain text", "hephaestus", audio_manager)
        audio_manager.play_sfx.assert_not_called()

    def test_empty_text_no_call(self) -> None:
        audio_manager = Mock()
        play_emote_sfx("", None, audio_manager)
        audio_manager.play_sfx.assert_not_called()

    def test_only_first_matching_emote_plays(self) -> None:
        """Multiple emotes but only the first matched one plays."""
        audio_manager = Mock()
        with patch.object(Path, "exists", return_value=True):
            play_emote_sfx("*sighs* and then *laughs*", None, audio_manager)
        # Should only play once (first match with existing file)
        assert audio_manager.play_sfx.call_count == 1

    def test_sfx_resolution_failure_no_crash(self) -> None:
        """When no SFX file is found for an emote, play_sfx not called."""
        audio_manager = Mock()
        with patch.object(Path, "exists", return_value=False):
            play_emote_sfx("*chuckles*", None, audio_manager)
        audio_manager.play_sfx.assert_not_called()

    def test_play_sfx_exception_handled(self) -> None:
        """If play_sfx raises, it should be caught and logged, not re-raised."""
        audio_manager = Mock()
        audio_manager.play_sfx.side_effect = RuntimeError("audio device error")
        with patch.object(Path, "exists", return_value=True):
            # Should not raise
            play_emote_sfx("*chuckles*", None, audio_manager)
        audio_manager.play_sfx.assert_called_once()

    def test_agent_name_none_still_works(self) -> None:
        audio_manager = Mock()
        with patch.object(Path, "exists", return_value=True):
            play_emote_sfx("*sighs*", None, audio_manager)
        audio_manager.play_sfx.assert_called_once()

    def test_unknown_emote_no_play(self) -> None:
        """An emote that doesn't match any keyword should not trigger play."""
        audio_manager = Mock()
        play_emote_sfx("*does a backflip*", "hephaestus", audio_manager)
        audio_manager.play_sfx.assert_not_called()


# ===================================================================
# 7. AudioMetrics
# ===================================================================
class TestAudioMetrics:
    """AudioMetrics dataclass."""

    def test_basic_init(self) -> None:
        m = AudioMetrics(peak_amplitude=0.9, rms_level=0.5, duration_ms=1000.0)
        assert m.peak_amplitude == 0.9
        assert m.rms_level == 0.5
        assert m.duration_ms == 1000.0
        assert m.sample_rate == 44100  # default

    def test_custom_sample_rate(self) -> None:
        m = AudioMetrics(peak_amplitude=0.5, rms_level=0.3, duration_ms=500.0, sample_rate=22050)
        assert m.sample_rate == 22050


# ===================================================================
# 8. AudioNormalizer
# ===================================================================
class TestAudioNormalizer:
    """AudioNormalizer static methods."""

    def test_normalize_amplitude_normal(self) -> None:
        samples = np.array([0.5, -0.5, 0.25, -0.25], dtype=np.float32)
        result = AudioNormalizer.normalize_amplitude(samples, target_level=0.85)
        # Peak of input is 0.5, scaling factor = 0.85 / 0.5 = 1.7
        expected = samples * (0.85 / 0.5)
        np.testing.assert_allclose(result, expected, rtol=1e-5)

    def test_normalize_amplitude_empty(self) -> None:
        samples = np.array([], dtype=np.float32)
        result = AudioNormalizer.normalize_amplitude(samples)
        assert len(result) == 0

    def test_normalize_amplitude_silent(self) -> None:
        """All-zero samples should be returned unchanged."""
        samples = np.zeros(100, dtype=np.float32)
        result = AudioNormalizer.normalize_amplitude(samples)
        np.testing.assert_array_equal(result, samples)

    def test_normalize_amplitude_already_at_target(self) -> None:
        samples = np.array([0.85, -0.85, 0.0], dtype=np.float32)
        result = AudioNormalizer.normalize_amplitude(samples, target_level=0.85)
        np.testing.assert_allclose(result, samples, rtol=1e-5)

    def test_normalize_amplitude_default_target(self) -> None:
        samples = np.array([1.0, -1.0], dtype=np.float32)
        result = AudioNormalizer.normalize_amplitude(samples)
        assert np.max(np.abs(result)) == pytest.approx(0.85, rel=1e-5)

    def test_normalize_amplitude_preserves_shape(self) -> None:
        samples = np.array([0.3, -0.6, 0.1], dtype=np.float32)
        result = AudioNormalizer.normalize_amplitude(samples)
        assert result.shape == samples.shape

    def test_calculate_rms_normal(self) -> None:
        samples = np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float32)
        rms = AudioNormalizer.calculate_rms(samples)
        assert rms == pytest.approx(1.0, rel=1e-5)

    def test_calculate_rms_empty(self) -> None:
        samples = np.array([], dtype=np.float32)
        assert AudioNormalizer.calculate_rms(samples) == 0.0

    def test_calculate_rms_single_value(self) -> None:
        samples = np.array([0.5], dtype=np.float32)
        assert AudioNormalizer.calculate_rms(samples) == pytest.approx(0.5, rel=1e-5)

    def test_calculate_rms_known_value(self) -> None:
        # RMS of [0.0, 1.0] = sqrt((0 + 1) / 2) = sqrt(0.5)
        samples = np.array([0.0, 1.0], dtype=np.float32)
        expected = math.sqrt(0.5)
        assert AudioNormalizer.calculate_rms(samples) == pytest.approx(expected, rel=1e-5)


# ===================================================================
# 9. AudioFadeEffect
# ===================================================================
class TestAudioFadeEffect:
    """AudioFadeEffect static methods."""

    # --- apply_fade_in ---

    def test_fade_in_normal(self) -> None:
        samples = np.ones(44100, dtype=np.float32)  # 1 second at 44100 Hz
        result = AudioFadeEffect.apply_fade_in(samples, duration_ms=100.0, sample_rate=44100)
        # First sample should be ~0 (faded), last sample untouched
        assert result[0] == pytest.approx(0.0, abs=1e-5)
        assert result[-1] == pytest.approx(1.0, abs=1e-5)
        # Midpoint of fade should be ~0.5
        fade_samples = int(100.0 * 44100 / 1000.0)
        mid = fade_samples // 2
        assert 0.3 < result[mid] < 0.7

    def test_fade_in_does_not_modify_original(self) -> None:
        samples = np.ones(1000, dtype=np.float32)
        original = samples.copy()
        AudioFadeEffect.apply_fade_in(samples, duration_ms=10.0)
        np.testing.assert_array_equal(samples, original)

    def test_fade_in_zero_duration(self) -> None:
        """Zero ms fade -> fade_samples=0 -> <=1 guard -> returns unchanged copy."""
        samples = np.ones(100, dtype=np.float32)
        result = AudioFadeEffect.apply_fade_in(samples, duration_ms=0.0)
        np.testing.assert_array_equal(result, samples)

    def test_fade_in_short_samples(self) -> None:
        """When sample count < fade_samples, fade should clamp to len(samples)."""
        samples = np.ones(10, dtype=np.float32)
        result = AudioFadeEffect.apply_fade_in(samples, duration_ms=1000.0, sample_rate=44100)
        # Fade length would be 44100 samples but clamped to 10
        assert result[0] == pytest.approx(0.0, abs=0.15)
        assert result[-1] == pytest.approx(1.0, abs=0.15)

    def test_fade_in_single_sample(self) -> None:
        """Single sample edge case: fade_samples min(X, 1) => <=1 guard."""
        samples = np.array([0.8], dtype=np.float32)
        result = AudioFadeEffect.apply_fade_in(samples, duration_ms=100.0)
        # fade_samples = min(4410, 1) = 1, but <=1 guard returns unchanged
        np.testing.assert_array_equal(result, samples)

    # --- apply_fade_out ---

    def test_fade_out_normal(self) -> None:
        samples = np.ones(44100, dtype=np.float32)
        result = AudioFadeEffect.apply_fade_out(samples, duration_ms=100.0, sample_rate=44100)
        # First sample untouched, last sample should be ~0
        assert result[0] == pytest.approx(1.0, abs=1e-5)
        assert result[-1] == pytest.approx(0.0, abs=1e-5)

    def test_fade_out_does_not_modify_original(self) -> None:
        samples = np.ones(1000, dtype=np.float32)
        original = samples.copy()
        AudioFadeEffect.apply_fade_out(samples, duration_ms=10.0)
        np.testing.assert_array_equal(samples, original)

    def test_fade_out_zero_duration(self) -> None:
        samples = np.ones(100, dtype=np.float32)
        result = AudioFadeEffect.apply_fade_out(samples, duration_ms=0.0)
        np.testing.assert_array_equal(result, samples)

    def test_fade_out_short_samples(self) -> None:
        samples = np.ones(10, dtype=np.float32)
        result = AudioFadeEffect.apply_fade_out(samples, duration_ms=1000.0, sample_rate=44100)
        assert result[0] == pytest.approx(1.0, abs=0.15)
        assert result[-1] == pytest.approx(0.0, abs=0.15)

    def test_fade_out_single_sample(self) -> None:
        samples = np.array([0.8], dtype=np.float32)
        result = AudioFadeEffect.apply_fade_out(samples, duration_ms=100.0)
        np.testing.assert_array_equal(result, samples)

    def test_fade_in_and_out_combined(self) -> None:
        """Apply both fades to verify they compose correctly."""
        samples = np.ones(44100, dtype=np.float32)
        result = AudioFadeEffect.apply_fade_in(samples, duration_ms=100.0)
        result = AudioFadeEffect.apply_fade_out(result, duration_ms=100.0)
        assert result[0] == pytest.approx(0.0, abs=1e-5)
        assert result[-1] == pytest.approx(0.0, abs=1e-5)
        # Middle should be close to 1.0
        assert result[len(result) // 2] == pytest.approx(1.0, abs=1e-5)


# ===================================================================
# 10. AudioVisualizer
# ===================================================================
class TestAudioVisualizer:
    """AudioVisualizer static methods."""

    # --- extract_waveform ---

    def test_extract_waveform_normal(self) -> None:
        samples = np.sin(np.linspace(0, 2 * np.pi, 1000)).astype(np.float32)
        result = AudioVisualizer.extract_waveform(samples, num_points=50)
        assert len(result) == 50
        assert all(0.0 <= v <= 1.0 for v in result)

    def test_extract_waveform_empty(self) -> None:
        samples = np.array([], dtype=np.float32)
        result = AudioVisualizer.extract_waveform(samples, num_points=100)
        assert result == [0.0] * 100

    def test_extract_waveform_default_points(self) -> None:
        samples = np.ones(500, dtype=np.float32)
        result = AudioVisualizer.extract_waveform(samples)
        assert len(result) == 100

    def test_extract_waveform_all_same_value(self) -> None:
        samples = np.full(200, 0.5, dtype=np.float32)
        result = AudioVisualizer.extract_waveform(samples, num_points=10)
        assert len(result) == 10
        # All values same -> after normalization, all should be 1.0
        assert all(v == pytest.approx(1.0) for v in result)

    def test_extract_waveform_single_sample(self) -> None:
        samples = np.array([0.7], dtype=np.float32)
        result = AudioVisualizer.extract_waveform(samples, num_points=5)
        assert len(result) == 5

    # --- estimate_loudness ---

    def test_estimate_loudness_normal(self) -> None:
        samples = np.array([0.5, -0.5, 0.5, -0.5], dtype=np.float32)
        loudness = AudioVisualizer.estimate_loudness(samples)
        # RMS = 0.5, dB = 20*log10(0.5) ~ -6.02
        assert loudness == pytest.approx(-6.0206, rel=1e-3)

    def test_estimate_loudness_empty(self) -> None:
        samples = np.array([], dtype=np.float32)
        loudness = AudioVisualizer.estimate_loudness(samples)
        assert loudness == float("-inf")

    def test_estimate_loudness_silent(self) -> None:
        samples = np.zeros(100, dtype=np.float32)
        loudness = AudioVisualizer.estimate_loudness(samples)
        assert loudness == float("-inf")

    def test_estimate_loudness_full_scale(self) -> None:
        samples = np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float32)
        loudness = AudioVisualizer.estimate_loudness(samples)
        # RMS = 1.0, dB = 20*log10(1.0) = 0.0
        assert loudness == pytest.approx(0.0, abs=0.01)

    def test_estimate_loudness_quiet(self) -> None:
        samples = np.array([0.01, -0.01], dtype=np.float32)
        loudness = AudioVisualizer.estimate_loudness(samples)
        # Should be a large negative number
        assert loudness < -30.0


# ===================================================================
# 11. PersonalityAudioProfile
# ===================================================================
class TestPersonalityAudioProfile:
    """PersonalityAudioProfile init and apply_profile."""

    def test_init_defaults(self) -> None:
        p = PersonalityAudioProfile("test_agent")
        assert p.name == "test_agent"
        assert p.target_rms == 0.5
        assert p.presence_boost_db == 0.0
        assert p.warmth_adjustment == 1.0

    def test_init_custom(self) -> None:
        p = PersonalityAudioProfile(
            "custom", target_rms=0.6, presence_boost_db=2.0, warmth_adjustment=1.1
        )
        assert p.name == "custom"
        assert p.target_rms == 0.6
        assert p.presence_boost_db == 2.0
        assert p.warmth_adjustment == 1.1

    def test_apply_profile_normalizes_rms(self) -> None:
        p = PersonalityAudioProfile("test", target_rms=0.5)
        # Input with RMS ~0.25
        samples = np.array([0.25, -0.25, 0.25, -0.25], dtype=np.float32)
        result = p.apply_profile(samples)
        result_rms = AudioNormalizer.calculate_rms(result)
        assert result_rms == pytest.approx(0.5, rel=1e-3)

    def test_apply_profile_silent_input(self) -> None:
        """Zero-RMS input should be returned unchanged (no div-by-zero)."""
        p = PersonalityAudioProfile("test", target_rms=0.5)
        samples = np.zeros(100, dtype=np.float32)
        result = p.apply_profile(samples)
        np.testing.assert_array_equal(result, samples)

    def test_apply_profile_preserves_shape(self) -> None:
        p = PersonalityAudioProfile("test")
        samples = np.random.randn(500).astype(np.float32) * 0.3
        result = p.apply_profile(samples)
        assert result.shape == samples.shape


# ===================================================================
# 12. AGENT_PROFILES dict
# ===================================================================
class TestAgentProfiles:
    """Verify the predefined AGENT_PROFILES dict."""

    EXPECTED_AGENTS = {"hephaestus", "metis", "kallos", "mneme", "techne", "dokimasia"}

    def test_all_six_agents_present(self) -> None:
        assert set(AGENT_PROFILES.keys()) == self.EXPECTED_AGENTS

    def test_profiles_are_personality_audio_profile_instances(self) -> None:
        for name, profile in AGENT_PROFILES.items():
            assert isinstance(profile, PersonalityAudioProfile), (
                f"{name} is not a PersonalityAudioProfile"
            )

    def test_profile_names_match_keys(self) -> None:
        for key, profile in AGENT_PROFILES.items():
            assert profile.name == key

    def test_target_rms_in_valid_range(self) -> None:
        for name, profile in AGENT_PROFILES.items():
            assert 0.0 < profile.target_rms <= 1.0, f"{name} target_rms out of range"


# ===================================================================
# 13. detect_agent
# ===================================================================
class TestDetectAgent:
    """Tests for maidens.detect_agent."""

    @pytest.mark.parametrize(
        "emoji,expected_name",
        [
            ("\U0001f525", "hephaestus"),  # fire
            ("\U0001f4d0", "metis"),  # triangular ruler
            ("\u2699\ufe0f", "techne"),  # gear with variation selector
            ("\u2699", "techne"),  # gear without variation selector
            ("\U0001f9ea", "dokimasia"),  # test tube
            ("\u2728", "kallos"),  # sparkles
            ("\U0001f4dc", "mneme"),  # scroll
        ],
    )
    def test_emoji_prefix_detection(self, emoji: str, expected_name: str) -> None:
        text = f"{emoji} Working on something"
        name, cleaned = detect_agent(text)
        assert name == expected_name
        assert cleaned == "Working on something"

    def test_no_emoji_returns_none(self) -> None:
        name, cleaned = detect_agent("Just plain text")
        assert name is None
        assert cleaned == "Just plain text"

    def test_empty_text(self) -> None:
        name, cleaned = detect_agent("")
        assert name is None
        assert cleaned == ""

    def test_emoji_with_leading_whitespace(self) -> None:
        name, cleaned = detect_agent("  \U0001f525 Forging")
        assert name == "hephaestus"
        assert cleaned == "Forging"

    def test_emoji_only(self) -> None:
        name, cleaned = detect_agent("\U0001f525")
        assert name == "hephaestus"
        assert cleaned == ""

    def test_unknown_emoji_prefix(self) -> None:
        name, cleaned = detect_agent("\U0001f600 Smiley face")
        assert name is None
        assert cleaned == "\U0001f600 Smiley face"


# ===================================================================
# 14. get_avatar_path
# ===================================================================
class TestGetAvatarPath:
    """Tests for maidens.get_avatar_path."""

    def test_nonexistent_name_returns_none(self) -> None:
        result = get_avatar_path("nonexistent_agent_xyz_123")
        assert result is None

    def test_returns_path_when_file_exists(self) -> None:
        """Mock Path.exists to simulate a found avatar."""
        with patch.object(Path, "exists", return_value=True):
            result = get_avatar_path("hephaestus")
            assert result is not None
            assert "hephaestus" in str(result)

    def test_checks_multiple_extensions(self) -> None:
        """Should check .png, .jpg, .jpeg, .webp in order."""
        checked_paths = []

        def mock_exists(self_path: Path) -> bool:
            checked_paths.append(self_path.suffix)
            return False

        with patch.object(Path, "exists", mock_exists):
            get_avatar_path("test")
        assert checked_paths == [".png", ".jpg", ".jpeg", ".webp"]

    def test_returns_first_found_extension(self) -> None:
        """Should return the first extension that exists."""

        def mock_exists(self_path: Path) -> bool:
            # Only .jpg exists
            return self_path.suffix == ".jpg"

        with patch.object(Path, "exists", mock_exists):
            result = get_avatar_path("test")
            assert result is not None
            assert result.suffix == ".jpg"


# ===================================================================
# 15. AGENTS dict structure
# ===================================================================
class TestAgentsDict:
    """Verify AGENTS dict has all required keys and structure."""

    REQUIRED_KEYS = {"title", "desc", "color", "quotes", "user_quotes"}
    EXPECTED_AGENTS = {"hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"}

    def test_all_six_agents_present(self) -> None:
        assert set(AGENTS.keys()) == self.EXPECTED_AGENTS

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_agent_has_required_keys(self, agent_name: str) -> None:
        agent = AGENTS[agent_name]
        missing = self.REQUIRED_KEYS - set(agent.keys())
        assert not missing, f"{agent_name} missing keys: {missing}"

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_agent_title_is_string(self, agent_name: str) -> None:
        assert isinstance(AGENTS[agent_name]["title"], str)

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_agent_desc_is_string(self, agent_name: str) -> None:
        assert isinstance(AGENTS[agent_name]["desc"], str)

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_agent_color_is_tuple_of_three(self, agent_name: str) -> None:
        color = AGENTS[agent_name]["color"]
        assert isinstance(color, tuple)
        assert len(color) == 3
        assert all(isinstance(c, int) for c in color)

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_agent_quotes_is_nonempty_list(self, agent_name: str) -> None:
        quotes = AGENTS[agent_name]["quotes"]
        assert isinstance(quotes, list)
        assert len(quotes) > 0

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_agent_user_quotes_is_nonempty_list(self, agent_name: str) -> None:
        user_quotes = AGENTS[agent_name]["user_quotes"]
        assert isinstance(user_quotes, list)
        assert len(user_quotes) > 0


# ===================================================================
# 16. HANDOFF_LINES dict
# ===================================================================
class TestHandoffLines:
    """Verify HANDOFF_LINES structure."""

    def test_keys_are_tuples(self) -> None:
        for key in HANDOFF_LINES:
            assert isinstance(key, tuple), f"Key {key} is not a tuple"
            assert len(key) == 2, f"Key {key} does not have exactly 2 elements"

    def test_values_are_nonempty_lists(self) -> None:
        for key, lines in HANDOFF_LINES.items():
            assert isinstance(lines, list), f"Value for {key} is not a list"
            assert len(lines) > 0, f"Value for {key} is empty"

    def test_all_values_are_strings(self) -> None:
        for key, lines in HANDOFF_LINES.items():
            for line in lines:
                assert isinstance(line, str), f"Non-string line in {key}: {line!r}"

    def test_hephaestus_to_metis_exists(self) -> None:
        assert ("hephaestus", "metis") in HANDOFF_LINES

    def test_hephaestus_to_techne_exists(self) -> None:
        assert ("hephaestus", "techne") in HANDOFF_LINES

    def test_hephaestus_to_dokimasia_exists(self) -> None:
        assert ("hephaestus", "dokimasia") in HANDOFF_LINES

    def test_hephaestus_to_kallos_exists(self) -> None:
        assert ("hephaestus", "kallos") in HANDOFF_LINES

    def test_hephaestus_to_mneme_exists(self) -> None:
        assert ("hephaestus", "mneme") in HANDOFF_LINES

    def test_tuple_elements_are_strings(self) -> None:
        for src, dst in HANDOFF_LINES:
            assert isinstance(src, str)
            assert isinstance(dst, str)


# ===================================================================
# 17. VICTORY_LINES dict
# ===================================================================
class TestVictoryLines:
    """Verify VICTORY_LINES structure."""

    EXPECTED_AGENTS = {"hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"}

    def test_all_agents_have_victory_lines(self) -> None:
        assert set(VICTORY_LINES.keys()) == self.EXPECTED_AGENTS

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_victory_lines_are_nonempty_lists(self, agent_name: str) -> None:
        lines = VICTORY_LINES[agent_name]
        assert isinstance(lines, list)
        assert len(lines) > 0

    @pytest.mark.parametrize(
        "agent_name", ["hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"]
    )
    def test_victory_lines_are_strings(self, agent_name: str) -> None:
        for line in VICTORY_LINES[agent_name]:
            assert isinstance(line, str)
