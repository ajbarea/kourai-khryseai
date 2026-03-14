"""Tests for GUI settings, font scaling, and typewriter effect."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from hosts.gui.font_scaler import FontScaler
from hosts.gui.settings import SettingsManager
from hosts.gui.typewriter import TypewriterManager


# Feature: gui-improvements, Property 10: Settings Persistence
class TestSettingsManagerProperty:
    """Property-based tests for SettingsManager persistence."""

    @settings(max_examples=50)
    @given(
        font_scale=st.floats(min_value=0.8, max_value=2.0, allow_nan=False, allow_infinity=False),
        auto_scroll=st.booleans(),
        high_contrast=st.booleans(),
        show_timestamps=st.booleans(),
        timestamp_24h=st.booleans(),
        typewriter_speed=st.integers(min_value=10, max_value=100),
        show_status_bubbles=st.booleans(),
    )
    def test_settings_persistence_across_loads(
        self,
        font_scale: float,
        auto_scroll: bool,
        high_contrast: bool,
        show_timestamps: bool,
        timestamp_24h: bool,
        typewriter_speed: int,
        show_status_bubbles: bool,
    ) -> None:
        """Settings should persist correctly when saved and reloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")

            # Create and set settings
            settings1 = SettingsManager(config_path)
            settings1.set("font_scale", font_scale)
            settings1.set("auto_scroll_enabled", auto_scroll)
            settings1.set("high_contrast", high_contrast)
            settings1.set("show_timestamps", show_timestamps)
            settings1.set("timestamp_format", "24h" if timestamp_24h else "12h")
            settings1.set("typewriter_speed_ms", typewriter_speed)
            settings1.set("status_bubbles_collapsed", not show_status_bubbles)
            settings1.save()

            # Create new instance from same file
            settings2 = SettingsManager(config_path)

            # Verify all settings persisted
            assert settings2.get("font_scale") == pytest.approx(font_scale, abs=0.01)
            assert settings2.get("auto_scroll_enabled") == auto_scroll
            assert settings2.get("high_contrast") == high_contrast
            assert settings2.get("show_timestamps") == show_timestamps
            assert settings2.get("timestamp_format") == ("24h" if timestamp_24h else "12h")
            assert settings2.get("typewriter_speed_ms") == typewriter_speed
            assert settings2.get("status_bubbles_collapsed") == (not show_status_bubbles)


class TestSettingsManagerUnit:
    """Unit tests for SettingsManager."""

    def test_default_values(self) -> None:
        """Settings should have correct default values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            mgr = SettingsManager(config_path)

            assert mgr.get("font_scale") == 1.0
            assert mgr.get("auto_scroll_enabled") is True
            assert mgr.get("high_contrast") is False
            assert mgr.get("show_timestamps") is True
            assert mgr.get("typewriter_speed_ms") == 30

    def test_get_set_methods(self) -> None:
        """Generic get/set methods should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            mgr = SettingsManager(config_path)

            mgr.set("custom_setting", "test_value")
            assert mgr.get("custom_setting") == "test_value"

            mgr.set("number_setting", 42)
            assert mgr.get("number_setting") == 42


class TestFontScalerUnit:
    """Unit tests for FontScaler."""

    def test_initial_scale(self) -> None:
        """FontScaler should initialize with default scale."""
        scaler = FontScaler()
        assert scaler.scale == 1.0

    def test_scale_clamping(self) -> None:
        """FontScaler should clamp scale to valid range."""
        scaler = FontScaler(min_scale=0.8, max_scale=2.0)

        # Test below minimum
        scaler.set_scale(0.5)
        assert scaler.scale == 0.8

        # Test above maximum
        scaler.set_scale(2.5)
        assert scaler.scale == 2.0

        # Test valid range
        scaler.set_scale(1.5)
        assert scaler.scale == 1.5

    def test_scroll_adjustment(self) -> None:
        """Scroll position should be adjusted correctly when scale changes."""
        scaler = FontScaler()

        # Test scroll adjustment
        new_scroll = scaler.adjust_scroll(
            current_scroll=100,
            old_scale=1.0,
            new_scale=1.5,
        )

        # Scroll position should be adjusted proportionally: 100 * (1.5 / 1.0) = 150
        assert new_scroll == 150


