"""Property-based tests for MessageHistory using Hypothesis."""

from hypothesis import given, settings, strategies as st

from hosts.gui.message_history import MessageHistory


# Feature: gui-improvements, Property 8: Message History Navigation
class TestMessageHistoryNavigationProperty:
    """Property-based tests for message history navigation."""

    @given(
        messages=st.lists(st.text(min_size=1), min_size=1, max_size=20),
        directions=st.lists(st.sampled_from([-1, 1]), min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_message_history_navigation(self, messages, directions):
        """Property: Navigating with Up/Down arrows shall correctly load
        messages from index 0 to N-1, with wraparound."""
        history = MessageHistory(max_size=20)

        for msg in messages:
            history.add(msg)

        # MessageHistory.add() silently drops whitespace-only messages
        messages = [m for m in messages if m.strip()]
        if not messages:
            assert len(history) == 0
            return

        assert len(history) == len(messages)

        current_index = len(messages)

        for direction in directions:
            msg = history.navigate(direction)
            if current_index == len(messages):
                current_index = len(messages) - 1 if direction == -1 else 0
            else:
                current_index = (current_index + direction) % len(messages)

            assert msg == messages[current_index]
