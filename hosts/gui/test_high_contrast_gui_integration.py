"""Tests for high contrast GUI integration."""

from unittest.mock import Mock

from high_contrast_gui_integration import HighContrastGUIIntegration


class TestHighContrastGUIIntegration:
    """Test high contrast GUI integration."""

    def test_initialization(self):
        """Test initialization of high contrast integration."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        assert integration.gui is mock_gui
        assert integration.settings is mock_settings
        assert integration.high_contrast_enabled is False

    def test_enable_high_contrast(self):
        """Test enabling high contrast mode."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        integration.enable_high_contrast()

        assert integration.high_contrast_enabled is True
        mock_settings.set.assert_called_with("high_contrast", True)
        mock_settings.save.assert_called_once()

    def test_disable_high_contrast(self):
        """Test disabling high contrast mode."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = True

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        integration.high_contrast_enabled = True
        integration.disable_high_contrast()

        assert integration.high_contrast_enabled is False
        mock_settings.set.assert_called_with("high_contrast", False)
        mock_settings.save.assert_called_once()

    def test_toggle_high_contrast_enable(self):
        """Test toggling high contrast mode (enable)."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        integration.toggle_high_contrast()

        assert integration.high_contrast_enabled is True

    def test_toggle_high_contrast_disable(self):
        """Test toggling high contrast mode (disable)."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = True

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        integration.high_contrast_enabled = True
        integration.toggle_high_contrast()

        assert integration.high_contrast_enabled is False

    def test_is_high_contrast_enabled(self):
        """Test checking if high contrast is enabled."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        assert integration.is_high_contrast_enabled() is False

        integration.high_contrast_enabled = True
        assert integration.is_high_contrast_enabled() is True

    def test_get_color_palette_standard(self):
        """Test getting standard color palette."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        palette = integration.get_color_palette()

        assert "background" in palette
        assert "text" in palette
        assert palette["background"] == (18, 10, 8)

    def test_get_color_palette_high_contrast(self):
        """Test getting high contrast color palette."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = True

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        integration.high_contrast_enabled = True
        palette = integration.get_color_palette()

        assert "background" in palette
        assert "text" in palette
        assert palette["background"] == (0, 0, 0)

    def test_get_color_standard(self):
        """Test getting specific color in standard mode."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        color = integration.get_color("gold")

        assert color == (218, 165, 32)

    def test_get_color_high_contrast(self):
        """Test getting specific color in high contrast mode."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = True

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        integration.high_contrast_enabled = True
        color = integration.get_color("gold")

        assert color == (255, 200, 0)

    def test_verify_wcag_compliance_white_on_black(self):
        """Test WCAG compliance verification."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        assert integration.verify_wcag_compliance((255, 255, 255), (0, 0, 0))

    def test_verify_wcag_compliance_large_text(self):
        """Test WCAG compliance verification for large text."""
        mock_gui = Mock()
        mock_settings = Mock()
        mock_settings.get.return_value = False

        integration = HighContrastGUIIntegration(mock_gui, mock_settings)
        assert integration.verify_wcag_compliance((255, 200, 0), (0, 0, 0), large_text=True)
