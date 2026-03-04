"""Pipeline status indicator for tracking agent processing."""

from dataclasses import dataclass, field


@dataclass
class PipelineStatusIndicator:
    """Shows which agent is currently processing."""

    current_agent: str = ""
    processing_queue: list[str] = field(default_factory=list)
    loading: bool = False

    def update_agent(self, agent: str) -> None:
        """Update current processing agent."""
        self.current_agent = agent

    def add_to_queue(self, agent: str) -> None:
        """Add agent to processing queue."""
        if agent not in self.processing_queue:
            self.processing_queue.append(agent)

    def remove_from_queue(self, agent: str) -> None:
        """Remove agent from processing queue."""
        if agent in self.processing_queue:
            self.processing_queue.remove(agent)

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        self.loading = loading

    def get_current_agent(self) -> str:
        """Get current processing agent."""
        return self.current_agent

    def get_queue(self) -> list[str]:
        """Get processing queue."""
        return self.processing_queue.copy()

    def is_loading(self) -> bool:
        """Check if currently loading."""
        return self.loading

    def clear_queue(self) -> None:
        """Clear the processing queue."""
        self.processing_queue.clear()
        self.current_agent = ""
        self.loading = False
