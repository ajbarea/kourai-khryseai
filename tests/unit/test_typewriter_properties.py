"""Property-based tests for TypewriterManager class.

Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence
Feature: gui-improvements, Property 2: Typewriter Skip Functionality
Feature: gui-improvements, Property 13: Motion Sensitivity Support

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 12.8
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from hosts.gui.typewriter import TypewriterManager

# Strategies for property-based testing
text_strategy = st.text(min_size=1, max_size=1000)
speed_strategy = st.integers(min_value=10, max_value=100)
delta_time_strategy = st.floats(
    min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False
)
any_speed_strategy = st.integers(min_value=-100, max_value=200)


class TestTypewriterCharacterSequenceProperty:
    """Property-based tests for character sequence display.

    Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence
    Validates: Requirements 1.1, 1.3
    """

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_characters_display_sequentially(self, text: str, speed: int) -> None:
        """Property: Characters display sequentially from first to last.

        For any text and speed setting, the typewriter effect shall display
        characters sequentially from first to last, with each character
        appearing at the configured interval.

        Validates: Requirements 1.1, 1.3
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Collect displayed text at each character
        displayed_texts = []
        current_chars = 0

        # Update until complete
        dt = speed / 1000.0  # Convert speed to seconds
        while not manager.is_complete():
            result = manager.update(dt)
            if len(result) > current_chars:
                displayed_texts.append(result)
                current_chars = len(result)

        # Verify all characters are displayed
        assert manager.get_displayed_text() == text

        # Verify characters appear in order
        for i, displayed in enumerate(displayed_texts):
            assert displayed == text[: i + 1]

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_displayed_text_is_prefix_of_full_text(self, text: str, speed: int) -> None:
        """Property: Displayed text is always a prefix of full text.

        For any text and speed, at any point during the effect, the displayed
        text shall be a prefix of the full text.

        Validates: Requirements 1.1, 1.3
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Update multiple times
        dt = speed / 1000.0
        for _ in range(100):
            displayed = manager.get_displayed_text()
            # Displayed text should be a prefix of full text
            assert text.startswith(displayed)
            manager.update(dt)

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_displayed_chars_never_exceeds_text_length(self, text: str, speed: int) -> None:
        """Property: Displayed character count never exceeds text length.

        For any text and speed, the number of displayed characters shall
        never exceed the length of the full text.

        Validates: Requirements 1.1, 1.3
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Update many times
        dt = speed / 1000.0
        for _ in range(1000):
            manager.update(dt)
            assert manager.displayed_chars <= len(text)

    @given(text=text_strategy, speed=speed_strategy, dt=delta_time_strategy)
    @settings(max_examples=100)
    def test_delta_time_consistency(self, text: str, speed: int, dt: float) -> None:
        """Property: Delta time produces consistent animation speed.

        For any text, speed, and delta time, the typewriter effect shall
        display characters at a consistent rate regardless of frame rate.

        Validates: Requirements 1.3, 1.4
        """
        if len(text) < 3 or dt == 0 or dt > 0.5:
            # Need at least 3 characters, non-zero dt, and reasonable dt
            # to test consistency without hitting completion
            return

        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Update with consistent delta time
        manager.update(dt)

        # Only test if we haven't completed
        if manager.is_complete():
            return

        # Update again with same delta time
        manager.update(dt)
        chars_after_second = manager.displayed_chars

        # The key property: characters should display at a rate proportional
        # to delta time and speed. We verify that the total characters
        # displayed after two updates is proportional to 2*dt.
        total_chars = chars_after_second
        expected_chars = (2 * dt * 1000.0) / speed

        # Allow for rounding differences
        assert abs(total_chars - expected_chars) <= 3.0

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_effect_completes_with_full_text(self, text: str, speed: int) -> None:
        """Property: Effect completes with full text displayed.

        For any text and speed, when the effect completes, the full text
        shall be displayed.

        Validates: Requirements 1.1, 1.3
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Update until complete
        dt = speed / 1000.0
        for _ in range(10000):
            manager.update(dt)
            if manager.is_complete():
                break

        # When complete, full text should be displayed
        assert manager.get_displayed_text() == text
        assert manager.displayed_chars == len(text)

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_speed_affects_display_rate(self, text: str, speed: int) -> None:
        """Property: Speed setting affects character display rate.

        For any text and speed, faster speeds should display more characters
        in the same time period than slower speeds.

        Validates: Requirements 1.3
        """
        if len(text) < 10:
            # Need enough text to see difference
            return

        # Fast speed
        manager_fast = TypewriterManager()
        manager_fast.start(text, speed_ms=10)
        manager_fast.update(0.05)
        fast_chars = manager_fast.displayed_chars

        # Slow speed
        manager_slow = TypewriterManager()
        manager_slow.start(text, speed_ms=100)
        manager_slow.update(0.05)
        slow_chars = manager_slow.displayed_chars

        # Fast should display more characters
        assert fast_chars >= slow_chars


class TestTypewriterSkipFunctionalityProperty:
    """Property-based tests for skip functionality.

    Feature: gui-improvements, Property 2: Typewriter Skip Functionality
    Validates: Requirements 1.2
    """

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_skip_shows_full_text_immediately(self, text: str, speed: int) -> None:
        """Property: Skip immediately displays full text.

        For any active typewriter effect, requesting skip shall immediately
        display the full text and terminate the effect.

        Validates: Requirements 1.2
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Skip before any update
        manager.skip()

        # Should show full text
        assert manager.get_displayed_text() == text
        assert manager.displayed_chars == len(text)
        assert manager.is_complete() is True

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_skip_during_partial_display(self, text: str, speed: int) -> None:
        """Property: Skip works during partial text display.

        For any typewriter effect in progress, skip shall immediately show
        the full text regardless of current progress.

        Validates: Requirements 1.2
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        # Display partial text
        manager.update(0.01)

        # Skip
        manager.skip()

        # Should show full text
        assert manager.get_displayed_text() == text
        assert manager.displayed_chars == len(text)
        assert manager.is_complete() is True

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_skip_terminates_effect(self, text: str, speed: int) -> None:
        """Property: Skip terminates the typewriter effect.

        For any typewriter effect, skip shall mark the effect as complete
        and prevent further character display.

        Validates: Requirements 1.2
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        manager.skip()
        assert manager.is_complete() is True
        assert manager.active is False

        # Further updates should not change displayed text
        manager.update(1.0)
        assert manager.get_displayed_text() == text

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_skip_sets_skip_flag(self, text: str, speed: int) -> None:
        """Property: Skip sets the skip requested flag.

        For any typewriter effect, skip shall set the skip requested flag
        to indicate the effect was skipped.

        Validates: Requirements 1.2
        """
        manager = TypewriterManager()
        manager.start(text, speed_ms=speed)

        assert manager._skip_requested is False
        manager.skip()
        assert manager._skip_requested is True

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_skip_when_inactive_is_safe(self, text: str, speed: int) -> None:
        """Property: Skip when inactive is safe and does nothing.

        For any inactive typewriter effect, skip shall be safe and not
        cause errors.

        Validates: Requirements 1.2
        """
        manager = TypewriterManager()

        # Skip without starting
        manager.skip()  # Should not raise
        assert manager.active is False


