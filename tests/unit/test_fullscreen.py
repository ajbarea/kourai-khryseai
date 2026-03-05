"""Test fullscreen toggle functionality."""

from pathlib import Path

import pytest

from hosts.gui.settings import DEFAULT_SETTINGS, SettingsManager


def test_fullscreen_default_setting():
    """Test that fullscreen defaults to False."""
    assert DEFAULT_SETTINGS["fullscreen"] is False


def test_fullscreen_setting_persistence(tmp_path):
    """Test that fullscreen setting persists to file."""
    config_file = tmp_path / "test_settings.json"
    settings = SettingsManager(config_file)

    # Initially False
    assert settings.get("fullscreen") is False

    # Set to True
    settings.set("fullscreen", True)
    settings.save()

    # Load in new instance
    settings2 = SettingsManager(config_file)
    assert settings2.get("fullscreen") is True


def test_fullscreen_toggle():
    """Test toggling fullscreen setting."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "settings.json"
        settings = SettingsManager(config_file)

        # Toggle on
        settings.set("fullscreen", True)
        assert settings.get("fullscreen") is True

        # Toggle off
        settings.set("fullscreen", False)
        assert settings.get("fullscreen") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
