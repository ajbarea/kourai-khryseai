"""Unit tests for TypewriterManager class.

Tests character-by-character display, skip functionality, speed settings,
pause/resume, and motion sensitivity support.
"""

from __future__ import annotations

from .typewriter import TypewriterManager


class TestTypewriterManagerBasic:
    """Basic TypewriterManager functionality tests."""

    def test_init_default_values(self) -> None:
        """Test that TypewriterManager initializes with correct defaults."""
        manager = TypewriterManager()
        assert manager.min_speed_ms == 10
        assert manager.max_speed_ms == 100
        assert manager.current_speed_ms == 30
        assert manager.active is False
        assert manager.paused is False
        assert manager.current_text == ""
        assert manager.displayed_chars == 0
        assert manager.motion_sensitivity_enabled is False

    def test_init_custom_speed_range(self) -> None:
        """Test initialization with custom speed range."""
        manager = TypewriterManager(min_speed_ms=5, max_speed_ms=200)
        assert manager.min_speed_ms == 5
        assert manager.max_speed_ms == 200

    def test_init_motion_sensitivity_enabled(self) -> None:
        """Test initialization with motion sensitivity enabled."""
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        assert manager.motion_sensitivity_enabled is True

    def test_start_basic(self) -> None:
        """Test starting typewriter effect."""
        manager = TypewriterManager()
        manager.start("Hello")
        assert manager.active is True
        assert manager.current_text == "Hello"
        assert manager.displayed_chars == 0
        assert manager.paused is False

    def test_start_with_custom_speed(self) -> None:
        """Test starting with custom speed."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=50)
        assert manager.current_speed_ms == 50

    def test_start_clamps_speed_to_minimum(self) -> None:
        """Test that start clamps speed to minimum."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=5)
        assert manager.current_speed_ms == 10  # Clamped to min

    def test_start_clamps_speed_to_maximum(self) -> None:
        """Test that start clamps speed to maximum."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=200)
        assert manager.current_speed_ms == 100  # Clamped to max

    def test_start_resets_state(self) -> None:
        """Test that start resets previous state."""
        manager = TypewriterManager()
        manager.start("First")
        manager.update(0.1)  # Advance timer

        # Start new text
        manager.start("Second")
        assert manager.current_text == "Second"
        assert manager.displayed_chars == 0
        assert manager._timer == 0.0

    def test_is_complete_initially_false(self) -> None:
        """Test that is_complete returns False initially."""
        manager = TypewriterManager()
        assert manager.is_complete() is True  # Not active

    def test_is_complete_after_start(self) -> None:
        """Test that is_complete returns False after start."""
        manager = TypewriterManager()
        manager.start("Hello")
        assert manager.is_complete() is False

    def test_get_displayed_text_empty(self) -> None:
        """Test get_displayed_text with no characters displayed."""
        manager = TypewriterManager()
        manager.start("Hello")
        assert manager.get_displayed_text() == ""

    def test_reset(self) -> None:
        """Test reset functionality."""
        manager = TypewriterManager()
        manager.start("Hello")
        manager.update(0.1)

        manager.reset()
        assert manager.active is False
        assert manager.paused is False
        assert manager.current_text == ""
        assert manager.displayed_chars == 0
        assert manager._timer == 0.0


class TestTypewriterCharacterDisplay:
    """Tests for character-by-character display."""

    def test_update_displays_first_character(self) -> None:
        """Test that update displays first character after speed time."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        # Update with 30ms (one character)
        result = manager.update(0.03)
        assert result == "H"
        assert manager.displayed_chars == 1

    def test_update_displays_multiple_characters(self) -> None:
        """Test that update displays multiple characters."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        # Update with 90ms (three characters)
        result = manager.update(0.09)
        assert result == "Hel"
        assert manager.displayed_chars == 3

    def test_update_accumulates_delta_time(self) -> None:
        """Test that delta time accumulates correctly."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        # First update: 20ms (not enough for one character)
        result1 = manager.update(0.02)
        assert result1 == ""
        assert manager.displayed_chars == 0

        # Second update: 20ms more (total 40ms, enough for one character)
        result2 = manager.update(0.02)
        assert result2 == "H"
        assert manager.displayed_chars == 1

    def test_update_does_not_exceed_text_length(self) -> None:
        """Test that displayed characters don't exceed text length."""
        manager = TypewriterManager()
        manager.start("Hi", speed_ms=30)

        # Update with 300ms (would be 10 characters, but text is only 2)
        result = manager.update(0.3)
        assert result == "Hi"
        assert manager.displayed_chars == 2

    def test_update_marks_complete_when_done(self) -> None:
        """Test that update marks effect as complete when all text shown."""
        manager = TypewriterManager()
        manager.start("Hi", speed_ms=30)

        # Update with enough time to show all characters
        manager.update(0.1)
        assert manager.is_complete() is True
        assert manager.active is False

    def test_update_returns_correct_text(self) -> None:
        """Test that update returns the correct displayed text."""
        manager = TypewriterManager()
        manager.start("Hello World", speed_ms=30)

        # Update to show 5 characters
        result = manager.update(0.15)
        assert result == "Hello"

    def test_update_with_empty_text(self) -> None:
        """Test update with empty text."""
        manager = TypewriterManager()
        manager.start("", speed_ms=30)

        result = manager.update(0.1)
        assert result == ""
        assert manager.is_complete() is True

    def test_update_with_single_character(self) -> None:
        """Test update with single character text."""
        manager = TypewriterManager()
        manager.start("A", speed_ms=30)

        result = manager.update(0.03)
        assert result == "A"
        assert manager.is_complete() is True

    def test_update_with_special_characters(self) -> None:
        """Test update with special characters."""
        manager = TypewriterManager()
        manager.start("Hello! @#$%", speed_ms=30)

        result = manager.update(0.3)
        assert "Hello!" in result
        assert "@" in result

    def test_update_with_unicode_characters(self) -> None:
        """Test update with unicode characters."""
        manager = TypewriterManager()
        manager.start("こんにちは", speed_ms=30)

        result = manager.update(0.09)
        assert len(result) == 3
        assert result == "こんに"  # First 3 chars


