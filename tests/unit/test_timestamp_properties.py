"""Property-based tests for Timestamp Display using Hypothesis."""

from hypothesis import given, settings, strategies as st

from hosts.gui.dialogue import DialogueEntry, DialogueHistory


# Feature: gui-improvements, Property 11: Timestamp Display Consistency
class TestTimestampDisplayProperty:
    """Property-based tests for timestamp display consistency."""

    @given(timestamp=st.floats(min_value=0, max_value=2e9), fmt=st.sampled_from(["12h", "24h"]))
    @settings(max_examples=100)
    def test_timestamp_display_consistency(self, timestamp, fmt):
        """Property: When timestamps are enabled, the timestamp shall be displayed consistently with
        configured format."""
        history = DialogueHistory()
        entry = DialogueEntry(agent="system", text="Test")
        entry.timestamp = timestamp

        result = history.get_timestamp_text(entry, fmt=fmt)

        assert result is not None
        assert len(result) > 0
        if fmt == "12h":
            assert any(m in result for m in ["AM", "PM"])
        else:
            assert "AM" not in result and "PM" not in result
