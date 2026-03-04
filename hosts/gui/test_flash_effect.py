"""Unit tests for FlashEffect class."""

from flash_effect import FlashEffect


class TestFlashEffectBasic:
    """Test basic FlashEffect initialization and state."""

    def test_init_default_values(self) -> None:
        """Test default initialization values."""
        effect = FlashEffect()
        assert effect.min_duration_ms == 200
        assert effect.max_duration_ms == 500
        assert effect.current_duration_ms == 350
        assert effect.active is False

    def test_init_custom_duration_range(self) -> None:
        """Test initialization with custom duration range."""
        effect = FlashEffect(min_duration_ms=100, max_duration_ms=600)
        assert effect.min_duration_ms == 100
        assert effect.max_duration_ms == 600
        assert effect.current_duration_ms == 350

    def test_trigger_basic(self) -> None:
        """Test basic trigger functionality."""
        effect = FlashEffect()
        effect.trigger()
        assert effect.active is True

    def test_trigger_with_custom_duration(self) -> None:
        """Test trigger with custom duration."""
        effect = FlashEffect()
        effect.trigger(duration_ms=300)
        assert effect.active is True
        assert effect.current_duration_ms == 300

    def test_trigger_clamps_duration_to_minimum(self) -> None:
        """Test trigger clamps duration to minimum."""
        effect = FlashEffect()
        effect.trigger(duration_ms=100)
        assert effect.current_duration_ms == 200  # Clamped to min

    def test_trigger_clamps_duration_to_maximum(self) -> None:
        """Test trigger clamps duration to maximum."""
        effect = FlashEffect()
        effect.trigger(duration_ms=600)
        assert effect.current_duration_ms == 500  # Clamped to max

    def test_is_complete_initially_true(self) -> None:
        """Test is_complete returns True initially."""
        effect = FlashEffect()
        assert effect.is_complete() is True

    def test_is_complete_after_trigger(self) -> None:
        """Test is_complete returns False after trigger."""
        effect = FlashEffect()
        effect.trigger()
        assert effect.is_complete() is False

    def test_reset(self) -> None:
        """Test reset functionality."""
        effect = FlashEffect()
        effect.trigger()
        assert effect.active is True
        effect.reset()
        assert effect.active is False
        assert effect._timer == 0.0


class TestFlashEffectAlphaFade:
    """Test alpha fade animation."""

    def test_update_returns_tuple(self) -> None:
        """Test update returns (active, alpha) tuple."""
        effect = FlashEffect()
        effect.trigger()
        result = effect.update(0.016)
        assert isinstance(result, tuple)
        assert len(result) == 2
        active, alpha = result
        assert isinstance(active, bool)
        assert isinstance(alpha, int)

    def test_update_starts_with_high_alpha(self) -> None:
        """Test update starts with high alpha value."""
        effect = FlashEffect()
        effect.trigger()
        active, alpha = effect.update(0.001)  # Very small dt
        assert alpha > 100  # Should be close to start_alpha (150)

    def test_update_fades_to_zero(self) -> None:
        """Test update fades alpha to zero."""
        effect = FlashEffect()
        effect.trigger(duration_ms=100)
        # Update multiple times to complete the effect
        for _ in range(10):
            active, alpha = effect.update(0.020)  # 20ms per update
        assert alpha == 0
        assert active is False

    def test_update_alpha_decreases_over_time(self) -> None:
        """Test alpha decreases over time."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        active1, alpha1 = effect.update(0.050)  # 50ms
        active2, alpha2 = effect.update(0.050)  # Another 50ms
        assert alpha2 < alpha1

    def test_update_with_zero_delta_time(self) -> None:
        """Test update with zero delta time."""
        effect = FlashEffect()
        effect.trigger()
        active, alpha = effect.update(0.0)
        assert active is True
        assert alpha == 150  # Should be at start_alpha

    def test_update_with_large_delta_time(self) -> None:
        """Test update with large delta time completes effect."""
        effect = FlashEffect()
        effect.trigger(duration_ms=100)
        active, alpha = effect.update(1.0)  # 1 second
        assert active is False
        assert alpha == 0

    def test_update_does_not_exceed_end_alpha(self) -> None:
        """Test alpha does not go below end_alpha."""
        effect = FlashEffect()
        effect.trigger(duration_ms=100)
        # Update multiple times beyond completion
        for _ in range(20):
            active, alpha = effect.update(0.050)
        assert alpha == 0
        assert alpha >= 0

    def test_update_does_not_exceed_start_alpha(self) -> None:
        """Test alpha does not exceed start_alpha."""
        effect = FlashEffect()
        effect.trigger()
        active, alpha = effect.update(0.001)
        assert alpha <= 150

    def test_update_returns_correct_active_state(self) -> None:
        """Test update returns correct active state."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        # Before completion
        active, _ = effect.update(0.050)
        assert active is True
        # After completion
        active, _ = effect.update(0.151)
        assert active is False


