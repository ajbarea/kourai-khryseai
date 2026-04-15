"""Tests for StatusBubbles GUI integration."""

from unittest.mock import Mock

from hosts.gui.status_bubbles_gui_integration import StatusBubblesGUIIntegration


class TestStatusBubblesGUIIntegration:
    """Test StatusBubbles GUI integration."""

    def test_initialization(self):
        """Test initialization of integration."""
        mock_gui = Mock()
        integration = StatusBubblesGUIIntegration(mock_gui)
        assert integration.gui is mock_gui
        assert integration.status_bubbles is not None

    def test_add_status_message(self):
        """Test adding status messages."""
        mock_gui = Mock()
        integration = StatusBubblesGUIIntegration(mock_gui)
        integration.add_status_message("Test status")
        assert len(integration.status_bubbles.get_content()) == 1

    def test_get_status_bubbles(self):
        """Test getting status bubbles instance."""
        mock_gui = Mock()
        integration = StatusBubblesGUIIntegration(mock_gui)
        bubbles = integration.get_status_bubbles()
        assert bubbles is integration.status_bubbles

    def test_clear_all_status(self):
        """Test clearing all status messages."""
        mock_gui = Mock()
        integration = StatusBubblesGUIIntegration(mock_gui)
        integration.add_status_message("Status 1")
        integration.add_status_message("Status 2")
        integration.status_bubbles.clear_status()
        assert len(integration.status_bubbles.get_content()) == 0
