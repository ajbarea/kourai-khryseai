"""Dynamic layout metrics for the Kourai GUI.

Replaces hardcoded geometric constants with a LayoutMetrics dataclass
computed from the current screen size and font scale.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutMetrics:
    w: int
    h: int
    font_scale: float

    @property
    def portrait_w(self) -> int:
        return max(200, int(310 * self.font_scale))

    @property
    def dialogue_x(self) -> int:
        return self.portrait_w + 8

    @property
    def dialogue_w(self) -> int:
        return self.w - self.portrait_w - 8

    @property
    def input_h(self) -> int:
        return max(60, int(80 * self.font_scale))

    @property
    def dialogue_h(self) -> int:
        return self.h - self.input_h

    @property
    def banner_h(self) -> int:
        return max(24, int(32 * self.font_scale))

    @property
    def banner_border_h(self) -> int:
        return max(1, int(self.font_scale))

    @property
    def banner_total_h(self) -> int:
        return self.banner_h + self.banner_border_h

    @property
    def scroll_chrome_h(self) -> int:
        return max(40, int(60 * self.font_scale))


current_layout = LayoutMetrics(w=1280, h=720, font_scale=1.0)


def sync_layout(w: int, h: int, scale: float) -> None:
    """Update the global layout metrics when the window resizes or zoom changes."""
    global current_layout
    current_layout = LayoutMetrics(w=w, h=h, font_scale=scale)
