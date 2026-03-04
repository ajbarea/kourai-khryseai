"""Unit tests for FontScaler class.

Tests scale range clamping, font scaling at various values, and scroll
adjustment calculations.
"""

from __future__ import annotations

import pygame
import pygame.freetype
import pytest

from .font_scaler import FontScaler


class TestFontScalerBasic:
    """Basic FontScaler functionality tests."""

    def test_init_default_scale(self) -> None:
        """Test that FontScaler initializes with default scale of 1.0."""
        scaler = FontScaler()
        assert scaler.scale == 1.0

    def test_init_custom_range(self) -> None:
        """Test that FontScaler accepts custom scale range."""
        scaler = FontScaler(min_scale=0.5, max_scale=3.0)
        assert scaler.min_scale == 0.5
        assert scaler.max_scale == 3.0

    def test_set_scale_valid_value(self) -> None:
        """Test setting a valid scale value."""
        scaler = FontScaler()
        scaler.set_scale(1.5)
        assert scaler.scale == 1.5

    def test_set_scale_at_minimum(self) -> None:
        """Test setting scale at minimum boundary."""
        scaler = FontScaler()
        scaler.set_scale(0.8)
        assert scaler.scale == 0.8

    def test_set_scale_at_maximum(self) -> None:
        """Test setting scale at maximum boundary."""
        scaler = FontScaler()
        scaler.set_scale(2.0)
        assert scaler.scale == 2.0


class TestFontScalerClamping:
    """FontScaler scale clamping tests."""

    def test_set_scale_below_minimum_clamped(self) -> None:
        """Test that scale below minimum is clamped to minimum."""
        scaler = FontScaler()
        scaler.set_scale(0.5)
        assert scaler.scale == 0.8

    def test_set_scale_above_maximum_clamped(self) -> None:
        """Test that scale above maximum is clamped to maximum."""
        scaler = FontScaler()
        scaler.set_scale(3.0)
        assert scaler.scale == 2.0

    def test_set_scale_negative_clamped(self) -> None:
        """Test that negative scale is clamped to minimum."""
        scaler = FontScaler()
        scaler.set_scale(-1.0)
        assert scaler.scale == 0.8

    def test_set_scale_zero_clamped(self) -> None:
        """Test that zero scale is clamped to minimum."""
        scaler = FontScaler()
        scaler.set_scale(0.0)
        assert scaler.scale == 0.8

    def test_set_scale_multiple_times(self) -> None:
        """Test setting scale multiple times with clamping."""
        scaler = FontScaler()
        scaler.set_scale(0.5)  # Clamped to 0.8
        assert scaler.scale == 0.8
        scaler.set_scale(1.5)  # Valid
        assert scaler.scale == 1.5
        scaler.set_scale(3.0)  # Clamped to 2.0
        assert scaler.scale == 2.0


class TestFontScaling:
    """FontScaler font scaling tests."""

    @pytest.fixture(autouse=True)
    def setup_pygame(self) -> None:
        """Initialize pygame for font tests."""
        if not pygame.get_init():
            pygame.init()

    def test_scale_font_at_100_percent(self) -> None:
        """Test scaling font at 100% (no scaling)."""
        scaler = FontScaler()
        scaler.set_scale(1.0)

        # Use default font instead of creating empty font file
        font = pygame.freetype.Font(None, 24)
        scaled_font = scaler.scale_font(font, 24)
        assert scaled_font.size == 24

    def test_scale_font_at_150_percent(self) -> None:
        """Test scaling font at 150%."""
        scaler = FontScaler()
        scaler.set_scale(1.5)

        font = pygame.freetype.Font(None, 24)
        scaled_font = scaler.scale_font(font, 24)
        assert scaled_font.size == 36  # 24 * 1.5

    def test_scale_font_at_80_percent(self) -> None:
        """Test scaling font at 80%."""
        scaler = FontScaler()
        scaler.set_scale(0.8)

        font = pygame.freetype.Font(None, 24)
        scaled_font = scaler.scale_font(font, 24)
        assert scaled_font.size == 19  # int(24 * 0.8)

    def test_scale_font_at_200_percent(self) -> None:
        """Test scaling font at 200%."""
        scaler = FontScaler()
        scaler.set_scale(2.0)

        font = pygame.freetype.Font(None, 24)
        scaled_font = scaler.scale_font(font, 24)
        assert scaled_font.size == 48  # 24 * 2.0

    def test_scale_font_various_base_sizes(self) -> None:
        """Test scaling font with various base sizes."""
        scaler = FontScaler()
        scaler.set_scale(1.5)

        # Test with different base sizes
        for base_size in [12, 16, 20, 24, 32]:
            font = pygame.freetype.Font(None, base_size)
            scaled_font = scaler.scale_font(font, base_size)
            expected_size = int(base_size * 1.5)
            assert scaled_font.size == expected_size


