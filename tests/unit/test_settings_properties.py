"""Property-based tests for SettingsManager class.

Feature: gui-improvements, Property 10: Settings Persistence
Validates: Requirements 15.1, 15.2, 15.3, 15.4
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from hosts.gui.settings import DEFAULT_SETTINGS, SettingsManager

# Strategy for valid setting keys
setting_keys = st.sampled_from(list(DEFAULT_SETTINGS.keys()))

# Strategy for valid setting values (matching types in DEFAULT_SETTINGS)
setting_values = st.one_of(
    st.integers(min_value=0, max_value=1000),  # For speed settings
    st.booleans(),  # For boolean settings
    st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),  # For scale
    st.sampled_from(["12h", "24h"]),  # For timestamp format
)


class TestSettingsPersistenceProperty:
    """Property-based tests for settings persistence.

    Feature: gui-improvements, Property 10: Settings Persistence
    Validates: Requirements 15.1, 15.2, 15.3, 15.4
    """

    @given(key=setting_keys, value=setting_values)
    @settings(max_examples=100)
    def test_settings_persist_across_instances(self, key: str, value) -> None:
        """Property: Settings saved by one instance are restored by another.

        For any setting key and value, when saved by one SettingsManager instance,
        a new instance should restore the exact same value.

        Validates: Requirements 15.1, 15.2, 15.3, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Save setting with first instance
            manager1 = SettingsManager(config_path)
            manager1.set(key, value)
            manager1.save()

            # Load with second instance
            manager2 = SettingsManager(config_path)

            # Verify the setting was restored
            assert manager2.get(key) == value

    @given(
        settings_dict=st.dictionaries(
            keys=st.sampled_from(list(DEFAULT_SETTINGS.keys())),
            values=st.one_of(
                st.integers(min_value=0, max_value=1000),
                st.booleans(),
                st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(["12h", "24h"]),
            ),
            min_size=1,
            max_size=len(DEFAULT_SETTINGS),
        )
    )
    @settings(max_examples=100)
    def test_multiple_settings_persist(self, settings_dict: dict) -> None:
        """Property: Multiple settings persist correctly together.

        For any set of settings, when saved together, all should be restored
        correctly by a new instance.

        Validates: Requirements 15.1, 15.2, 15.3, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Save multiple settings
            manager1 = SettingsManager(config_path)
            for key, value in settings_dict.items():
                manager1.set(key, value)
            manager1.save()

            # Load with new instance
            manager2 = SettingsManager(config_path)

            # Verify all settings were restored
            for key, value in settings_dict.items():
                assert manager2.get(key) == value

    @given(key=setting_keys, value=setting_values)
    @settings(max_examples=100)
    def test_settings_file_is_valid_json(self, key: str, value) -> None:
        """Property: Saved settings file is always valid JSON.

        For any setting, the saved file should be valid JSON that can be
        parsed by a JSON parser.

        Validates: Requirements 15.1, 15.3
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            manager = SettingsManager(config_path)
            manager.set(key, value)
            manager.save()

            # Verify file is valid JSON
            with config_path.open() as f:
                data = json.load(f)

            # Verify the setting is in the file
            assert key in data
            assert data[key] == value

    @given(key=setting_keys, value=setting_values)
    @settings(max_examples=100)
    def test_defaults_preserved_for_unmodified_settings(self, key: str, value) -> None:
        """Property: Default settings are preserved for unmodified keys.

        For any modified setting, all other settings should retain their
        default values after save and load.

        Validates: Requirements 15.3, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Modify only one setting
            manager1 = SettingsManager(config_path)
            manager1.set(key, value)
            manager1.save()

            # Load with new instance
            manager2 = SettingsManager(config_path)

            # Verify modified setting
            assert manager2.get(key) == value

            # Verify all other settings have defaults
            for default_key, default_value in DEFAULT_SETTINGS.items():
                if default_key != key:
                    assert manager2.get(default_key) == default_value

    @given(key=setting_keys, value1=setting_values, value2=setting_values)
    @settings(max_examples=100)
    def test_settings_can_be_updated(self, key: str, value1, value2) -> None:
        """Property: Settings can be updated and changes persist.

        For any setting, when updated to a new value and saved, the new
        value should be restored on load.

        Validates: Requirements 15.1, 15.2, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Save first value
            manager1 = SettingsManager(config_path)
            manager1.set(key, value1)
            manager1.save()

            # Update to second value
            manager2 = SettingsManager(config_path)
            manager2.set(key, value2)
            manager2.save()

            # Load and verify second value
            manager3 = SettingsManager(config_path)
            assert manager3.get(key) == value2

    @given(key=setting_keys)
    @settings(max_examples=100)
    def test_get_with_default_parameter(self, key: str) -> None:
        """Property: get() with default parameter returns default for missing keys.

        For any key, when requesting a non-existent key with a default,
        the default should be returned.

        Validates: Requirements 15.3, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            manager = SettingsManager(config_path)

            # Request non-existent key with default
            default_value = "test_default"
            result = manager.get("nonexistent_key_xyz", default_value)

            assert result == default_value

    @given(
        settings_dict=st.dictionaries(
            keys=st.sampled_from(list(DEFAULT_SETTINGS.keys())),
            values=st.one_of(
                st.integers(min_value=0, max_value=1000),
                st.booleans(),
                st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(["12h", "24h"]),
            ),
            min_size=1,
            max_size=len(DEFAULT_SETTINGS),
        )
    )
    @settings(max_examples=100)
    def test_settings_survive_multiple_save_load_cycles(self, settings_dict: dict) -> None:
        """Property: Settings survive multiple save/load cycles.

        For any set of settings, after multiple save/load cycles, the
        settings should remain unchanged.

        Validates: Requirements 15.1, 15.2, 15.3, 15.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Initial save
            manager = SettingsManager(config_path)
            for key, value in settings_dict.items():
                manager.set(key, value)
            manager.save()

            # Multiple load/save cycles
            for _ in range(3):
                manager = SettingsManager(config_path)
                manager.save()

            # Final load and verify
            manager = SettingsManager(config_path)
            for key, value in settings_dict.items():
                assert manager.get(key) == value
