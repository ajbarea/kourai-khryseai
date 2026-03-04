"""Integration of PipelineStatusIndicator with the main GUI."""

from pipeline_status_indicator import PipelineStatusIndicator


class PipelineStatusGUIIntegration:
    """Manages integration of pipeline status indicator with the main GUI."""

    def __init__(self, gui_instance):
        """Initialize integration with GUI instance."""
        self.gui = gui_instance
        self.indicator = PipelineStatusIndicator()

    def update_current_agent(self, agent: str) -> None:
        """Update the current processing agent."""
        self.indicator.update_agent(agent)

    def add_agent_to_queue(self, agent: str) -> None:
        """Add an agent to the processing queue."""
        self.indicator.add_to_queue(agent)

    def remove_agent_from_queue(self, agent: str) -> None:
        """Remove an agent from the processing queue."""
        self.indicator.remove_from_queue(agent)

    def set_loading_state(self, loading: bool) -> None:
        """Set the loading state."""
        self.indicator.set_loading(loading)

    def get_current_agent(self) -> str:
        """Get the current processing agent."""
        return self.indicator.get_current_agent()

    def get_processing_queue(self) -> list[str]:
        """Get the processing queue."""
        return self.indicator.get_queue()

    def is_loading(self) -> bool:
        """Check if currently loading."""
        return self.indicator.is_loading()

    def clear_pipeline(self) -> None:
        """Clear the pipeline."""
        self.indicator.clear_queue()

    def get_indicator(self) -> PipelineStatusIndicator:
        """Get the indicator instance."""
        return self.indicator
