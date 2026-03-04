"""Status bubbles for displaying technical status information."""

from dataclasses import dataclass, field


@dataclass
class StatusBubbles:
    """Collapsible panel for technical status information."""

    collapsed: bool = False
    _content: list[str] = field(default_factory=list)
    _last_update: float = 0.0
    _max_messages: int = 10

    def toggle_collapse(self) -> None:
        """Toggle collapse state."""
        self.collapsed = not self.collapsed

    def add_status(self, text: str) -> None:
        """Add status message."""
        self._content.append(text)
        # Keep only the most recent messages
        if len(self._content) > self._max_messages:
            self._content.pop(0)

    def clear_status(self) -> None:
        """Clear all status messages."""
        self._content.clear()

    def update(self, dt: float) -> None:
        """Update background content."""
        self._last_update += dt

    def get_height(self) -> int:
        """Get current height based on collapse state."""
        if self.collapsed:
            return 24  # Minimal height for collapsed state
        # Calculate height based on number of messages
        # Assume 20px per message + 10px padding
        return len(self._content) * 20 + 10

    def get_content(self) -> list[str]:
        """Get current status messages."""
        return self._content.copy()

    def is_collapsed(self) -> bool:
        """Check if status bubbles are collapsed."""
        return self.collapsed
