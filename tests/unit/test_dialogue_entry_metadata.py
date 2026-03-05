"""Tests for DialogueEntry metadata functionality."""

import time

import pytest

from hosts.gui.dialogue import DialogueEntry


class TestDialogueEntryMetadata:
    """Test DialogueEntry metadata functionality."""

    def test_dialogue_entry_with_metadata(self):
        """Test creating DialogueEntry with metadata."""
        entry = DialogueEntry("Hephaestus", "Test message", processing_time=1.5, agent_count=3)
        assert entry.agent == "Hephaestus"
        assert entry.text == "Test message"
        assert entry.processing_time == 1.5
        assert entry.agent_count == 3
        assert entry.metadata_visible is True

    def test_dialogue_entry_without_metadata(self):
        """Test creating DialogueEntry without metadata."""
        entry = DialogueEntry("Hephaestus", "Test message")
        assert entry.processing_time is None
        assert entry.agent_count is None

    def test_dialogue_entry_timestamp(self):
        """Test that timestamp is set on creation."""
        before = time.monotonic()
        entry = DialogueEntry("Hephaestus", "Test message")
        after = time.monotonic()
        assert before <= entry.timestamp <= after

    def test_dialogue_entry_metadata_visible(self):
        """Test metadata visibility flag."""
        entry = DialogueEntry("Hephaestus", "Test message")
        assert entry.metadata_visible is True

    def test_dialogue_entry_with_processing_time(self):
        """Test DialogueEntry with processing time."""
        entry = DialogueEntry("Hephaestus", "Test message", processing_time=2.5)
        assert entry.processing_time == 2.5

    def test_dialogue_entry_with_agent_count(self):
        """Test DialogueEntry with agent count."""
        entry = DialogueEntry("Hephaestus", "Test message", agent_count=5)
        assert entry.agent_count == 5

    def test_dialogue_entry_slots(self):
        """Test that DialogueEntry uses slots."""
        entry = DialogueEntry("Hephaestus", "Test message")
        # Should not be able to add arbitrary attributes
        with pytest.raises(AttributeError):
            entry.new_attribute = "value"

    def test_dialogue_entry_is_user(self):
        """Test DialogueEntry with is_user flag."""
        entry = DialogueEntry(
            "User", "Test message", is_user=True, processing_time=0.1, agent_count=1
        )
        assert entry.is_user is True
        assert entry.processing_time == 0.1

    def test_dialogue_entry_is_result(self):
        """Test DialogueEntry with is_result flag."""
        entry = DialogueEntry(
            "Hephaestus", "Test result", is_result=True, processing_time=1.0, agent_count=2
        )
        assert entry.is_result is True
        assert entry.processing_time == 1.0

    def test_dialogue_entry_is_error(self):
        """Test DialogueEntry with is_error flag."""
        entry = DialogueEntry("System", "Error message", is_error=True)
        assert entry.is_error is True