class TestFlashEffectDuration:
    """Test duration handling."""

    def test_duration_200ms(self) -> None:
        """Test 200ms duration."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        assert effect.current_duration_ms == 200

    def test_duration_350ms_default(self) -> None:
        """Test 350ms default duration."""
        effect = FlashEffect()
        effect.trigger()
        assert effect.current_duration_ms == 350

    def test_duration_500ms(self) -> None:
        """Test 500ms duration."""
        effect = FlashEffect()
        effect.trigger(duration_ms=500)
        assert effect.current_duration_ms == 500

    def test_duration_affects_fade_speed(self) -> None:
        """Test duration affects fade speed."""
        effect1 = FlashEffect()
        effect1.trigger(duration_ms=200)
        _, alpha1 = effect1.update(0.050)

        effect2 = FlashEffect()
        effect2.trigger(duration_ms=500)
        _, alpha2 = effect2.update(0.050)

        # Shorter duration should fade faster
        assert alpha1 < alpha2

    def test_duration_range_validation(self) -> None:
        """Test duration is within valid range."""
        effect = FlashEffect()
        for duration in [200, 250, 300, 350, 400, 450, 500]:
            effect.trigger(duration_ms=duration)
            assert effect.current_duration_ms == duration


class TestFlashEffectEdgeCases:
    """Test edge cases and error conditions."""

    def test_update_when_not_active(self) -> None:
        """Test update when effect is not active."""
        effect = FlashEffect()
        active, alpha = effect.update(0.016)
        assert active is False
        assert alpha == 0

    def test_multiple_triggers_in_sequence(self) -> None:
        """Test multiple triggers in sequence."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        assert effect.active is True
        effect.trigger(duration_ms=300)
        assert effect.active is True
        assert effect.current_duration_ms == 300
        assert effect._timer == 0.0

    def test_trigger_resets_timer(self) -> None:
        """Test trigger resets timer."""
        effect = FlashEffect()
        effect.trigger()
        effect.update(0.050)
        assert effect._timer > 0.0
        effect.trigger()
        assert effect._timer == 0.0

    def test_very_short_duration(self) -> None:
        """Test very short duration (at minimum)."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        active, alpha = effect.update(0.200)
        assert active is False
        assert alpha == 0

    def test_very_long_duration(self) -> None:
        """Test very long duration (at maximum)."""
        effect = FlashEffect()
        effect.trigger(duration_ms=500)
        active, alpha = effect.update(0.100)
        assert active is True
        assert alpha > 0

    def test_alpha_interpolation_midpoint(self) -> None:
        """Test alpha interpolation at midpoint."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        # Update to halfway through effect
        effect.update(0.100)  # 100ms of 200ms
        active, alpha = effect.update(0.0)  # No additional time
        # Alpha should be approximately halfway between 150 and 0
        assert 70 < alpha < 80  # Approximately 75

    def test_reset_clears_state(self) -> None:
        """Test reset clears all state."""
        effect = FlashEffect()
        effect.trigger()
        effect.update(0.050)
        effect.reset()
        assert effect.active is False
        assert effect._timer == 0.0
        active, alpha = effect.update(0.016)
        assert active is False
        assert alpha == 0

    def test_negative_duration_clamped(self) -> None:
        """Test negative duration is clamped to minimum."""
        effect = FlashEffect()
        effect.trigger(duration_ms=-100)
        assert effect.current_duration_ms == 200

    def test_zero_duration_clamped(self) -> None:
        """Test zero duration is clamped to minimum."""
        effect = FlashEffect()
        effect.trigger(duration_ms=0)
        assert effect.current_duration_ms == 200

    def test_very_large_duration_clamped(self) -> None:
        """Test very large duration is clamped to maximum."""
        effect = FlashEffect()
        effect.trigger(duration_ms=10000)
        assert effect.current_duration_ms == 500


class TestFlashEffectConsistency:
    """Test consistency and determinism."""

    def test_same_duration_same_fade_curve(self) -> None:
        """Test same duration produces same fade curve."""
        effect1 = FlashEffect()
        effect1.trigger(duration_ms=300)
        _, alpha1 = effect1.update(0.050)

        effect2 = FlashEffect()
        effect2.trigger(duration_ms=300)
        _, alpha2 = effect2.update(0.050)

        assert alpha1 == alpha2

    def test_alpha_monotonically_decreases(self) -> None:
        """Test alpha monotonically decreases."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        prev_alpha = 150
        for _ in range(20):
            _, alpha = effect.update(0.010)
            assert alpha <= prev_alpha
            prev_alpha = alpha

    def test_effect_completes_exactly_at_duration(self) -> None:
        """Test effect completes at specified duration."""
        effect = FlashEffect()
        effect.trigger(duration_ms=200)
        # Update just before completion
        active, _ = effect.update(0.199)
        assert active is True
        # Update past completion
        active, alpha = effect.update(0.001)
        assert active is False
        assert alpha == 0
