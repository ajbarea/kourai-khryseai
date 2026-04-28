"""Integration of PipelineStatusIndicator with the main GUI."""

from .pipeline_status_indicator import PipelineStatusIndicator


class PipelineStatusGUIIntegration:
    """Manages integration of pipeline status indicator with the main GUI."""

    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.indicator = PipelineStatusIndicator()

    def update_current_agent(self, agent: str) -> None:
        self.indicator.update_agent(agent)

    def add_agent_to_queue(self, agent: str) -> None:
        self.indicator.add_to_queue(agent)

    def remove_agent_from_queue(self, agent: str) -> None:
        self.indicator.remove_from_queue(agent)

    def set_loading_state(self, loading: bool) -> None:
        self.indicator.set_loading(loading)

    def get_current_agent(self) -> str:
        return self.indicator.get_current_agent()

    def get_processing_queue(self) -> list[str]:
        return self.indicator.get_queue()

    def is_loading(self) -> bool:
        return self.indicator.is_loading()

    def clear_pipeline(self) -> None:
        self.indicator.clear_queue()

    def get_indicator(self) -> PipelineStatusIndicator:
        return self.indicator
