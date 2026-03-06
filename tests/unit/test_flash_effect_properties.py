"""Property-based tests for FlashEffect using Hypothesis."""

from hypothesis import given, settings, strategies as st

from hosts.gui.flash_effect import FlashEffect


# Feature: gui-improvements, Property 5: Flash Effect Duration
class TestFlashEffectDurationProperty:
    """Property-based tests for flash effect duration."""

    @given(
        duration_ms=st.integers(min_value=200, max_value=500),
        dt=st.floats(min_value=0.001, max_value=0.1),
    )
    @settings(max_examples=100)
    def test_flash_effect_duration_is_within_range(self, duration_ms, dt):
        """Property: For any agent handoff, the flash effect shall last between 200ms and 500ms
        as configured."""
        effect = FlashEffect(min_duration_ms=200, max_duration_ms=500)
        effect.trigger(duration_ms)

        elapsed_time = 0.0
        while effect.active:
            active, alpha = effect.update(dt)
            elapsed_time += dt * 1000.0

            if elapsed_time < duration_ms:
                assert alpha <= 150

        assert elapsed_time >= duration_ms
        assert effect.is_complete()
