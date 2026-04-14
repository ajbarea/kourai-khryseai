"""Persistent settings for the CLI host.

Stores toggles for voice, music, romance, and other features in a local JSON file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Settings file location: project_root/.cache/cli_settings.json
_SETTINGS_FILE = Path(__file__).resolve().parents[2] / ".cache" / "cli_settings.json"


@dataclass
class CLISettings:
    """CLI host feature toggles."""

    voice_enabled: bool = True
    music_enabled: bool = True
    romance_enabled: bool = False
    gossip_enabled: bool = False
    ambient_enabled: bool = True
    metrics_tracking_enabled: bool = True
    romance_nudges_enabled: bool = True
    gossip_nudges_enabled: bool = True

    def save(self) -> None:
        """Persist settings to disk."""
        try:
            _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _SETTINGS_FILE.open("w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            logger.error("Failed to save CLI settings: %s", e)

    @classmethod
    def load(cls) -> CLISettings:
        """Load settings from disk, falling back to defaults."""
        if not _SETTINGS_FILE.exists():
            return cls()
        try:
            with _SETTINGS_FILE.open(encoding="utf-8") as f:
                data = json.load(f)
                return cls(**data)
        except Exception as e:
            logger.warning("Failed to load CLI settings, using defaults: %s", e)
            return cls()

    def toggle(self, key: str) -> bool:
        """Toggle a boolean setting and save. Returns the new value."""
        if not hasattr(self, key):
            raise AttributeError(f"Unknown setting: {key}")

        current = getattr(self, key)
        setattr(self, key, not current)
        self.save()
        return getattr(self, key)
