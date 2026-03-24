"""Backwards-compatibility shim — settings_ui split into focused modules.

All implementation has moved to:

    settings_widgets.py — TabButton, VolumeSlider, ToggleSwitch, Button, CycleButton,
                          _ensure_freetype_ready
    settings_overlay.py — SettingsOverlay

Callers importing from hosts.gui.settings_ui continue to work unchanged.
"""

from hosts.gui.settings_overlay import SettingsOverlay
from hosts.gui.settings_widgets import (
    Button,
    CycleButton,
    TabButton,
    ToggleSwitch,
    VolumeSlider,
)

__all__ = [
    "Button",
    "CycleButton",
    "SettingsOverlay",
    "TabButton",
    "ToggleSwitch",
    "VolumeSlider",
]
