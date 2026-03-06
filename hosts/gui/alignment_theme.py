"""Alignment-based visual theming for Kourai Khryseai GUI.

Dynamically shifts the GUI color palette based on the player's
Sovereignty/Devotion alignment gauges. Creates visual feedback
that makes the player's choices feel impactful.

Palette shifts:
  - High Sovereignty → Crimson/dark gold (authoritative)
  - High Devotion → Rose-blue/soft gold (warm)
  - High Both (Commander) → Royal purple/gold (imperial)
  - Low Both (Professional) → Default neutral palette
"""

from __future__ import annotations


def _lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Linearly interpolate between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


# Default palette (neutral/professional)
_NEUTRAL = {
    "background": (12, 10, 8),
    "bubble_bg": (18, 14, 10),
    "gold": (218, 165, 32),
    "gold_dim": (140, 105, 20),
    "text": (240, 235, 225),
    "scrollbar": (160, 155, 145),
    "error_red": (200, 80, 60),
}

# Sovereignty-shifted palette (crimson/authority)
_SOVEREIGNTY = {
    "background": (16, 8, 8),
    "bubble_bg": (24, 12, 10),
    "gold": (220, 140, 40),
    "gold_dim": (160, 80, 30),
    "text": (245, 230, 220),
    "scrollbar": (170, 140, 130),
    "error_red": (220, 60, 50),
}

# Devotion-shifted palette (rose-blue/warmth)
_DEVOTION = {
    "background": (8, 10, 16),
    "bubble_bg": (12, 14, 22),
    "gold": (180, 170, 200),
    "gold_dim": (100, 110, 150),
    "text": (230, 235, 245),
    "scrollbar": (140, 150, 170),
    "error_red": (180, 80, 100),
}

# Commander palette (royal purple/gold)
_COMMANDER = {
    "background": (14, 8, 16),
    "bubble_bg": (20, 12, 22),
    "gold": (200, 160, 220),
    "gold_dim": (140, 100, 160),
    "text": (240, 235, 245),
    "scrollbar": (160, 150, 170),
    "error_red": (200, 70, 100),
}


def compute_alignment_palette(
    sovereignty: int,
    devotion: int,
) -> dict[str, tuple[int, int, int]]:
    """Compute a blended color palette based on alignment values.

    Args:
        sovereignty: Current sovereignty value (0-100).
        devotion: Current devotion value (0-100).

    Returns:
        A palette dict compatible with ``Theme.apply_palette()``.
    """
    sov_t = sovereignty / 100.0
    dev_t = devotion / 100.0

    # Determine dominant influence
    both_high = min(sov_t, dev_t)  # Commander blend factor
    sov_only = max(0.0, sov_t - both_high)
    dev_only = max(0.0, dev_t - both_high)

    # Start from neutral and blend toward each archetype
    result: dict[str, tuple[int, int, int]] = {}
    for key in _NEUTRAL:
        neutral = _NEUTRAL[key]
        color = neutral

        # Blend sovereignty influence
        if sov_only > 0.1:
            color = _lerp_color(color, _SOVEREIGNTY[key], sov_only * 0.7)

        # Blend devotion influence
        if dev_only > 0.1:
            color = _lerp_color(color, _DEVOTION[key], dev_only * 0.7)

        # Blend commander influence (overrides the above)
        if both_high > 0.3:
            commander_t = (both_high - 0.3) / 0.7  # Ramp from 30% alignment
            color = _lerp_color(color, _COMMANDER[key], commander_t * 0.8)

        result[key] = color

    return result
