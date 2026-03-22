"""Theme manager — alignment-based visual theming.

Extracted from __main__.py Phase 18. Handles periodic alignment
profile refresh and palette computation/application. High-contrast
mode bypasses alignment palette entirely.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .alignment_theme import compute_alignment_palette

if TYPE_CHECKING:
    from .alignment_gauges import AlignmentGaugePanel
    from .constants import Theme
    from .gui_components_integration import GUIComponentsIntegration

logger = logging.getLogger(__name__)


class ThemeManager:
    """Refreshes alignment-based theme palette on a timer."""

    def __init__(
        self,
        alignment_panel: AlignmentGaugePanel,
        gui_integration: GUIComponentsIntegration,
        theme: Theme,
    ) -> None:
        self.alignment_panel = alignment_panel
        self.gui_integration = gui_integration
        self.theme = theme
        self._refresh_timer: float = 0.0

    def update(self, dt: float) -> None:
        """Refresh alignment-based theming every 10s."""
        try:
            if not self.gui_integration.settings.get("high_contrast", False):
                self._refresh_timer += dt
                if self._refresh_timer >= 10.0:
                    self._refresh_timer = 0.0
                    self._reload_profile_alignment()
                alignment_palette = compute_alignment_palette(
                    self.alignment_panel.sovereignty, self.alignment_panel.devotion
                )
                self.theme.apply_palette(alignment_palette)
            else:
                self.theme.apply_palette(self.gui_integration.high_contrast.get_color_palette())
        except Exception as e:
            logger.exception("Error updating theme: %s", e)

    def _reload_profile_alignment(self) -> None:
        """Reload alignment values from the player profile."""
        try:
            from kourai_common.player import PlayerProfile

            prof = PlayerProfile.load()
            if prof:
                self.alignment_panel.update_values(prof.sovereignty, prof.devotion, prof.role)
        except Exception:
            logger.debug("Periodic alignment sync failed")
