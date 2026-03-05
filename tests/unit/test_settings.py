"""Unit tests for SettingsManager class."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hosts.gui.settings import DEFAULT_SETTINGS, SettingsManager


class TestSettingsManagerBasic:
    """Test basic SettingsManager functionality."""

    def test_init_creates_default_settings(self) -> None:
        """Test that initialization creates default settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            # Verify all default settings are present
            for key, value in DEFAULT_SETTINGS.items():
                assert manager.get(key) == value

    def test_get_returns_default_when_key_not_found(self) -> None:
        """Test that get returns default value when key not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            assert manager.get("nonexistent_key", "default_value") == "default_value"
            assert manager.get("nonexistent_key") is None

    def test_set_updates_setting(self) -> None:
        """Test that set updates a setting value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.set("typewriter_speed_ms", 50)
            assert manager.get("typewriter_speed_ms") == 50

    def test_set_creates_new_setting(self) -> None:
        """Test that set can create new settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.set("custom_setting", "custom_value")
            assert manager.get("custom_setting") == "custom_value"


class TestSettingsManagerPersistence:
    """Test settings persistence to file."""

    def test_save_creates_config_file(self) -> None:
        """Test that save creates the config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.save()
            assert config_path.exists()

    def test_save_writes_json_format(self) -> None:
        """Test that save writes valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)
            manager.set("typewriter_speed_ms", 75)

            manager.save()

            with open(config_path) as f:
                data = json.load(f)

            assert data["typewriter_speed_ms"] == 75

    def test_load_restores_saved_settings(self) -> None:
        """Test that load restores previously saved settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Save settings
            manager1 = SettingsManager(config_path)
            manager1.set("typewriter_speed_ms", 60)
            manager1.set("font_scale", 1.5)
            manager1.save()

            # Load settings in new manager
            manager2 = SettingsManager(config_path)
            assert manager2.get("typewriter_speed_ms") == 60
            assert manager2.get("font_scale") == 1.5

    def test_load_uses_defaults_when_file_missing(self) -> None:
        """Test that load uses defaults when config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"
            manager = SettingsManager(config_path)

            # Should have default settings
            assert manager.get("typewriter_speed_ms") == DEFAULT_SETTINGS["typewriter_speed_ms"]

    def test_load_merges_with_defaults(self) -> None:
        """Test that load merges saved settings with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Save only some settings
            with open(config_path, "w") as f:
                json.dump({"typewriter_speed_ms": 80}, f)

            # Load should merge with defaults
            manager = SettingsManager(config_path)
            assert manager.get("typewriter_speed_ms") == 80
            assert manager.get("auto_scroll_enabled") == DEFAULT_SETTINGS["auto_scroll_enabled"]

    def test_save_creates_parent_directories(self) -> None:
        """Test that save creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "nested" / "settings.json"
            manager = SettingsManager(config_path)

            manager.save()
            assert config_path.exists()
            assert config_path.parent.exists()


class TestSettingsManagerErrorHandling:
    """Test error handling in SettingsManager."""

    def test_load_handles_invalid_json(self) -> None:
        """Test that load handles invalid JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Write invalid JSON
            with open(config_path, "w") as f:
                f.write("{ invalid json }")

            # Should not raise, should use defaults
            manager = SettingsManager(config_path)
            assert manager.get("typewriter_speed_ms") == DEFAULT_SETTINGS["typewriter_speed_ms"]

    def test_load_handles_missing_file(self) -> None:
        """Test that load handles missing file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"

            # Should not raise
            manager = SettingsManager(config_path)
            assert manager.get("typewriter_speed_ms") == DEFAULT_SETTINGS["typewriter_speed_ms"]

    def test_save_handles_permission_error(self) -> None:
        """Test that save handles permission errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            # Make directory read-only (Unix-like systems)
            import os
            import stat

            try:
                os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
                # Should not raise
                manager.save()
            finally:
                # Restore permissions for cleanup
                os.chmod(tmpdir, stat.S_IRWXU)


class TestSettingsManagerAllSettings:
    """Test all default settings are properly managed."""

    def test_all_default_settings_accessible(self) -> None:
        """Test that all default settings are accessible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            for key, value in DEFAULT_SETTINGS.items():
                assert manager.get(key) == value

    def test_modify_all_setting_types(self) -> None:
        """Test modifying settings of different types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            # Integer
            manager.set("typewriter_speed_ms", 100)
            assert manager.get("typewriter_speed_ms") == 100

            # Boolean
            manager.set("auto_scroll_enabled", False)
            assert manager.get("auto_scroll_enabled") is False

            # Float
            manager.set("font_scale", 2.0)
            assert manager.get("font_scale") == 2.0

            # String
            manager.set("timestamp_format", "12h")
            assert manager.get("timestamp_format") == "12h"

    def test_persist_all_setting_types(self) -> None:
        """Test persisting settings of different types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Save various types
            manager1 = SettingsManager(config_path)
            manager1.set("typewriter_speed_ms", 100)
            manager1.set("auto_scroll_enabled", False)
            manager1.set("font_scale", 2.0)
            manager1.set("timestamp_format", "12h")
            manager1.save()

            # Load and verify
            manager2 = SettingsManager(config_path)
            assert manager2.get("typewriter_speed_ms") == 100
            assert manager2.get("auto_scroll_enabled") is False
            assert manager2.get("font_scale") == 2.0
            assert manager2.get("timestamp_format") == "12h"


class TestSettingsManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_set_none_value(self) -> None:
        """Test setting a None value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.set("some_key", None)
            assert manager.get("some_key") is None

    def test_set_empty_string(self) -> None:
        """Test setting an empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.set("some_key", "")
            assert manager.get("some_key") == ""

    def test_set_zero_value(self) -> None:
        """Test setting zero value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.set("typewriter_speed_ms", 0)
            assert manager.get("typewriter_speed_ms") == 0

    def test_set_false_value(self) -> None:
        """Test setting False value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            manager.set("auto_scroll_enabled", False)
            assert manager.get("auto_scroll_enabled") is False

    def test_config_path_as_string(self) -> None:
        """Test that config_path can be provided as string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "settings.json")
            manager = SettingsManager(config_path)

            manager.set("typewriter_speed_ms", 50)
            manager.save()

            assert Path(config_path).exists()
