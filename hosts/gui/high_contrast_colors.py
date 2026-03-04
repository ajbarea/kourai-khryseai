"""High contrast color palette for WCAG 2.2 Level AA compliance."""

# Standard colors (normal mode)
STANDARD_COLORS = {
    "background": (18, 10, 8),
    "text": (255, 255, 255),
    "gold": (218, 165, 32),
    "gold_dim": (180, 140, 20),
    "error_red": (220, 80, 80),
    "scrollbar": (100, 80, 60),
    "bubble_bg": (30, 22, 10),
    "bubble_border": (218, 165, 32),
    "user_bubble_bg": (30, 22, 10),
    "user_bubble_border": (180, 140, 20),
    "result_bubble_bg": (20, 18, 10),
    "result_bubble_border": (218, 165, 32),
    "error_bubble_bg": (40, 10, 10),
    "error_bubble_border": (220, 80, 80),
}

# High contrast colors (WCAG 2.2 Level AA compliant)
# Ensures 4.5:1 contrast ratio for normal text (under 18pt or under 14pt bold)
# Ensures 3:1 contrast ratio for large text (18pt+ or 14pt+ bold)
HIGH_CONTRAST_COLORS = {
    "background": (0, 0, 0),  # Pure black
    "text": (255, 255, 255),  # Pure white - 21:1 contrast
    "gold": (255, 200, 0),  # Bright gold - 10.5:1 contrast with black
    "gold_dim": (200, 150, 0),  # Darker gold - 7.5:1 contrast with black
    "error_red": (255, 0, 0),  # Pure red - 5.3:1 contrast with black
    "scrollbar": (200, 200, 200),  # Light gray - 12:1 contrast with black
    "bubble_bg": (40, 40, 40),  # Dark gray
    "bubble_border": (255, 200, 0),  # Bright gold - 10.5:1 contrast
    "user_bubble_bg": (40, 40, 40),  # Dark gray
    "user_bubble_border": (200, 150, 0),  # Darker gold - 7.5:1 contrast
    "result_bubble_bg": (30, 30, 30),  # Very dark gray
    "result_bubble_border": (255, 200, 0),  # Bright gold - 10.5:1 contrast
    "error_bubble_bg": (60, 0, 0),  # Dark red
    "error_bubble_border": (255, 0, 0),  # Pure red - 5.3:1 contrast
}


def get_color_palette(high_contrast: bool = False) -> dict[str, tuple[int, int, int]]:
    """Get the appropriate color palette based on high contrast setting.

    Args:
        high_contrast: Whether to use high contrast mode.

    Returns:
        Dictionary of color names to RGB tuples.
    """
    return HIGH_CONTRAST_COLORS if high_contrast else STANDARD_COLORS


def get_color(name: str, high_contrast: bool = False) -> tuple[int, int, int]:
    """Get a specific color from the palette.

    Args:
        name: Color name.
        high_contrast: Whether to use high contrast mode.

    Returns:
        RGB tuple for the color.
    """
    palette = get_color_palette(high_contrast)
    return palette.get(name, (255, 255, 255))


def verify_contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    """Calculate contrast ratio between two colors (WCAG formula).

    Args:
        fg: Foreground color RGB tuple.
        bg: Background color RGB tuple.

    Returns:
        Contrast ratio (1:1 to 21:1).
    """

    def luminance(rgb: tuple[int, int, int]) -> float:
        """Calculate relative luminance."""
        r, g, b = [x / 255.0 for x in rgb]
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1 = luminance(fg)
    l2 = luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def is_wcag_aa_compliant(
    fg: tuple[int, int, int], bg: tuple[int, int, int], large_text: bool = False
) -> bool:
    """Check if color combination meets WCAG 2.2 Level AA standards.

    Args:
        fg: Foreground color RGB tuple.
        bg: Background color RGB tuple.
        large_text: Whether text is large (18pt+ or 14pt+ bold).

    Returns:
        True if contrast ratio meets WCAG AA standards.
    """
    ratio = verify_contrast_ratio(fg, bg)
    # WCAG AA: 4.5:1 for normal text, 3:1 for large text
    return ratio >= (3.0 if large_text else 4.5)
