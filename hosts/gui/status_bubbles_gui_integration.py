"""Integration of StatusBubbles with the main GUI."""

from status_bubbles import StatusBubbles


class StatusBubblesGUIIntegration:
    """Manages integration of status bubbles with the main GUI."""

    def __init__(self, gui_instance):
        """Initialize integration with GUI instance."""
        self.gui = gui_instance
        self.status_bubbles = StatusBubbles()

    def add_status_message(self, text: str) -> None:
        """Add a status message to the bubbles."""
        self.status_bubbles.add_status(text)

    def toggle_status_bubbles(self) -> None:
        """Toggle the collapse state of status bubbles."""
        self.status_bubbles.toggle_collapse()

    def update(self, dt: float) -> None:
        """Update status bubbles."""
        self.status_bubbles.update(dt)

    def get_status_bubbles(self) -> StatusBubbles:
        """Get the status bubbles instance."""
        return self.status_bubbles

    def clear_all_status(self) -> None:
        """Clear all status messages."""
        self.status_bubbles.clear_status()

    def is_collapsed(self) -> bool:
        """Check if status bubbles are collapsed."""
        return self.status_bubbles.is_collapsed()

    def get_display_height(self) -> int:
        """Get the height for display purposes."""
        return self.status_bubbles.get_height()
