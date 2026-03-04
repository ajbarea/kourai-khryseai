"""Tests for GUI settings and font scaling."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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
        """Settings should persist correctly when saved and reloaded.

        Validates: Requirements 15.1, 15.2, 15.3, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")

            # Create and set settings
            settings1 = SettingsManager(config_path)
            settings1.set_font_scale(font_scale)
            settings1.set_auto_scroll(auto_scroll)
            settings1.set_high_contrast(high_contrast)
            settings1.set_show_timestamps(show_timestamps)
            settings1.set_timestamp_24h(timestamp_24h)
            settings1.set_typewriter_speed(typewriter_speed)
            settings1.set_show_status_bubbles(show_status_bubbles)

            # Create new instance from same file
            settings2 = SettingsManager(config_path)

            # Verify all settings persisted
            assert settings2.get_font_scale() == pytest.approx(font_scale, abs=0.01)
            assert settings2.get_auto_scroll() == auto_scroll
            assert settings2.get_high_contrast() == high_contrast
            assert settings2.get_show_timestamps() == show_timestamps
            assert settings2.get_timestamp_24h() == timestamp_24h
            assert settings2.get_typewriter_speed() == typewriter_speed
            assert settings2.get_show_status_bubbles() == show_status_bubbles


class TestSettingsManagerUnit:
    """Unit tests for SettingsManager."""

    def test_default_values(self) -> None:
        """Settings should have correct default values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            assert settings.get_font_scale() == 1.0
            assert settings.get_auto_scroll() is True
            assert settings.get_high_contrast() is False
            assert settings.get_show_timestamps() is True
            assert settings.get_timestamp_24h() is True
            assert settings.get_typewriter_speed() == 30
            assert settings.get_show_status_bubbles() is True

    def test_font_scale_clamping(self) -> None:
        """Font scale should be clamped to valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            # Test below minimum
            settings.set_font_scale(0.5)
            assert settings.get_font_scale() == 0.8

            # Test above maximum
            settings.set_font_scale(2.5)
            assert settings.get_font_scale() == 2.0

            # Test valid range
            settings.set_font_scale(1.5)
            assert settings.get_font_scale() == 1.5

    def test_typewriter_speed_clamping(self) -> None:
        """Typewriter speed should be clamped to valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            # Test below minimum
            settings.set_typewriter_speed(5)
            assert settings.get_typewriter_speed() == 10

            # Test above maximum
            settings.set_typewriter_speed(150)
            assert settings.get_typewriter_speed() == 100

            # Test valid range
            settings.set_typewriter_speed(50)
            assert settings.get_typewriter_speed() == 50

    def test_get_set_methods(self) -> None:
        """Generic get/set methods should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            settings.set("custom_setting", "test_value")
            assert settings.get("custom_setting") == "test_value"

            settings.set("number_setting", 42)
            assert settings.get("number_setting") == 42

    def test_window_size(self) -> None:
        """Window size settings should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            settings.set_window_size(1920, 1080)
            width, height = settings.get_window_size()
            assert width == 1920
            assert height == 1080


class TestFontScalerUnit:
    """Unit tests for FontScaler."""

    def test_initial_scale_from_settings(self) -> None:
        """FontScaler should initialize with scale from settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)
            settings.set_font_scale(1.2)

            scaler = FontScaler(settings)

            assert scaler.get_scale() == 1.2

    def test_scale_clamping(self) -> None:
        """FontScaler should clamp scale to valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            scaler = FontScaler(settings)

            # Test below minimum
            scaler.set_scale(0.5)
            assert scaler.get_scale() == 0.8

            # Test above maximum
            scaler.set_scale(2.5)
            assert scaler.get_scale() == 2.0

            # Test valid range
            scaler.set_scale(1.5)
            assert scaler.get_scale() == 1.5

    def test_scale_up_down(self) -> None:
        """Scale up/down methods should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)
            settings.set_font_scale(1.0)

            scaler = FontScaler(settings)

            scaler.scale_up()
            assert scaler.get_scale() == pytest.approx(1.1, abs=0.01)

            scaler.scale_down()
            assert scaler.get_scale() == pytest.approx(1.0, abs=0.01)

    def test_font_caching(self) -> None:
        """FontScaler should cache fonts correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            scaler = FontScaler(settings)

            # Get font multiple times - should return cached version
            font1 = scaler.get_font("body")
            font2 = scaler.get_font("body")

            # Same font object should be returned
            assert font1 is font2

    def test_font_scaling(self) -> None:
        """Font sizes should be scaled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)
            settings.set_font_scale(1.5)

            scaler = FontScaler(settings)

            # Body font base size is 16, should be scaled to 24
            font = scaler.get_font("body")
            # The font size should be approximately scaled
            assert font.size == 24

    def test_scroll_adjustment(self) -> None:
        """Scroll position should be adjusted correctly when scale changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            scaler = FontScaler(settings)

            # Test scroll adjustment
            new_scroll = scaler.adjust_scroll_for_scale(
                old_scale=1.0,
                new_scale=1.5,
                current_scroll=100,
                content_height=1000,
                view_height=500,
            )

            # Scroll position should be adjusted proportionally
            assert new_scroll >= 0
            assert new_scroll <= 1000 - 500  # Within valid range

    def test_scroll_adjustment_no_change_needed(self) -> None:
        """Scroll adjustment should return 0 when content fits in view."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            scaler = FontScaler(settings)

            # When content height is less than view height, no scroll needed
            new_scroll = scaler.adjust_scroll_for_scale(
                old_scale=1.0,
                new_scale=1.5,
                current_scroll=0,
                content_height=300,
                view_height=500,
            )

            assert new_scroll == 0

    def test_scroll_adjustment_at_minimum(self) -> None:
        """Scroll adjustment should handle minimum scale correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            scaler = FontScaler(settings)

            new_scroll = scaler.adjust_scroll_for_scale(
                old_scale=0.8,
                new_scale=1.0,
                current_scroll=0,
                content_height=800,
                view_height=500,
            )

            assert new_scroll >= 0

    def test_scroll_adjustment_at_maximum(self) -> None:
        """Scroll adjustment should handle maximum scale correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            scaler = FontScaler(settings)

            new_scroll = scaler.adjust_scroll_for_scale(
                old_scale=2.0,
                new_scale=1.5,
                current_scroll=500,
                content_height=2000,
                view_height=500,
            )

            assert new_scroll >= 0
            assert new_scroll <= 2000 - 500  # Within valid range


# Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence
class TestTypewriterManagerProperty:
    """Property-based tests for typewriter effect."""

    @settings(max_examples=50)
    @given(
        text=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P")), min_size=1, max_size=50
        ),
        speed_ms=st.integers(min_value=10, max_value=100),
    )
    def test_typewriter_reveals_characters_sequentially(
        self,
        text: str,
        speed_ms: int,
    ) -> None:
        """Typewriter should reveal characters one at a time.

        Validates: Requirements 1.1, 1.3
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)
            settings.set_typewriter_speed(speed_ms)

            typewriter = TypewriterManager(settings)
            typewriter.start(text)

            # After starting, no characters should be displayed yet
            assert typewriter.get_displayed_text() == ""

            # Simulate updates until complete
            dt = speed_ms / 1000.0  # 1 character per update
            while typewriter.update(dt):
                pass

            # All characters should be revealed
            assert typewriter.get_displayed_text() == text


# Feature: gui-improvements, Property 2: Typewriter Skip Functionality
class TestTypewriterSkipProperty:
    """Property-based tests for typewriter skip functionality."""

    @settings(max_examples=50)
    @given(
        text=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P")), min_size=10, max_size=50
        ),
    )
    def test_skip_reveals_all_text_immediately(
        self,
        text: str,
    ) -> None:
        """Skipping should immediately reveal all text.

        Validates: Requirement 1.2
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.start(text)

            # Simulate some updates
            dt = 0.01  # Small time step
            for _ in range(5):
                typewriter.update(dt)

            # Skip to end
            typewriter.skip()

            # All text should be revealed immediately
            assert typewriter.get_displayed_text() == text
            assert not typewriter.is_typing()


class TestTypewriterManagerUnit:
    """Unit tests for TypewriterManager."""

    def test_start_resets_state(self) -> None:
        """Starting new text should reset state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.start("Hello")

            # Simulate some typing
            dt = 0.01
            for _ in range(3):
                typewriter.update(dt)

            # Start new text
            typewriter.start("World")

            # State should be reset
            assert typewriter.get_displayed_text() == ""
            assert typewriter.is_typing()
            assert not typewriter.is_skipped()

    def test_pause_resume(self) -> None:
        """Pause and resume should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.start("Hello World")

            # Type some characters
            dt = 0.01
            for _ in range(3):
                typewriter.update(dt)

            displayed_before = typewriter.get_displayed_text()

            # Pause
            typewriter.pause()
            assert typewriter.is_paused()

            # Update while paused - no change
            typewriter.update(dt)
            assert typewriter.get_displayed_text() == displayed_before

            # Resume
            typewriter.resume()
            assert not typewriter.is_paused()

            # Continue typing
            typewriter.update(dt)
            assert len(typewriter.get_displayed_text()) > len(displayed_before)

    def test_skip_to_end(self) -> None:
        """Skip should reveal all text immediately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.start("Hello World")

            # Type some characters
            dt = 0.01
            for _ in range(3):
                typewriter.update(dt)

            # Skip
            typewriter.skip()

            # All text should be revealed
            assert typewriter.get_displayed_text() == "Hello World"
            assert not typewriter.is_typing()

    def test_speed_setting(self) -> None:
        """Speed setting should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.set_speed(50)
            assert typewriter.get_speed() == 50

            typewriter.set_speed(5)
            assert typewriter.get_speed() == 10  # Clamped to minimum

            typewriter.set_speed(150)
            assert typewriter.get_speed() == 100  # Clamped to maximum

    def test_motion_sensitive(self) -> None:
        """Motion sensitivity setting should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)

            typewriter.set_motion_sensitive(True)
            assert typewriter.is_motion_sensitive()

            typewriter.set_motion_sensitive(False)
            assert not typewriter.is_motion_sensitive()

    def test_reset(self) -> None:
        """Reset should return to initial state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.start("Hello World")

            # Type some characters
            dt = 0.01
            for _ in range(3):
                typewriter.update(dt)

            # Reset
            typewriter.reset()

            # State should be reset
            assert typewriter.get_displayed_text() == ""
            assert not typewriter.is_typing()
            assert not typewriter.is_paused()
            assert not typewriter.is_skipped()

    def test_completion_detection(self) -> None:
        """Update should return True when complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            settings = SettingsManager(config_path)

            typewriter = TypewriterManager(settings)
            typewriter.start("Hi")

            # Not complete yet
            assert not typewriter.update(0.01)

            # Complete after enough time
            assert typewriter.update(0.01)
