"""Settings persistence manager for Kourai Khryseai GUI.

Handles loading and saving user preferences to a JSON configuration file.
Supports all settings defined in the Settings data model with sensible defaults.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default settings values
DEFAULT_SETTINGS = {
    "typewriter_speed_ms": 30,
    "typewriter_enabled": True,
    "auto_scroll_enabled": True,
    "flash_effect_enabled": True,
    "font_scale": 1.0,
    "high_contrast": False,
    "timestamp_format": "24h",
    "show_timestamps": True,
    "show_metadata": True,
    "show_debug_logs": False,
    "reduce_motion": False,
    "fullscreen": False,
    "display_mode": "Windowed",
    "music_volume": 0.05,
    "ambient_volume": 0.10,
    "voice_volume": 1.0,
    "sfx_volume": 0.85,
}


class SettingsManager:
    """Manages settings persistence using JSON configuration file.

    Loads settings from a JSON config file on initialization, provides get/set
    methods for all settings, and persists changes to file. Handles file I/O
    errors gracefully and uses sensible defaults when settings file doesn't exist.
    """

    def __init__(self, config_path: Path | str) -> None:
        """Initialize SettingsManager with config file path.

        Args:
            config_path: Path to the JSON configuration file.
        """
        self.config_path = Path(config_path)
        self.settings: dict[str, Any] = DEFAULT_SETTINGS.copy()
        self._load()

    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value.

        Args:
            key: Setting key to retrieve.
            default: Default value if key not found.

        Returns:
            Setting value or default if not found.
        """
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set setting value.

        Args:
            key: Setting key to set.
            value: Value to set.
        """
        self.settings[key] = value

    def save(self) -> None:
        """Save settings to file.

        Persists current settings to JSON file. Creates parent directories
        if they don't exist. Handles file I/O errors gracefully.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except OSError as e:
            # Gracefully handle file I/O errors
            logger.warning(f"Failed to save settings to {self.config_path}: {e}")

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        self.settings = DEFAULT_SETTINGS.copy()
        self.save()

    def _load(self) -> None:
        """Load settings from file.

        Loads settings from JSON file if it exists. If file doesn't exist,
        uses default settings. Handles file I/O errors gracefully.
        """
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                loaded = json.load(f)
                if "display_mode" not in loaded and loaded.get("fullscreen") is True:
                    loaded["display_mode"] = "Fullscreen"
                    logger.debug(
                        "Migrated legacy fullscreen setting to display_mode=Fullscreen for %s",
                        self.config_path,
                    )
                # Merge loaded settings with defaults to handle new settings
                self.settings.update(loaded)
        except (OSError, json.JSONDecodeError) as e:
            # Gracefully handle file I/O and JSON parsing errors
            logger.warning(f"Failed to load settings from {self.config_path}: {e}")
            # Keep default settings