class TestTypewriterSkip:
    """Tests for skip functionality."""

    def test_skip_shows_full_text(self) -> None:
        """Test that skip shows full text immediately."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        manager.skip()
        assert manager.get_displayed_text() == "Hello"
        assert manager.displayed_chars == 5

    def test_skip_marks_complete(self) -> None:
        """Test that skip marks effect as complete."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        manager.skip()
        assert manager.is_complete() is True
        assert manager.active is False

    def test_skip_when_not_active(self) -> None:
        """Test skip when effect is not active."""
        manager = TypewriterManager()
        manager.skip()  # Should not raise error
        assert manager.active is False

    def test_skip_during_partial_display(self) -> None:
        """Test skip during partial text display."""
        manager = TypewriterManager()
        manager.start("Hello World", speed_ms=30)

        # Display partial text
        manager.update(0.06)
        assert manager.displayed_chars == 2

        # Skip to full text
        manager.skip()
        assert manager.get_displayed_text() == "Hello World"
        assert manager.displayed_chars == 11

    def test_skip_sets_skip_requested_flag(self) -> None:
        """Test that skip sets the skip requested flag."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        manager.skip()
        assert manager._skip_requested is True


class TestTypewriterPauseResume:
    """Tests for pause/resume functionality."""

    def test_pause_stops_progress(self) -> None:
        """Test that pause stops character display progress."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        # Display some characters
        manager.update(0.06)
        assert manager.displayed_chars == 2

        # Pause
        manager.pause()
        assert manager.paused is True

        # Update should not advance
        manager.update(0.1)
        assert manager.displayed_chars == 2

    def test_resume_continues_progress(self) -> None:
        """Test that resume continues character display."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        # Display some characters
        manager.update(0.06)
        assert manager.displayed_chars == 2

        # Pause
        manager.pause()
        manager.update(0.1)
        assert manager.displayed_chars == 2

        # Resume
        manager.resume()
        manager.update(0.06)
        assert manager.displayed_chars > 2

    def test_pause_when_not_active(self) -> None:
        """Test pause when effect is not active."""
        manager = TypewriterManager()
        manager.pause()  # Should not raise error
        assert manager.paused is False

    def test_resume_when_not_paused(self) -> None:
        """Test resume when effect is not paused."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)
        manager.resume()  # Should not raise error
        assert manager.paused is False

    def test_pause_resume_cycle(self) -> None:
        """Test multiple pause/resume cycles."""
        manager = TypewriterManager()
        manager.start("Hello World", speed_ms=30)

        # First cycle
        manager.update(0.06)
        chars_at_first = manager.displayed_chars
        manager.pause()
        manager.update(0.1)
        assert manager.displayed_chars == chars_at_first

        manager.resume()
        manager.update(0.06)
        assert manager.displayed_chars > chars_at_first

        # Second cycle
        chars_at_second = manager.displayed_chars
        manager.pause()
        manager.update(0.1)
        assert manager.displayed_chars == chars_at_second

        manager.resume()
        manager.update(0.06)
        assert manager.displayed_chars > chars_at_second

    def test_update_returns_same_text_when_paused(self) -> None:
        """Test that update returns same text when paused."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        manager.update(0.06)
        result_before = manager.get_displayed_text()

        manager.pause()
        result_after = manager.update(0.1)

        assert result_after == result_before


class TestTypewriterSpeedSettings:
    """Tests for speed settings."""

    def test_set_speed_valid_value(self) -> None:
        """Test setting valid speed."""
        manager = TypewriterManager()
        manager.set_speed(50)
        assert manager.current_speed_ms == 50

    def test_set_speed_clamps_to_minimum(self) -> None:
        """Test that set_speed clamps to minimum."""
        manager = TypewriterManager()
        manager.set_speed(5)
        assert manager.current_speed_ms == 10

    def test_set_speed_clamps_to_maximum(self) -> None:
        """Test that set_speed clamps to maximum."""
        manager = TypewriterManager()
        manager.set_speed(200)
        assert manager.current_speed_ms == 100

    def test_set_speed_affects_new_effects(self) -> None:
        """Test that set_speed affects new effects."""
        manager = TypewriterManager()
        manager.set_speed(50)
        manager.start("Hello")

        assert manager.current_speed_ms == 50

    def test_speed_range_10_to_100(self) -> None:
        """Test that speed range is 10ms to 100ms."""
        manager = TypewriterManager()

        # Test minimum
        manager.set_speed(10)
        assert manager.current_speed_ms == 10

        # Test maximum
        manager.set_speed(100)
        assert manager.current_speed_ms == 100

    def test_different_speeds_display_at_different_rates(self) -> None:
        """Test that different speeds display characters at different rates."""
        text = "Hello World"

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
        assert fast_chars > slow_chars


class TestTypewriterMotionSensitivity:
    """Tests for motion sensitivity support."""

    def test_motion_sensitivity_disabled_by_default(self) -> None:
        """Test that motion sensitivity is disabled by default."""
        manager = TypewriterManager()
        assert manager.motion_sensitivity_enabled is False

    def test_motion_sensitivity_enabled_on_init(self) -> None:
        """Test enabling motion sensitivity on initialization."""
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        assert manager.motion_sensitivity_enabled is True

    def test_set_motion_sensitivity(self) -> None:
        """Test setting motion sensitivity."""
        manager = TypewriterManager()
        manager.set_motion_sensitivity(True)
        assert manager.motion_sensitivity_enabled is True

        manager.set_motion_sensitivity(False)
        assert manager.motion_sensitivity_enabled is False

    def test_motion_sensitivity_shows_full_text_immediately(self) -> None:
        """Test that motion sensitivity shows full text immediately."""
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start("Hello World")

        # Should show full text immediately
        assert manager.displayed_chars == 11
        assert manager.active is False
        assert manager.get_displayed_text() == "Hello World"

    def test_motion_sensitivity_with_update(self) -> None:
        """Test that motion sensitivity works with update."""
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start("Hello")

        # Update should not change anything
        result = manager.update(0.1)
        assert result == "Hello"
        assert manager.displayed_chars == 5

    def test_motion_sensitivity_toggle_after_start(self) -> None:
        """Test toggling motion sensitivity after start."""
        manager = TypewriterManager()
        manager.start("Hello World", speed_ms=30)

        # Display partial text
        manager.update(0.06)
        assert manager.displayed_chars == 2

        # Enable motion sensitivity (should not affect current effect)
        manager.set_motion_sensitivity(True)
        assert manager.motion_sensitivity_enabled is True

        # New effect should show full text immediately
        manager.start("New Text")
        assert manager.displayed_chars == 8
        assert manager.active is False

    def test_motion_sensitivity_with_empty_text(self) -> None:
        """Test motion sensitivity with empty text."""
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start("")

        assert manager.displayed_chars == 0
        assert manager.active is False


class TestTypewriterEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_very_long_text(self) -> None:
        """Test with very long text."""
        manager = TypewriterManager()
        long_text = "A" * 10000
        manager.start(long_text, speed_ms=10)

        # Update with enough time to show all
        manager.update(100.0)
        assert manager.displayed_chars == 10000
        assert manager.is_complete() is True

    def test_very_fast_speed(self) -> None:
        """Test with very fast speed (minimum)."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=10)

        # Update with 50ms (5 characters at 10ms each)
        manager.update(0.05)
        assert manager.displayed_chars == 5

    def test_very_slow_speed(self) -> None:
        """Test with very slow speed (maximum)."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=100)

        # Update with 50ms (0.5 characters at 100ms each)
        manager.update(0.05)
        assert manager.displayed_chars == 0

    def test_zero_delta_time(self) -> None:
        """Test update with zero delta time."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        result = manager.update(0.0)
        assert result == ""
        assert manager.displayed_chars == 0

    def test_very_large_delta_time(self) -> None:
        """Test update with very large delta time."""
        manager = TypewriterManager()
        manager.start("Hello", speed_ms=30)

        # Update with 10 seconds (should show all text)
        result = manager.update(10.0)
        assert result == "Hello"
        assert manager.is_complete() is True

    def test_multiple_starts_in_sequence(self) -> None:
        """Test starting multiple effects in sequence."""
        manager = TypewriterManager()

        texts = ["First", "Second", "Third"]
        for text in texts:
            manager.start(text, speed_ms=30)
            manager.update(0.2)
            assert manager.is_complete() is True

    def test_whitespace_text(self) -> None:
        """Test with whitespace text."""
        manager = TypewriterManager()
        manager.start("   ", speed_ms=30)

        manager.update(0.1)
        assert manager.displayed_chars == 3
        assert manager.get_displayed_text() == "   "

    def test_newline_characters(self) -> None:
        """Test with newline characters."""
        manager = TypewriterManager()
        manager.start("Hello\nWorld", speed_ms=30)

        manager.update(0.2)
        assert "\n" in manager.get_displayed_text()

    def test_tab_characters(self) -> None:
        """Test with tab characters."""
        manager = TypewriterManager()
        manager.start("Hello\tWorld", speed_ms=30)

        manager.update(0.2)
        assert "\t" in manager.get_displayed_text()
