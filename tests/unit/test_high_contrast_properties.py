"""Property-based tests for High Contrast Mode using Hypothesis."""

from hypothesis import given, settings, strategies as st

from hosts.gui.high_contrast_colors import (
    get_color_palette,
    is_wcag_aa_compliant,
    verify_contrast_ratio,
)


# Feature: gui-improvements, Property 12: High Contrast Mode Accessibility
class TestHighContrastAccessibilityProperty:
    """Property-based tests for high contrast mode accessibility."""

    @given(
        bg_name=st.sampled_from(
            [
                "background",
                "bubble_bg",
                "user_bubble_bg",
                "result_bubble_bg",
                "error_bubble_bg",
            ]
        ),
        text_name=st.sampled_from(["text", "gold", "gold_dim", "error_red", "bubble_border"]),
    )
    @settings(max_examples=100)
    def test_high_contrast_ratios(self, bg_name, text_name):
        """Property: High contrast mode contrast ratio meets WCAG 2.2 Level AA standards."""
        palette = get_color_palette(high_contrast=True)

        bg_color = palette[bg_name]
        text_color = palette[text_name]

        valid_pairs = [
            ("text", "background"),
            ("gold", "bubble_bg"),
            ("gold_dim", "user_bubble_bg"),
            ("text", "user_bubble_bg"),
            ("text", "result_bubble_bg"),
            ("text", "error_bubble_bg"),
            ("error_red", "error_bubble_bg"),
        ]

        if (text_name, bg_name) in valid_pairs:
            ratio = verify_contrast_ratio(text_color, bg_color)
            is_compliant = is_wcag_aa_compliant(text_color, bg_color, large_text=False)

            assert ratio >= 4.5, f"Contrast ratio for {text_name} on {bg_name} is {ratio} < 4.5"
            assert is_compliant is True