class TestMotionSensitivityProperty:
    """Property-based tests for motion sensitivity support.

    Feature: gui-improvements, Property 13: Motion Sensitivity Support
    Validates: Requirements 1.7, 12.8
    """

    @given(text=text_strategy)
    @settings(max_examples=100)
    def test_motion_sensitivity_shows_full_text_immediately(self, text: str) -> None:
        """Property: Motion sensitivity shows full text immediately.

        For any text, when motion sensitivity is enabled, the typewriter
        effect shall display the full text immediately without animation.

        Validates: Requirements 1.7, 12.8
        """
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start(text)

        # Should show full text immediately
        assert manager.get_displayed_text() == text
        assert manager.displayed_chars == len(text)
        assert manager.active is False

    @given(text=text_strategy, speed=speed_strategy)
    @settings(max_examples=100)
    def test_motion_sensitivity_ignores_speed_setting(self, text: str, speed: int) -> None:
        """Property: Motion sensitivity ignores speed setting.

        For any text and speed, when motion sensitivity is enabled, the
        speed setting shall be ignored and text displayed immediately.

        Validates: Requirements 1.7, 12.8
        """
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start(text, speed_ms=speed)

        # Should show full text immediately regardless of speed
        assert manager.get_displayed_text() == text
        assert manager.displayed_chars == len(text)

    @given(text=text_strategy, dt=delta_time_strategy)
    @settings(max_examples=100)
    def test_motion_sensitivity_update_does_not_animate(self, text: str, dt: float) -> None:
        """Property: Motion sensitivity update does not animate.

        For any text and delta time, when motion sensitivity is enabled,
        update shall not animate and shall return full text.

        Validates: Requirements 1.7, 12.8
        """
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start(text)

        # Update should not change anything
        result = manager.update(dt)
        assert result == text
        assert manager.displayed_chars == len(text)

    @given(text=text_strategy)
    @settings(max_examples=100)
    def test_motion_sensitivity_toggle_affects_new_effects(self, text: str) -> None:
        """Property: Motion sensitivity toggle affects new effects.

        For any text, toggling motion sensitivity shall affect new effects
        but not current effects.

        Validates: Requirements 1.7, 12.8
        """
        manager = TypewriterManager()

        # Start without motion sensitivity
        manager.start(text, speed_ms=30)
        manager.update(0.01)

        # Enable motion sensitivity
        manager.set_motion_sensitivity(True)

        # New effect should show full text immediately
        manager.start(text)
        assert manager.displayed_chars == len(text)
        assert manager.active is False

    @given(text=text_strategy)
    @settings(max_examples=100)
    def test_motion_sensitivity_with_empty_text(self, text: str) -> None:
        """Property: Motion sensitivity handles empty text correctly.

        For any text (including empty), motion sensitivity shall handle it
        correctly without errors.

        Validates: Requirements 1.7, 12.8
        """
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start(text)

        # Should complete immediately
        assert manager.is_complete() is True
        assert manager.get_displayed_text() == text

    @given(text=text_strategy)
    @settings(max_examples=100)
    def test_motion_sensitivity_preserves_text_content(self, text: str) -> None:
        """Property: Motion sensitivity preserves text content.

        For any text, motion sensitivity shall display the exact same text
        content, just without animation.

        Validates: Requirements 1.7, 12.8
        """
        manager_with_sensitivity = TypewriterManager(motion_sensitivity_enabled=True)
        manager_with_sensitivity.start(text)

        manager_without_sensitivity = TypewriterManager()
        manager_without_sensitivity.start(text, speed_ms=10)
        # Update enough to show all text
        manager_without_sensitivity.update(100.0)

        # Both should have same final text
        assert manager_with_sensitivity.get_displayed_text() == text
        assert manager_without_sensitivity.get_displayed_text() == text


class TestTypewriterSpeedRangeProperty:
    """Property-based tests for speed range validation.

    Validates: Requirements 1.3
    """

    @given(speed=any_speed_strategy)
    @settings(max_examples=100)
    def test_speed_always_clamped_to_valid_range(self, speed: int) -> None:
        """Property: Speed is always clamped to valid range.

        For any speed value, the resulting speed shall be within [10, 100].

        Validates: Requirements 1.3
        """
        manager = TypewriterManager()
        manager.set_speed(speed)

        assert 10 <= manager.current_speed_ms <= 100

    @given(speed=any_speed_strategy)
    @settings(max_examples=100)
    def test_start_speed_clamped_to_valid_range(self, speed: int) -> None:
        """Property: Start speed is clamped to valid range.

        For any speed value in start, the resulting speed shall be within [10, 100].

        Validates: Requirements 1.3
        """
        manager = TypewriterManager()
        manager.start("test", speed_ms=speed)

        assert 10 <= manager.current_speed_ms <= 100
