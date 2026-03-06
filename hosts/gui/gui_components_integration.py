"""Integration of all GUI components for the Kourai Khryseai GUI."""

from pathlib import Path

from .agent_handoff_personality_integration import AgentHandoffPersonalityIntegration
from .agent_personality_indicators import AgentPersonalityIndicators
from .font_scaler import FontScaler
from .high_contrast_gui_integration import HighContrastGUIIntegration
from .pipeline_status_gui_integration import PipelineStatusGUIIntegration
from .scratchpad_gui_integration import ScratchpadGUIIntegration
from .settings import SettingsManager
from .status_bubbles_gui_integration import StatusBubblesGUIIntegration


class GUIComponentsIntegration:
    """Manages integration of all GUI components."""

    def __init__(self, gui_instance, config_path: Path | str | None = None):
        """Initialize all GUI components.

        Args:
            gui_instance: The main GUI instance.
            config_path: Path to settings configuration file.
        """
        self.gui = gui_instance

        # Initialize settings manager
        if config_path is None:
            config_path = Path.home() / ".kourai_khryseai" / "settings.json"
        self.settings = SettingsManager(config_path)

        # Initialize core components
        self.font_scaler = FontScaler()
        self.status_bubbles = StatusBubblesGUIIntegration(gui_instance)
        self.pipeline_status = PipelineStatusGUIIntegration(gui_instance)
        self.scratchpad = ScratchpadGUIIntegration(gui_instance)
        self.high_contrast = HighContrastGUIIntegration(gui_instance, self.settings)
        self.agent_personalities = AgentPersonalityIndicators()
        self.agent_handoff = AgentHandoffPersonalityIntegration(
            gui_instance, self.agent_personalities
        )

        # Load settings
        self._load_settings()

    def _load_settings(self) -> None:
        """Load all settings from settings manager."""
        # Font scaling
        font_scale = self.settings.get("font_scale", 1.0)
        self.font_scaler.set_scale(font_scale)

        # High contrast
        high_contrast = self.settings.get("high_contrast", False)
        if high_contrast:
            self.high_contrast.enable_high_contrast()

    def save_all_settings(self) -> None:
        """Save all settings to file."""
        self.settings.set("font_scale", self.font_scaler.scale)
        self.settings.set("high_contrast", self.high_contrast.is_high_contrast_enabled())
        self.settings.set("show_debug_logs", self.settings.get("show_debug_logs", False))
        self.settings.save()

    def get_settings_manager(self) -> SettingsManager:
        """Get the settings manager."""
        return self.settings

    def get_font_scaler(self) -> FontScaler:
        """Get the font scaler."""
        return self.font_scaler

    def get_status_bubbles(self) -> StatusBubblesGUIIntegration:
        """Get the status bubbles integration."""
        return self.status_bubbles

    def get_pipeline_status(self) -> PipelineStatusGUIIntegration:
        """Get the pipeline status integration."""
        return self.pipeline_status

    def get_scratchpad(self) -> ScratchpadGUIIntegration:
        """Get the scratchpad integration."""
        return self.scratchpad

    def get_high_contrast(self) -> HighContrastGUIIntegration:
        """Get the high contrast integration."""
        return self.high_contrast

    def get_agent_personalities(self) -> AgentPersonalityIndicators:
        """Get the agent personality indicators."""
        return self.agent_personalities

    def get_agent_handoff(self) -> AgentHandoffPersonalityIntegration:
        """Get the agent handoff personality integration."""
        return self.agent_handoff
