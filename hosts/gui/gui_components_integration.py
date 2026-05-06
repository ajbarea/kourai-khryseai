"""Aggregator for live GUI component integrations.

Holds the components that are actually wired into the render / event /
settings paths. Historically also held a stratum of staged-but-unwired
classes (status bubbles, pipeline indicator, scratchpad, agent
personality indicators); those were pruned because their integration
shims had been instantiated but never called from any rendering or
logic path. The shared rebuilds for those features are filed under
ROADMAP and will land alongside their renderers, not ahead of them.
"""

from __future__ import annotations

from pathlib import Path

from .font_scaler import FontScaler
from .high_contrast_gui_integration import HighContrastGUIIntegration
from .settings import SettingsManager


class GUIComponentsIntegration:
    """Manages integration of all live GUI components."""

    def __init__(self, gui_instance, config_path: Path | str | None = None):
        """Initialize the live GUI components.

        Args:
            gui_instance: The main GUI instance.
            config_path: Path to settings configuration file.
        """
        self.gui = gui_instance

        if config_path is None:
            config_path = Path.home() / ".kourai_khryseai" / "settings.json"
        self.settings = SettingsManager(config_path)

        self.font_scaler = FontScaler()
        self.high_contrast = HighContrastGUIIntegration(gui_instance, self.settings)

        self._load_settings()

    def _load_settings(self) -> None:
        """Load settings into the live components."""
        # Font scaling — also push into constants.FontProxy registry so every
        # cached font rebuilds at the saved size on next render.
        from .constants import set_font_scale as _push_font_scale

        font_scale = self.settings.get("font_scale", 1.0)
        self.font_scaler.set_scale(font_scale)
        _push_font_scale(self.font_scaler.scale)

        high_contrast = self.settings.get("high_contrast", False)
        if high_contrast:
            self.high_contrast.enable_high_contrast()

    def save_all_settings(self) -> None:
        """Persist live-component state through SettingsManager."""
        self.settings.set("font_scale", self.font_scaler.scale)
        self.settings.set("high_contrast", self.high_contrast.is_high_contrast_enabled())
        self.settings.set("show_debug_logs", self.settings.get("show_debug_logs", False))
        self.settings.save()

    def get_settings_manager(self) -> SettingsManager:
        return self.settings

    def get_font_scaler(self) -> FontScaler:
        return self.font_scaler

    def get_high_contrast(self) -> HighContrastGUIIntegration:
        return self.high_contrast
