"""TTS settings persistence and configuration.

Handles saving/loading TTS preferences to JSON config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from .dialogue_pacing import PacingMode

if TYPE_CHECKING:
    from .tts_gui_integration import TTSGUIManager


class TTSSettingsConfig:
    """Manages TTS settings persistence."""

    DEFAULT_CONFIG: ClassVar[dict[str, Any]] = {
        "tts_enabled": True,
        "pacing_mode": "NORMAL",
        "thinking_pause_enabled": True,
        "thinking_pause_duration": 0.5,
        "min_chars_per_second": 50.0,
        # M20 sub-task 4 — dialogue/audio sync mode.
        # "audio-led" (default): word-paced typewriter advances on TTS
        #   on_word events, text reveals in lockstep with audio.
        # "instant": legacy time-based typewriter, text appears at its
        #   own pace and audio catches up.
        "dialogue_sync_mode": "audio-led",
    }

    def __init__(self, config_path: Path | None = None):
        """Initialize settings config.

        Args:
            config_path: Path to settings JSON file. Uses default if None.
        """
        self.config_path = config_path or Path.home() / ".kourai" / "tts_settings.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self._load()

    def _load(self) -> dict[str, Any]:
        """Load settings from file or use defaults."""
        if self.config_path.exists():
            try:
                with self.config_path.open() as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return self.DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Save current settings to file."""
        with self.config_path.open("w") as f:
            json.dump(self.settings, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        self.settings[key] = value

    def apply_to_manager(self, manager: TTSGUIManager) -> None:
        """Apply saved settings to a TTS manager.

        Args:
            manager: TTSGUIManager instance to configure.
        """
        # TTS enabled
        if "tts_enabled" in self.settings:
            manager.set_tts_enabled(self.settings["tts_enabled"])

        # Pacing mode
        if "pacing_mode" in self.settings:
            try:
                mode = PacingMode[self.settings["pacing_mode"]]
                manager.set_pacing_mode(mode)
            except KeyError:
                pass

        # Thinking pause
        if "thinking_pause_enabled" in self.settings:
            enabled = self.settings["thinking_pause_enabled"]
            duration = self.settings.get("thinking_pause_duration", 0.5)
            manager.pacer.set_thinking_pause(enabled, duration)

        # Reading speed
        if "min_chars_per_second" in self.settings:
            manager.pacer.config.min_chars_per_second = self.settings["min_chars_per_second"]

        # M20 sub-task 4 — dialogue sync mode (audio-led | instant)
        if "dialogue_sync_mode" in self.settings:
            manager.dialogue_sync_mode = self.settings["dialogue_sync_mode"]

    def update_from_manager(self, manager: TTSGUIManager) -> None:
        """Update settings from current manager state.

        Args:
            manager: TTSGUIManager instance to read from.
        """
        self.settings["tts_enabled"] = manager.enable_tts
        self.settings["pacing_mode"] = manager.pacer.config.mode.name
        self.settings["thinking_pause_enabled"] = manager.pacer.config.enable_thinking_pause
        self.settings["thinking_pause_duration"] = manager.pacer.config.thinking_pause_duration
        self.settings["min_chars_per_second"] = manager.pacer.config.min_chars_per_second
        self.settings["dialogue_sync_mode"] = getattr(manager, "dialogue_sync_mode", "audio-led")

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.settings = self.DEFAULT_CONFIG.copy()
        self.save()


# ============================================================================
# Usage Example
# ============================================================================
"""
In your main() function:

    # Load settings
    tts_config = TTSSettingsConfig()

    # Create manager
    tts_manager = TTSGUIManager(recv_q, enable_tts=True)

    # Apply saved settings
    tts_config.apply_to_manager(tts_manager)

    # ... main loop ...

    # When user changes settings:
    tts_manager.set_pacing_mode(PacingMode.SLOW)

    # Save settings on exit
    tts_config.update_from_manager(tts_manager)
    tts_config.save()
"""
