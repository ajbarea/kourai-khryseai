"""Property-based tests for FontScaler class.

Feature: gui-improvements, Property 9: Font Scale Consistency
Validates: Requirements 9.1, 9.2, 9.3, 12.1, 12.5
"""

from __future__ import annotations

import pytest

pytest.importorskip("pygame")

import pygame
import pygame.freetype
from hypothesis import given, settings, strategies as st

from hosts.gui.font_scaler import FontScaler

# Strategy for valid scale values (80% to 200%)
valid_scales = st.floats(min_value=0.8, max_value=2.0, allow_nan=False, allow_infinity=False)

# Strategy for scale values that might need clamping
any_scales = st.floats(allow_nan=False, allow_infinity=False)

# Strategy for base font sizes
base_sizes = st.integers(min_value=8, max_value=72)

# Strategy for scroll positions
scroll_positions = st.integers(min_value=0, max_value=10000)


class TestFontScaleConsistencyProperty:
    """Property-based tests for font scale consistency.

    Feature: gui-improvements, Property 9: Font Scale Consistency
    Validates: Requirements 9.1, 9.2, 9.3, 12.1, 12.5
    """

    @pytest.fixture(autouse=True)
    def setup_pygame(self) -> None:
        """Initialize pygame for font tests."""
        if not pygame.get_init():
            pygame.init()

    @given(scale=valid_scales, base_size=base_sizes)
    @settings(max_examples=100)
    def test_scale_within_valid_range(self, scale: float, base_size: int) -> None:
        """Property: Scale values within valid range are preserved.

        For any scale value from 80% to 200%, setting that scale should
        preserve the exact value.

        Validates: Requirements 9.1, 9.2, 9.3
        """
        scaler = FontScaler()
        scaler.set_scale(scale)

        # Scale should be preserved exactly
        assert scaler.scale == scale
        assert 0.8 <= scaler.scale <= 2.0

    @given(scale=any_scales)
    @settings(max_examples=100)
    def test_scale_always_clamped_to_range(self, scale: float) -> None:
        """Property: Any scale value is clamped to valid range.

        For any scale value (including out-of-range), the resulting scale
        should always be within [0.8, 2.0].

        Validates: Requirements 9.1, 9.2
        """
        scaler = FontScaler()
        scaler.set_scale(scale)

        # Scale should always be within valid range
        assert 0.8 <= scaler.scale <= 2.0

    @given(scale=valid_scales, base_size=base_sizes)
    @settings(max_examples=100)
    def test_scaled_font_size_proportional(self, scale: float, base_size: int) -> None:
        """Property: Scaled font size is proportional to base size and scale.

        For any valid scale and base size, the scaled font size should be
        approximately equal to base_size * scale (rounded to int).

        Validates: Requirements 9.1, 9.2, 9.3
        """
        scaler = FontScaler()
        scaler.set_scale(scale)

        font = pygame.freetype.Font(None, base_size)
        scaled_font = scaler.scale_font(font, base_size)

        expected_size = int(base_size * scale)
        actual_size = scaled_font.size
        if isinstance(actual_size, tuple):
            actual_size = actual_size[0]
        assert actual_size == expected_size

    @given(scale=valid_scales, base_size=base_sizes)
    @settings(max_examples=100)
    def test_scale_100_percent_preserves_size(self, scale: float, base_size: int) -> None:
        """Property: 100% scale preserves original font size.

        For any base size, when scale is set to 1.0 (100%), the scaled
        font size should equal the base size.

        Validates: Requirements 9.1, 9.3
        """
        scaler = FontScaler()
        scaler.set_scale(1.0)

        font = pygame.freetype.Font(None, base_size)
        scaled_font = scaler.scale_font(font, base_size)

        actual_size = scaled_font.size
        if isinstance(actual_size, tuple):
            actual_size = actual_size[0]
        assert actual_size == base_size

    @given(
        old_scale=valid_scales,
        new_scale=valid_scales,
        scroll_pos=scroll_positions,
    )
    @settings(max_examples=100)
    def test_scroll_adjustment_proportional(
        self, old_scale: float, new_scale: float, scroll_pos: int
    ) -> None:
        """Property: Scroll adjustment is proportional to scale change.

        For any old and new scale values and scroll position, the adjusted
        scroll position should be proportional to the scale ratio.

        Validates: Requirements 9.2, 9.3, 12.5
        """
        scaler = FontScaler()

        if old_scale == 0:
            # Skip division by zero case
            return

        adjusted = scaler.adjust_scroll(scroll_pos, old_scale, new_scale)
        expected = int(scroll_pos * (new_scale / old_scale))

        assert adjusted == expected

    @given(scale=valid_scales, scroll_pos=scroll_positions)
    @settings(max_examples=100)
    def test_scroll_adjustment_no_change_same_scale(self, scale: float, scroll_pos: int) -> None:
        """Property: Scroll position unchanged when scale doesn't change.

        For any scroll position and scale, when adjusting with the same
        old and new scale, the scroll position should remain unchanged.

        Validates: Requirements 9.3, 12.5
        """
        scaler = FontScaler()
        adjusted = scaler.adjust_scroll(scroll_pos, scale, scale)

        assert adjusted == scroll_pos

    @given(scale=valid_scales)
    @settings(max_examples=100)
    def test_scale_idempotent(self, scale: float) -> None:
        """Property: Setting scale multiple times is idempotent.

        For any scale value, setting it multiple times should result in
        the same final scale value.

        Validates: Requirements 9.1, 9.2
        """
        scaler = FontScaler()

        # Set scale multiple times
        for _ in range(5):
            scaler.set_scale(scale)

        # Final scale should match the input (clamped if necessary)
        expected = max(0.8, min(scale, 2.0))
        assert scaler.scale == expected

    @given(
        scale1=valid_scales,
        scale2=valid_scales,
        base_size=base_sizes,
    )
    @settings(max_examples=100)
    def test_scale_transition_consistency(
        self, scale1: float, scale2: float, base_size: int
    ) -> None:
        """Property: Font size changes consistently across scale transitions.

        For any two scale values and base size, transitioning from scale1
        to scale2 should result in a font size proportional to scale2.

        Validates: Requirements 9.1, 9.2, 9.3
        """
        scaler = FontScaler()

        # Set first scale
        scaler.set_scale(scale1)
        font1 = pygame.freetype.Font(None, base_size)
        scaled_font1 = scaler.scale_font(font1, base_size)
        size1 = scaled_font1.size

        # Transition to second scale
        scaler.set_scale(scale2)
        font2 = pygame.freetype.Font(None, base_size)
        scaled_font2 = scaler.scale_font(font2, base_size)
        size2 = scaled_font2.size

        # Verify sizes are proportional to scales
        expected_size1 = int(base_size * scale1)
        expected_size2 = int(base_size * scale2)

        assert size1 == expected_size1
        assert size2 == expected_size2

    @given(
        old_scale=valid_scales,
        new_scale=valid_scales,
        scroll_pos=scroll_positions,
    )
    @settings(max_examples=100)
    def test_scroll_adjustment_maintains_relative_position(
        self, old_scale: float, new_scale: float, scroll_pos: int
    ) -> None:
        """Property: Scroll adjustment maintains relative position in content.

        For any scale transition and scroll position, the adjusted scroll
        position should maintain the same relative position in the content.

        Validates: Requirements 9.3, 12.5
        """
        scaler = FontScaler()

        if old_scale == 0:
            return

        adjusted = scaler.adjust_scroll(scroll_pos, old_scale, new_scale)

        # Verify the ratio is maintained
        if scroll_pos > 0 and new_scale > 0:
            original_ratio = scroll_pos / old_scale
            adjusted_ratio = adjusted / new_scale
            # Allow for floating point and integer rounding errors
            assert abs(original_ratio - adjusted_ratio) <= 1.5

    @given(scale=any_scales)
    @settings(max_examples=100)
    def test_scale_clamping_boundaries(self, scale: float) -> None:
        """Property: Scale clamping respects exact boundaries.

        For any scale value, after clamping, the result should be exactly
        at the boundary or within the valid range.

        Validates: Requirements 9.1, 9.2
        """
        scaler = FontScaler()
        scaler.set_scale(scale)

        # Check boundaries
        if scale < 0.8:
            assert scaler.scale == 0.8
        elif scale > 2.0:
            assert scaler.scale == 2.0
        else:
            assert scaler.scale == scale

    @given(base_size=base_sizes)
    @settings(max_examples=100)
    def test_scale_range_coverage(self, base_size: int) -> None:
        """Property: All scale values in range produce valid font sizes.

        For any base size, all scale values from 80% to 200% should produce
        valid (positive) font sizes.

        Validates: Requirements 9.1, 9.2, 9.3
        """
        scaler = FontScaler()

        # Test multiple scales across the range
        test_scales = [0.8, 1.0, 1.2, 1.5, 1.8, 2.0]

        for test_scale in test_scales:
            scaler.set_scale(test_scale)
            font = pygame.freetype.Font(None, base_size)
            scaled_font = scaler.scale_font(font, base_size)

            actual_size = scaled_font.size
            if isinstance(actual_size, tuple):
                actual_size = actual_size[0]

            # Font size should be positive
            assert actual_size > 0
            # Font size should be proportional to scale
            expected = int(base_size * test_scale)
            assert actual_size == expected
