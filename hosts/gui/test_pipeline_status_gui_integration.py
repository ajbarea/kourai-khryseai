"""Tests for PipelineStatusIndicator GUI integration."""

from unittest.mock import Mock

from pipeline_status_gui_integration import PipelineStatusGUIIntegration


class TestPipelineStatusGUIIntegration:
    """Test PipelineStatusIndicator GUI integration."""

    def test_initialization(self):
        """Test initialization of integration."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        assert integration.gui is mock_gui
        assert integration.indicator is not None

    def test_update_current_agent(self):
        """Test updating current agent."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        integration.update_current_agent("Hephaestus")
        assert integration.get_current_agent() == "Hephaestus"

    def test_add_agent_to_queue(self):
        """Test adding agent to queue."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        integration.add_agent_to_queue("Metis")
        assert "Metis" in integration.get_processing_queue()

    def test_remove_agent_from_queue(self):
        """Test removing agent from queue."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        integration.add_agent_to_queue("Metis")
        integration.remove_agent_from_queue("Metis")
        assert "Metis" not in integration.get_processing_queue()

    def test_set_loading_state(self):
        """Test setting loading state."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        assert integration.is_loading() is False
        integration.set_loading_state(True)
        assert integration.is_loading() is True

    def test_get_processing_queue(self):
        """Test getting processing queue."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        integration.add_agent_to_queue("Hephaestus")
        integration.add_agent_to_queue("Metis")
        queue = integration.get_processing_queue()
        assert len(queue) == 2
        assert "Hephaestus" in queue
        assert "Metis" in queue

    def test_clear_pipeline(self):
        """Test clearing the pipeline."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        integration.update_current_agent("Hephaestus")
        integration.add_agent_to_queue("Metis")
        integration.clear_pipeline()
        assert integration.get_current_agent() == ""
        assert len(integration.get_processing_queue()) == 0

    def test_get_indicator(self):
        """Test getting indicator instance."""
        mock_gui = Mock()
        integration = PipelineStatusGUIIntegration(mock_gui)
        indicator = integration.get_indicator()
        assert indicator is integration.indicator
