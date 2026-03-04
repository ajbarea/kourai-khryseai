"""Tests for DialogueHistory timestamp and metadata display."""

from hosts.gui.__main__ import DialogueEntry, DialogueHistory


class TestDialogueHistoryMetadata:
    """Test DialogueHistory timestamp and metadata display."""

    def test_get_timestamp_text_24h(self):
        """Test getting timestamp in 24-hour format."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message")
        timestamp_text = history.get_timestamp_text(entry, "24h")
        # Should be in format HH:MM:SS
        assert len(timestamp_text) == 8
        assert timestamp_text.count(":") == 2

    def test_get_timestamp_text_12h(self):
        """Test getting timestamp in 12-hour format."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message")
        timestamp_text = history.get_timestamp_text(entry, "12h")
        # Should contain AM or PM
        assert "AM" in timestamp_text or "PM" in timestamp_text

    def test_get_metadata_text_with_processing_time(self):
        """Test getting metadata text with processing time."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message", processing_time=1.5)
        metadata_text = history.get_metadata_text(entry)
        assert "1.50s" in metadata_text

    def test_get_metadata_text_with_agent_count(self):
        """Test getting metadata text with agent count."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message", agent_count=3)
        metadata_text = history.get_metadata_text(entry)
        assert "3" in metadata_text

    def test_get_metadata_text_with_both(self):
        """Test getting metadata text with both processing time and agent count."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message", processing_time=2.0, agent_count=4)
        metadata_text = history.get_metadata_text(entry)
        assert "2.00s" in metadata_text
        assert "4" in metadata_text
        assert "|" in metadata_text

    def test_get_metadata_text_empty(self):
        """Test getting metadata text when no metadata available."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message")
        metadata_text = history.get_metadata_text(entry)
        assert metadata_text == ""

    def test_toggle_timestamps(self):
        """Test toggling timestamps."""
        history = DialogueHistory()
        # Should not raise an error
        history.toggle_timestamps()

    def test_toggle_metadata(self):
        """Test toggling metadata."""
        history = DialogueHistory()
        # Should not raise an error
        history.toggle_metadata()

    def test_set_timestamp_format(self):
        """Test setting timestamp format."""
        history = DialogueHistory()
        # Should not raise an error
        history.set_timestamp_format("12h")
        history.set_timestamp_format("24h")

    def test_metadata_text_formatting(self):
        """Test metadata text formatting."""
        history = DialogueHistory()
        entry = DialogueEntry("Hephaestus", "Test message", processing_time=0.123, agent_count=2)
        metadata_text = history.get_metadata_text(entry)
        # Should have proper formatting
        assert "0.12s" in metadata_text
        assert "2" in metadata_text
