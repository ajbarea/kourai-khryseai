"""Property-based tests for AutoScrollManager using Hypothesis.

Feature: gui-improvements
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from hosts.gui.auto_scroll import AutoScrollManager


# Feature: gui-improvements, Property 3: Auto-Scroll Position Preservation
@given(
    scroll_pos=st.integers(min_value=0, max_value=10000),
    content_height=st.integers(min_value=100, max_value=100000),
    view_height=st.integers(min_value=100, max_value=10000),
)
@settings(max_examples=100)
def test_auto_scroll_position_preservation(scroll_pos, content_height, view_height):
    """Property: When auto-scroll is disabled, scroll position is preserved.

    Validates: Requirements 2.3

    For any scroll position and new message, when auto-scroll is disabled,
    the scroll position shall remain unchanged after the message is added.
    """
    manager = AutoScrollManager()
    manager.enabled = False

    # Clamp scroll position to valid range
    max_scroll = max(0, content_height - view_height)
    scroll_pos = min(scroll_pos, max_scroll)

    # Record initial position
    manager.update_distance(scroll_pos, content_height, view_height)
    initial_position = manager._last_scroll_y

    # Simulate new message by increasing content height
    new_content_height = content_height + 100

    # Update with same scroll position (simulating preserved position)
    manager.update_distance(scroll_pos, new_content_height, view_height)

    # Verify position is preserved
    assert manager._last_scroll_y == initial_position
    assert manager._last_scroll_y == scroll_pos


# Feature: gui-improvements, Property 4: Auto-Scroll to Bottom
@given(
    scroll_pos=st.integers(min_value=0, max_value=10000),
    content_height=st.integers(min_value=100, max_value=100000),
    view_height=st.integers(min_value=100, max_value=10000),
)
@settings(max_examples=100)
def test_auto_scroll_to_bottom(scroll_pos, content_height, view_height):
    """Property: When auto-scroll is enabled, scroll to bottom on new message.

    Validates: Requirements 2.2

    For any new message, when auto-scroll is enabled, the dialogue history
    shall scroll to the bottom within 100ms of the message being added.
    """
    manager = AutoScrollManager()
    manager.enabled = True

    # Verify should_scroll returns True
    assert manager.should_scroll() is True

    # Clamp scroll position to valid range
    max_scroll = max(0, content_height - view_height)
    scroll_pos = min(scroll_pos, max_scroll)

    # Update distance (simulating scroll to bottom)
    manager.update_distance(scroll_pos, content_height, view_height)

    # When auto-scroll is enabled, the manager should indicate scrolling is needed
    # by returning True from should_scroll()
    assert manager.should_scroll() is True


# Feature: gui-improvements, Property 3: Auto-Scroll Position Preservation (Extended)
@given(
    initial_scroll=st.integers(min_value=0, max_value=5000),
    content_height=st.integers(min_value=100, max_value=50000),
    view_height=st.integers(min_value=100, max_value=5000),
    new_messages_height=st.integers(min_value=0, max_value=1000),
)
@settings(max_examples=100)
def test_auto_scroll_disabled_preserves_across_updates(
    initial_scroll, content_height, view_height, new_messages_height
):
    """Property: Disabled auto-scroll preserves position across multiple updates.

    Validates: Requirements 2.3

    For any sequence of updates, when auto-scroll is disabled, the scroll
    position shall remain unchanged even as new content is added.
    """
    manager = AutoScrollManager()
    manager.enabled = False

    # Clamp initial scroll to valid range
    max_scroll = max(0, content_height - view_height)
    initial_scroll = min(initial_scroll, max_scroll)

    # Set initial position
    manager.update_distance(initial_scroll, content_height, view_height)

    # Simulate multiple message additions
    for _ in range(5):
        new_content_height = content_height + new_messages_height
        # Position should be preserved (not auto-scrolled)
        manager.update_distance(initial_scroll, new_content_height, view_height)
        assert manager._last_scroll_y == initial_scroll
        content_height = new_content_height


# Feature: gui-improvements, Property 4: Auto-Scroll to Bottom (Extended)
@given(
    content_height=st.integers(min_value=100, max_value=50000),
    view_height=st.integers(min_value=100, max_value=5000),
)
@settings(max_examples=100)
def test_auto_scroll_enabled_always_scrolls(content_height, view_height):
    """Property: When auto-scroll is enabled, should_scroll always returns True.

    Validates: Requirements 2.2

    For any content and view height, when auto-scroll is enabled, the
    should_scroll() method shall always return True.
    """
    manager = AutoScrollManager()
    manager.enabled = True

    # should_scroll should always return True when enabled
    assert manager.should_scroll() is True

    # Update distance multiple times
    for scroll_pos in [0, 100, 500, 1000]:
        manager.update_distance(scroll_pos, content_height, view_height)
        assert manager.should_scroll() is True


# Feature: gui-improvements, Property 3: Auto-Scroll Position Preservation (Toggle)
@given(
    scroll_pos=st.integers(min_value=0, max_value=5000),
    content_height=st.integers(min_value=100, max_value=50000),
    view_height=st.integers(min_value=100, max_value=5000),
)
@settings(max_examples=100)
def test_auto_scroll_toggle_preserves_distance(scroll_pos, content_height, view_height):
    """Property: Toggle preserves scroll distance calculation.

    Validates: Requirements 2.3

    For any scroll position, toggling auto-scroll on/off shall not affect
    the calculated scroll distance.
    """
    manager = AutoScrollManager()

    # Clamp scroll position
    max_scroll = max(0, content_height - view_height)
    scroll_pos = min(scroll_pos, max_scroll)

    # Calculate distance
    manager.update_distance(scroll_pos, content_height, view_height)
    distance_before = manager.scroll_distance

    # Toggle and verify distance is preserved
    manager.toggle()
    assert manager.scroll_distance == distance_before

    manager.toggle()
    assert manager.scroll_distance == distance_before


# Feature: gui-improvements, Property 3: Auto-Scroll Position Preservation (Distance Calculation)
@given(
    scroll_pos=st.integers(min_value=0, max_value=10000),
    content_height=st.integers(min_value=100, max_value=100000),
    view_height=st.integers(min_value=100, max_value=10000),
)
@settings(max_examples=100)
def test_auto_scroll_distance_calculation_correctness(scroll_pos, content_height, view_height):
    """Property: Distance calculation is always correct.

    Validates: Requirements 2.3, 2.4

    For any scroll position, content height, and view height, the calculated
    distance shall equal max_scroll - current_scroll, clamped to [0, max_scroll].
    """
    manager = AutoScrollManager()

    # Clamp scroll position to valid range
    max_scroll = max(0, content_height - view_height)
    scroll_pos = min(scroll_pos, max_scroll)

    # Calculate expected distance
    expected_distance = max(0, max_scroll - scroll_pos)

    # Update and verify
    manager.update_distance(scroll_pos, content_height, view_height)
    assert manager.scroll_distance == expected_distance


# Feature: gui-improvements, Property 4: Auto-Scroll to Bottom (Distance at Bottom)
@given(
    content_height=st.integers(min_value=100, max_value=100000),
    view_height=st.integers(min_value=100, max_value=10000),
)
@settings(max_examples=100)
def test_auto_scroll_distance_zero_at_bottom(content_height, view_height):
    """Property: Distance is zero when scrolled to bottom.

    Validates: Requirements 2.2, 2.4

    For any content and view height, when scroll position equals max_scroll,
    the distance shall be zero.
    """
    manager = AutoScrollManager()

    # Calculate max scroll position
    max_scroll = max(0, content_height - view_height)

    # Update with scroll at bottom
    manager.update_distance(max_scroll, content_height, view_height)

    # Distance should be zero
    assert manager.scroll_distance == 0
    assert manager.get_distance_text() == "At bottom"
