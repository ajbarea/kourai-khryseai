"""Status bubbles for displaying technical status information."""

from dataclasses import dataclass, field


@dataclass
class StatusBubbles:
    """Buffer for technical status information (Debug Logs)."""

    _content: list[str] = field(default_factory=list)
    _max_messages: int = 100

    def add_status(self, text: str) -> None:
        """Add status message."""
        self._content.append(text)
        # Keep only the most recent messages
        if len(self._content) > self._max_messages:
            self._content.pop(0)

    def clear_status(self) -> None:
        """Clear all status messages."""
        self._content.clear()

    def get_content(self) -> list[str]:
        """Get current status messages."""
        return self._content.copy()