class TestScrollAdjustment:
    """FontScaler scroll adjustment tests."""

    def test_adjust_scroll_no_change(self) -> None:
        """Test scroll adjustment when scale doesn't change."""
        scaler = FontScaler()
        adjusted = scaler.adjust_scroll(100, 1.0, 1.0)
        assert adjusted == 100

    def test_adjust_scroll_scale_increase(self) -> None:
        """Test scroll adjustment when scale increases."""
        scaler = FontScaler()
        # If scale doubles, scroll position should double
        adjusted = scaler.adjust_scroll(100, 1.0, 2.0)
        assert adjusted == 200

    def test_adjust_scroll_scale_decrease(self) -> None:
        """Test scroll adjustment when scale decreases."""
        scaler = FontScaler()
        # If scale halves, scroll position should halve
        adjusted = scaler.adjust_scroll(100, 2.0, 1.0)
        assert adjusted == 50

    def test_adjust_scroll_from_80_to_100_percent(self) -> None:
        """Test scroll adjustment from 80% to 100%."""
        scaler = FontScaler()
        # Scale from 0.8 to 1.0 (increase by 1.25x)
        adjusted = scaler.adjust_scroll(80, 0.8, 1.0)
        assert adjusted == 100  # 80 * (1.0 / 0.8)

    def test_adjust_scroll_from_100_to_150_percent(self) -> None:
        """Test scroll adjustment from 100% to 150%."""
        scaler = FontScaler()
        # Scale from 1.0 to 1.5 (increase by 1.5x)
        adjusted = scaler.adjust_scroll(100, 1.0, 1.5)
        assert adjusted == 150  # 100 * (1.5 / 1.0)

    def test_adjust_scroll_from_150_to_100_percent(self) -> None:
        """Test scroll adjustment from 150% to 100%."""
        scaler = FontScaler()
        # Scale from 1.5 to 1.0 (decrease by 0.667x)
        adjusted = scaler.adjust_scroll(150, 1.5, 1.0)
        assert adjusted == 100  # 150 * (1.0 / 1.5)

    def test_adjust_scroll_zero_scroll_position(self) -> None:
        """Test scroll adjustment with zero scroll position."""
        scaler = FontScaler()
        adjusted = scaler.adjust_scroll(0, 1.0, 2.0)
        assert adjusted == 0

    def test_adjust_scroll_large_scroll_position(self) -> None:
        """Test scroll adjustment with large scroll position."""
        scaler = FontScaler()
        adjusted = scaler.adjust_scroll(10000, 1.0, 1.5)
        assert adjusted == 15000

    def test_adjust_scroll_zero_old_scale(self) -> None:
        """Test scroll adjustment with zero old scale (edge case)."""
        scaler = FontScaler()
        # Should return current scroll unchanged to avoid division by zero
        adjusted = scaler.adjust_scroll(100, 0, 1.0)
        assert adjusted == 100

    def test_adjust_scroll_fractional_scales(self) -> None:
        """Test scroll adjustment with fractional scales."""
        scaler = FontScaler()
        # Scale from 0.9 to 1.1
        adjusted = scaler.adjust_scroll(100, 0.9, 1.1)
        expected = int(100 * (1.1 / 0.9))
        assert adjusted == expected

    def test_adjust_scroll_maintains_proportional_position(self) -> None:
        """Test that scroll adjustment maintains proportional position."""
        scaler = FontScaler()

        # Test multiple scale transitions
        transitions = [
            (100, 1.0, 1.5),  # 100 -> 150
            (150, 1.5, 0.8),  # 150 -> 80
            (80, 0.8, 2.0),  # 80 -> 200
        ]

        for scroll, old_scale, new_scale in transitions:
            adjusted = scaler.adjust_scroll(scroll, old_scale, new_scale)
            expected = int(scroll * (new_scale / old_scale))
            assert adjusted == expected


class TestFontScalerEdgeCases:
    """FontScaler edge case tests."""

    def test_scale_range_boundaries(self) -> None:
        """Test that scale range boundaries are respected."""
        scaler = FontScaler(min_scale=0.5, max_scale=3.0)

        scaler.set_scale(0.4)
        assert scaler.scale == 0.5

        scaler.set_scale(3.5)
        assert scaler.scale == 3.0

    def test_very_small_scale(self) -> None:
        """Test with very small scale value."""
        scaler = FontScaler()
        scaler.set_scale(0.001)
        assert scaler.scale == 0.8  # Clamped to minimum

    def test_very_large_scale(self) -> None:
        """Test with very large scale value."""
        scaler = FontScaler()
        scaler.set_scale(1000.0)
        assert scaler.scale == 2.0  # Clamped to maximum

    def test_float_precision_in_scroll_adjustment(self) -> None:
        """Test scroll adjustment with float precision."""
        scaler = FontScaler()
        # Test with values that might have floating point precision issues
        adjusted = scaler.adjust_scroll(333, 0.9, 1.1)
        # Should be int(333 * (1.1 / 0.9)) = int(408.333...) = 407 or 408
        # depending on float precision
        assert isinstance(adjusted, int)
        # Allow for floating point precision variations
        assert 407 <= adjusted <= 408

    def test_multiple_scale_changes(self) -> None:
        """Test multiple scale changes in sequence."""
        scaler = FontScaler()

        scales = [0.8, 1.0, 1.5, 2.0, 1.2, 0.9]
        for scale in scales:
            scaler.set_scale(scale)
            # Verify scale is within valid range
            assert scaler.min_scale <= scaler.scale <= scaler.max_scale
