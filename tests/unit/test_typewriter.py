"""Unit tests for TypewriterManager class.

Tests character-by-character display, skip functionality, speed settings,
pause/resume, and motion sensitivity support.
"""

from __future__ import annotations

from hosts.gui.typewriter import TypewriterManager


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


# ===================================================================
# M20 sub-task 2 Tier 1 — word-paced mode
# ===================================================================


class TestTypewriterWordPaced:
    """Word-paced mode: cursor only advances on advance_word() calls
    (driven by the TTS engine's on_word trampoline). dt is ignored.
    """

    def test_start_word_paced_resets_cursor_to_zero(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world from Hephaestus")
        assert manager.displayed_chars == 0
        assert manager.active is True
        assert manager._word_paced is True

    def test_advance_word_reveals_next_source_word(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world from Hephaestus")
        manager.advance_word()
        # First word + trailing space → cursor at start of "world"
        assert manager.get_displayed_text().rstrip() == "Hello"

    def test_advance_word_walks_through_all_words(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world from Hephaestus")
        manager.advance_word()
        manager.advance_word()
        manager.advance_word()
        # Three of four words revealed
        assert "Hephaestus" not in manager.get_displayed_text()
        manager.advance_word()
        assert manager.get_displayed_text() == "Hello world from Hephaestus"
        assert manager.is_complete()

    def test_advance_word_idempotent_past_end_of_text(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Two words")
        manager.advance_word()
        manager.advance_word()
        # Extra fires must not raise or scramble state.
        manager.advance_word()
        manager.advance_word()
        assert manager.get_displayed_text() == "Two words"
        assert manager.is_complete()

    def test_word_paced_ignores_dt_updates(self) -> None:
        """dt-based update() must not advance the cursor in word-paced mode —
        otherwise the time-based animator races the TTS event stream."""
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.update(10.0)  # 10 seconds of dt at 30ms/char would normally fill it
        assert manager.displayed_chars == 0
        assert manager.get_displayed_text() == ""

    def test_flush_remaining_completes_animation(self) -> None:
        """Fallback path when audio stops before all words fired."""
        manager = TypewriterManager()
        manager.start_word_paced("One two three four")
        manager.advance_word()
        manager.flush_remaining()
        assert manager.get_displayed_text() == "One two three four"
        assert manager.is_complete()

    def test_motion_sensitivity_skips_word_paced_animation(self) -> None:
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start_word_paced("Animation should be skipped entirely")
        assert manager.get_displayed_text() == "Animation should be skipped entirely"
        assert manager.is_complete()

    def test_advance_word_noop_when_not_word_paced(self) -> None:
        """Time-based mode must not respond to advance_word() — otherwise a
        stray on_word callback from a previous TTS call could corrupt the
        cursor mid-time-paced render."""
        manager = TypewriterManager()
        manager.start("Hello world", speed_ms=30)
        manager.advance_word()
        assert manager.displayed_chars == 0  # untouched

    def test_paused_word_paced_blocks_advance(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.pause()
        manager.advance_word()
        assert manager.displayed_chars == 0  # paused → no advance

    def test_reset_clears_word_paced_state(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.advance_word()
        manager.reset()
        assert manager._word_paced is False
        assert manager._word_end_indices == []
        assert manager._words_revealed == 0


class TestTypewriterPendingAudio:
    """M20 sub-task 2 polish — synthesis indicator on the GUI surface.

    During the ~3s Kokoro synthesis-wait window the dialogue panel
    would otherwise show the agent name + portrait above an empty body.
    `set_pending_audio` injects a single-ellipsis placeholder so the
    player has visible feedback that the agent is loading; cleared by
    `clear_pending_audio`, `advance_word`, `flush_remaining`, or
    `reset`.
    """

    def test_pending_audio_renders_ellipsis_placeholder(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world from Hephaestus")
        manager.set_pending_audio()
        assert manager.get_displayed_text() == "…"

    def test_clear_pending_audio_reverts_to_empty_body(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.set_pending_audio()
        manager.clear_pending_audio()
        # Back to normal word-paced empty start before any advance_word.
        assert manager.get_displayed_text() == ""

    def test_advance_word_clears_pending_audio(self) -> None:
        """First spoken word arriving means audio started — drop the
        placeholder and show real text from this point on."""
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.set_pending_audio()
        manager.advance_word()
        # Cursor moved past "Hello"; placeholder must NOT mask the real
        # revealed text.
        revealed = manager.get_displayed_text()
        assert "…" not in revealed
        assert revealed.rstrip() == "Hello"

    def test_flush_remaining_clears_pending_audio(self) -> None:
        """End-of-audio fallback reveals everything — no stale placeholder."""
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.set_pending_audio()
        manager.flush_remaining()
        assert manager.get_displayed_text() == "Hello world"

    def test_reset_clears_pending_audio(self) -> None:
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.set_pending_audio()
        manager.reset()
        # After reset the manager is inactive and current_text is empty;
        # get_displayed_text returns empty string, no placeholder leak.
        assert manager.get_displayed_text() == ""

    def test_set_pending_audio_noop_when_motion_sensitivity_enabled(self) -> None:
        """Motion-sensitive players see the full text immediately —
        showing a placeholder would be a regression on that contract."""
        manager = TypewriterManager(motion_sensitivity_enabled=True)
        manager.start_word_paced("Hello world from Hephaestus")
        manager.set_pending_audio()
        assert manager.get_displayed_text() == "Hello world from Hephaestus"

    def test_set_pending_audio_noop_outside_word_paced_mode(self) -> None:
        """Time-based mode renders dt-driven; placeholder only makes
        sense for the audio-led word-paced path."""
        manager = TypewriterManager()
        manager.start("Hello world", speed_ms=30)
        manager.set_pending_audio()
        # Time-based mode at t=0: no chars displayed yet, no placeholder.
        assert manager.get_displayed_text() == ""

    def test_update_returns_placeholder_when_pending_audio(self) -> None:
        """The pygame draw loop reads via `update(dt)`, not just
        `get_displayed_text()`. Both surfaces must agree on the
        placeholder."""
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.set_pending_audio()
        # update() with any dt in word-paced mode must not advance —
        # but the placeholder should still surface.
        assert manager.update(0.5) == "…"

    def test_set_pending_audio_skipped_after_first_word_already_revealed(self) -> None:
        """Defensive: if `set_pending_audio` is called AFTER on_word
        has already advanced the cursor (race / late call), the
        placeholder must not mask real text."""
        manager = TypewriterManager()
        manager.start_word_paced("Hello world")
        manager.advance_word()
        manager.set_pending_audio()
        revealed = manager.get_displayed_text()
        assert "…" not in revealed
        assert "Hello" in revealed


class TestComputeWordEndIndices:
    """Direct tests for the word-boundary helper."""

    def test_empty_text_returns_empty_list(self) -> None:
        from hosts.gui.typewriter import _compute_word_end_indices

        assert _compute_word_end_indices("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        from hosts.gui.typewriter import _compute_word_end_indices

        assert _compute_word_end_indices("   \t\n  ") == []

    def test_single_word_returns_end_index(self) -> None:
        from hosts.gui.typewriter import _compute_word_end_indices

        assert _compute_word_end_indices("Hello") == [5]

    def test_multiple_words_returns_each_end_index(self) -> None:
        from hosts.gui.typewriter import _compute_word_end_indices

        # "Hello world" — first word ends at index 5, second at 11.
        assert _compute_word_end_indices("Hello world") == [5, 11]

    def test_collapses_multiple_spaces(self) -> None:
        from hosts.gui.typewriter import _compute_word_end_indices

        # Multiple spaces between words don't create extra boundaries.
        assert _compute_word_end_indices("Hello   world") == [5, 13]

    def test_handles_punctuation_as_part_of_word(self) -> None:
        """We split on whitespace, not punctuation — `"Hello,"` is one
        word for cursor-advance purposes (TTS may emit punctuation as a
        separate on_word event but the cursor reveals the punctuation
        glued to the word it follows)."""
        from hosts.gui.typewriter import _compute_word_end_indices

        assert _compute_word_end_indices("Hello, world!") == [6, 13]