class TestTypewriterManagerProperty:
    """Property-based tests for typewriter effect."""

    @settings(max_examples=50)
    @given(
        text=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P")),
            min_size=1,
            max_size=50,
        ),
        speed_ms=st.integers(min_value=10, max_value=100),
    )
    def test_typewriter_reveals_characters_sequentially(
        self,
        text: str,
        speed_ms: int,
    ) -> None:
        """Typewriter should reveal characters one at a time."""
        typewriter = TypewriterManager()
        typewriter.set_speed(speed_ms)
        typewriter.start(text)

        # After starting, no characters should be displayed yet
        assert typewriter.get_displayed_text() == ""

        # Simulate updates until complete
        dt = speed_ms / 1000.0  # Time for exactly 1 character
        displayed = ""
        for i in range(len(text)):
            displayed = typewriter.update(dt)
            assert len(displayed) == i + 1
            assert displayed == text[: i + 1]

        # All characters should be revealed
        assert typewriter.get_displayed_text() == text
        assert typewriter.is_complete()


class TestTypewriterManagerUnit:
    """Unit tests for TypewriterManager."""

    def test_start_resets_state(self) -> None:
        """Starting new text should reset state."""
        typewriter = TypewriterManager()
        typewriter.start("Hello")

        # Simulate some typing
        typewriter.update(0.05)
        assert typewriter.displayed_chars > 0

        # Start new text
        typewriter.start("World")

        # State should be reset
        assert typewriter.get_displayed_text() == ""
        assert not typewriter.is_complete()

    def test_pause_resume(self) -> None:
        """Pause and resume should work correctly."""
        typewriter = TypewriterManager()
        typewriter.start("Hello World", speed_ms=50)

        # Type some characters
        typewriter.update(0.06)  # Should type 1 char
        displayed_before = typewriter.get_displayed_text()
        assert len(displayed_before) == 1

        # Pause
        typewriter.pause()
        assert typewriter.paused

        # Update while paused - no change
        typewriter.update(0.1)
        assert typewriter.get_displayed_text() == displayed_before

        # Resume
        typewriter.resume()
        assert not typewriter.paused

        # Continue typing
        typewriter.update(0.1)
        assert len(typewriter.get_displayed_text()) > len(displayed_before)

    def test_skip_to_end(self) -> None:
        """Skip should reveal all text immediately."""
        typewriter = TypewriterManager()
        typewriter.start("Hello World")

        # Skip
        typewriter.skip()

        # All text should be revealed
        assert typewriter.get_displayed_text() == "Hello World"
        assert typewriter.is_complete()

    def test_speed_setting(self) -> None:
        """Speed setting should work correctly."""
        typewriter = TypewriterManager(min_speed_ms=10, max_speed_ms=100)
        typewriter.set_speed(50)
        assert typewriter.current_speed_ms == 50

        typewriter.set_speed(5)
        assert typewriter.current_speed_ms == 10  # Clamped to minimum

        typewriter.set_speed(150)
        assert typewriter.current_speed_ms == 100  # Clamped to maximum

    def test_motion_sensitivity(self) -> None:
        """Motion sensitivity setting should work correctly."""
        typewriter = TypewriterManager()

        typewriter.set_motion_sensitivity(True)
        assert typewriter.motion_sensitivity_enabled

        # When motion sensitivity is enabled, start() should skip immediately
        typewriter.start("Fast Text")
        assert typewriter.get_displayed_text() == "Fast Text"
        assert typewriter.is_complete()

    def test_reset(self) -> None:
        """Reset should return to initial state."""
        typewriter = TypewriterManager()
        typewriter.start("Hello World")
        typewriter.update(0.1)

        # Reset
        typewriter.reset()

        # State should be reset
        assert typewriter.get_displayed_text() == ""
        assert typewriter.is_complete()  # active = False means complete
        assert not typewriter.paused
