"""Tests for GUI components integration."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from gui_components_integration import GUIComponentsIntegration


class TestGUIComponentsIntegration:
    """Test GUI components integration."""

    def test_initialization(self):
        """Test initialization of GUI components integration."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            assert integration.gui is mock_gui
            assert integration.settings is not None
            assert integration.font_scaler is not None
            assert integration.status_bubbles is not None
            assert integration.pipeline_status is not None
            assert integration.high_contrast is not None
            assert integration.agent_personalities is not None
            assert integration.agent_handoff is not None

    def test_get_settings_manager(self):
        """Test getting settings manager."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            settings = integration.get_settings_manager()
            assert settings is integration.settings

    def test_get_font_scaler(self):
        """Test getting font scaler."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            scaler = integration.get_font_scaler()
            assert scaler is integration.font_scaler

    def test_get_status_bubbles(self):
        """Test getting status bubbles."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            bubbles = integration.get_status_bubbles()
            assert bubbles is integration.status_bubbles

    def test_get_pipeline_status(self):
        """Test getting pipeline status."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            pipeline = integration.get_pipeline_status()
            assert pipeline is integration.pipeline_status

    def test_get_high_contrast(self):
        """Test getting high contrast integration."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            hc = integration.get_high_contrast()
            assert hc is integration.high_contrast

    def test_get_agent_personalities(self):
        """Test getting agent personalities."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            personalities = integration.get_agent_personalities()
            assert personalities is integration.agent_personalities

    def test_get_agent_handoff(self):
        """Test getting agent handoff integration."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            handoff = integration.get_agent_handoff()
            assert handoff is integration.agent_handoff

    def test_update(self):
        """Test updating all components."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            # Should not raise an error
            integration.update(0.016)

    def test_save_all_settings(self):
        """Test saving all settings."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"
            integration = GUIComponentsIntegration(mock_gui, config_path)

            # Should not raise an error
            integration.save_all_settings()

            # Settings file should exist
            assert config_path.exists()

    def test_load_settings_font_scale(self):
        """Test loading font scale settings."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Create integration and set font scale
            integration = GUIComponentsIntegration(mock_gui, config_path)
            integration.font_scaler.set_scale(1.5)
            integration.save_all_settings()

            # Create new integration and check if font scale is loaded
            integration2 = GUIComponentsIntegration(mock_gui, config_path)
            assert integration2.font_scaler.scale == 1.5

    def test_load_settings_high_contrast(self):
        """Test loading high contrast settings."""
        mock_gui = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "settings.json"

            # Create integration and enable high contrast
            integration = GUIComponentsIntegration(mock_gui, config_path)
            integration.high_contrast.enable_high_contrast()
            integration.save_all_settings()

            # Create new integration and check if high contrast is loaded
            integration2 = GUIComponentsIntegration(mock_gui, config_path)
            assert integration2.high_contrast.is_high_contrast_enabled()

    def test_default_config_path(self):
        """Test default config path."""
        mock_gui = Mock()
        integration = GUIComponentsIntegration(mock_gui)

        # Should have a valid settings manager
        assert integration.settings is not None
