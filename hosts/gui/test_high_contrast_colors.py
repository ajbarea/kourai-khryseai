"""Tests for high contrast color palette."""

import pytest
from high_contrast_colors import (
    HIGH_CONTRAST_COLORS,
    STANDARD_COLORS,
    get_color,
    get_color_palette,
    is_wcag_aa_compliant,
    verify_contrast_ratio,
)


class TestHighContrastColors:
    """Test high contrast color functionality."""

    def test_get_standard_palette(self):
        """Test getting standard color palette."""
        palette = get_color_palette(high_contrast=False)
        assert palette == STANDARD_COLORS
        assert "background" in palette
        assert "text" in palette

    def test_get_high_contrast_palette(self):
        """Test getting high contrast color palette."""
        palette = get_color_palette(high_contrast=True)
        assert palette == HIGH_CONTRAST_COLORS
        assert "background" in palette
        assert "text" in palette

    def test_get_color_standard(self):
        """Test getting specific color in standard mode."""
        color = get_color("gold", high_contrast=False)
        assert color == STANDARD_COLORS["gold"]

    def test_get_color_high_contrast(self):
        """Test getting specific color in high contrast mode."""
        color = get_color("gold", high_contrast=True)
        assert color == HIGH_CONTRAST_COLORS["gold"]

    def test_get_color_default(self):
        """Test getting non-existent color returns default."""
        color = get_color("nonexistent", high_contrast=False)
        assert color == (255, 255, 255)

    def test_contrast_ratio_white_on_black(self):
        """Test contrast ratio for white on black."""
        ratio = verify_contrast_ratio((255, 255, 255), (0, 0, 0))
        assert ratio == pytest.approx(21.0, rel=0.1)

    def test_contrast_ratio_black_on_white(self):
        """Test contrast ratio for black on white."""
        ratio = verify_contrast_ratio((0, 0, 0), (255, 255, 255))
        assert ratio == pytest.approx(21.0, rel=0.1)

    def test_contrast_ratio_same_color(self):
        """Test contrast ratio for same color."""
        ratio = verify_contrast_ratio((128, 128, 128), (128, 128, 128))
        assert ratio == pytest.approx(1.0, rel=0.01)

    def test_wcag_aa_white_on_black_normal_text(self):
        """Test WCAG AA compliance for white on black (normal text)."""
        assert is_wcag_aa_compliant((255, 255, 255), (0, 0, 0), large_text=False)

    def test_wcag_aa_white_on_black_large_text(self):
        """Test WCAG AA compliance for white on black (large text)."""
        assert is_wcag_aa_compliant((255, 255, 255), (0, 0, 0), large_text=True)

    def test_wcag_aa_gold_on_black_normal_text(self):
        """Test WCAG AA compliance for gold on black (normal text)."""
        # High contrast gold should meet 4.5:1 ratio
        assert is_wcag_aa_compliant((255, 200, 0), (0, 0, 0), large_text=False)

    def test_wcag_aa_gold_on_black_large_text(self):
        """Test WCAG AA compliance for gold on black (large text)."""
        # High contrast gold should meet 3:1 ratio for large text
        assert is_wcag_aa_compliant((255, 200, 0), (0, 0, 0), large_text=True)

    def test_wcag_aa_red_on_black_normal_text(self):
        """Test WCAG AA compliance for red on black (normal text)."""
        # Pure red should meet 5.3:1 ratio
        assert is_wcag_aa_compliant((255, 0, 0), (0, 0, 0), large_text=False)

    def test_high_contrast_palette_has_all_colors(self):
        """Test that high contrast palette has all required colors."""
        required_colors = [
            "background",
            "text",
            "gold",
            "gold_dim",
            "error_red",
            "scrollbar",
            "bubble_bg",
            "bubble_border",
        ]
        for color in required_colors:
            assert color in HIGH_CONTRAST_COLORS

    def test_standard_palette_has_all_colors(self):
        """Test that standard palette has all required colors."""
        required_colors = [
            "background",
            "text",
            "gold",
            "gold_dim",
            "error_red",
            "scrollbar",
            "bubble_bg",
            "bubble_border",
        ]
        for color in required_colors:
            assert color in STANDARD_COLORS

    def test_high_contrast_background_is_black(self):
        """Test that high contrast background is black."""
        assert HIGH_CONTRAST_COLORS["background"] == (0, 0, 0)

    def test_high_contrast_text_is_white(self):
        """Test that high contrast text is white."""
        assert HIGH_CONTRAST_COLORS["text"] == (255, 255, 255)

    def test_contrast_ratio_calculation_symmetry(self):
        """Test that contrast ratio is symmetric."""
        ratio1 = verify_contrast_ratio((255, 255, 255), (0, 0, 0))
        ratio2 = verify_contrast_ratio((0, 0, 0), (255, 255, 255))
        assert ratio1 == pytest.approx(ratio2, rel=0.01)
