"""Unit tests for StatusBubbles class."""

from hosts.gui.status_bubbles import StatusBubbles


class TestStatusBubbles:
    """Test StatusBubbles functionality."""

    def test_initial_state(self):
        """Test initial state of StatusBubbles."""
        bubbles = StatusBubbles()
        assert bubbles.get_content() == []

    def test_add_status(self):
        """Test adding status messages."""
        bubbles = StatusBubbles()
        bubbles.add_status("Status 1")
        assert len(bubbles.get_content()) == 1
        assert bubbles.get_content()[0] == "Status 1"

    def test_add_multiple_status(self):
        """Test adding multiple status messages."""
        bubbles = StatusBubbles()
        bubbles.add_status("Status 1")
        bubbles.add_status("Status 2")
        bubbles.add_status("Status 3")
        assert len(bubbles.get_content()) == 3
        assert bubbles.get_content() == ["Status 1", "Status 2", "Status 3"]

    def test_max_messages_limit(self):
        """Test that max messages limit is enforced."""
        bubbles = StatusBubbles()
        for i in range(110):
            bubbles.add_status(f"Status {i}")
        # Should only keep the last 100
        assert len(bubbles.get_content()) == 100
        assert bubbles.get_content()[0] == "Status 10"

    def test_clear_status(self):
        """Test clearing all status messages."""
        bubbles = StatusBubbles()
        bubbles.add_status("Status 1")
        bubbles.add_status("Status 2")
        bubbles.clear_status()
        assert len(bubbles.get_content()) == 0

    def test_content_copy(self):
        """Test that get_content returns a copy."""
        bubbles = StatusBubbles()
        bubbles.add_status("Status 1")
        content = bubbles.get_content()
        content.append("Status 2")
        # Original should not be modified
        assert len(bubbles.get_content()) == 1
