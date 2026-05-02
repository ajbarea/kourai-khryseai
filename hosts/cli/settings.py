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
    # OFF + voice ON = audio-only mode (dialogue speaks but skips
    # the comms-window). voice OFF forces effective ON in streaming.
    captions_enabled: bool = True
    # Currently selected player project (project_id), or None for "no project".
    # When set, the REPL wraps each turn in a forge worktree session.
    active_project_id: str | None = None
    # Skip the M13 Forge Order Confirmation gate. Power-user opt-out for
    # iterative work where the read-back-then-confirm beat is friction.
    # Default OFF — the gate is the always-on contract of the forge.
    yolo_enabled: bool = False
    # Granular middle ground between full /yolo and the always-on gate:
    # when True, Hephaestus skips CONFIRM_ORDER for read-only / planning-only
    # pipelines (Metis-only, Mneme-only, CHAT) and still gates anything
    # that would touch disk (Techne / Kallos / Dokimasia). Inspired by
    # Cline + ClawCode's per-tool gating. Default OFF — matches the
    # always-on gate.
    auto_approve_reads: bool = False
    # Per-stream volume. Defaults mirror `hosts/gui/settings_overlay.py`'s
    # values so a player who learned the GUI sliders gets the same
    # baseline in the CLI. Granular controls — the binary on/off toggle
    # didn't let a too-loud stream be tamed without disabling it.
    music_volume: float = 0.65
    ambient_volume: float = 0.50
    voice_volume: float = 1.0
    sfx_volume: float = 0.85

    @classmethod
    def load(cls) -> CLISettings:
        """Load settings from disk, falling back to defaults.

        Forward-compatible: unknown keys in older settings.json files are
        dropped silently so a player upgrading mid-stream doesn't get a
        crash; missing keys for new fields fall back to dataclass
        defaults (which is how ``yolo_enabled`` lands on existing files).
        """
        if not _SETTINGS_FILE.exists():
            return cls()
        try:
            with _SETTINGS_FILE.open(encoding="utf-8") as f:
                data = json.load(f)
                known = {f.name for f in cls.__dataclass_fields__.values()}
                return cls(**{k: v for k, v in data.items() if k in known})
        except Exception as e:
            logger.warning("Failed to load CLI settings, using defaults: %s", e)
            return cls()

    def save(self) -> None:
        """Persist settings to disk."""
        try:
            _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _SETTINGS_FILE.open("w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            logger.error("Failed to save CLI settings: %s", e)

    def toggle(self, key: str) -> bool:
        """Toggle a boolean setting and save. Returns the new value."""
        if not hasattr(self, key):
            raise AttributeError(f"Unknown setting: {key}")

        current = getattr(self, key)
        setattr(self, key, not current)
        self.save()
        return getattr(self, key)

    def set_volume(self, key: str, value: float) -> float:
        """Set a ``*_volume`` setting (clamped to ``[0.0, 1.0]``) and save.

        Returns the clamped value. Raises ``AttributeError`` if ``key``
        isn't a known volume field — keeps callers honest when a typo
        would otherwise silently land on a different attribute.
        """
        if not key.endswith("_volume") or not hasattr(self, key):
            raise AttributeError(f"Unknown volume setting: {key}")
        clamped = max(0.0, min(1.0, float(value)))
        setattr(self, key, clamped)
        self.save()
        return clamped
