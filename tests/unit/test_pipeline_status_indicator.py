"""Unit tests for PipelineStatusIndicator class."""

from hosts.gui.pipeline_status_indicator import PipelineStatusIndicator


class TestPipelineStatusIndicator:
    """Test PipelineStatusIndicator functionality."""

    def test_initial_state(self):
        """Test initial state of PipelineStatusIndicator."""
        indicator = PipelineStatusIndicator()
        assert indicator.current_agent == ""
        assert indicator.get_queue() == []
        assert indicator.is_loading() is False

    def test_update_agent(self):
        """Test updating current agent."""
        indicator = PipelineStatusIndicator()
        indicator.update_agent("Hephaestus")
        assert indicator.get_current_agent() == "Hephaestus"

    def test_add_to_queue(self):
        """Test adding agents to queue."""
        indicator = PipelineStatusIndicator()
        indicator.add_to_queue("Hephaestus")
        assert "Hephaestus" in indicator.get_queue()

    def test_add_duplicate_to_queue(self):
        """Test that duplicate agents are not added to queue."""
        indicator = PipelineStatusIndicator()
        indicator.add_to_queue("Hephaestus")
        indicator.add_to_queue("Hephaestus")
        assert len(indicator.get_queue()) == 1

    def test_add_multiple_to_queue(self):
        """Test adding multiple agents to queue."""
        indicator = PipelineStatusIndicator()
        indicator.add_to_queue("Hephaestus")
        indicator.add_to_queue("Metis")
        indicator.add_to_queue("Techne")
        assert len(indicator.get_queue()) == 3
        assert indicator.get_queue() == ["Hephaestus", "Metis", "Techne"]

    def test_remove_from_queue(self):
        """Test removing agents from queue."""
        indicator = PipelineStatusIndicator()
        indicator.add_to_queue("Hephaestus")
        indicator.add_to_queue("Metis")
        indicator.remove_from_queue("Hephaestus")
        assert "Hephaestus" not in indicator.get_queue()
        assert "Metis" in indicator.get_queue()

    def test_remove_nonexistent_from_queue(self):
        """Test removing non-existent agent from queue."""
        indicator = PipelineStatusIndicator()
        indicator.add_to_queue("Hephaestus")
        indicator.remove_from_queue("Metis")
        assert len(indicator.get_queue()) == 1

    def test_set_loading(self):
        """Test setting loading state."""
        indicator = PipelineStatusIndicator()
        assert indicator.is_loading() is False
        indicator.set_loading(True)
        assert indicator.is_loading() is True
        indicator.set_loading(False)
        assert indicator.is_loading() is False

    def test_clear_queue(self):
        """Test clearing the queue."""
        indicator = PipelineStatusIndicator()
        indicator.update_agent("Hephaestus")
        indicator.add_to_queue("Metis")
        indicator.add_to_queue("Techne")
        indicator.set_loading(True)

        indicator.clear_queue()

        assert indicator.get_current_agent() == ""
        assert indicator.get_queue() == []
        assert indicator.is_loading() is False  # Loading state is cleared

    def test_queue_copy(self):
        """Test that get_queue returns a copy."""
        indicator = PipelineStatusIndicator()
        indicator.add_to_queue("Hephaestus")
        queue = indicator.get_queue()
        queue.append("Metis")
        # Original should not be modified
        assert len(indicator.get_queue()) == 1
