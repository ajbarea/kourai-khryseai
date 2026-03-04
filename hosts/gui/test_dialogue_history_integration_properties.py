"""Property-based tests for DialogueHistory with TypewriterManager integration.

Tests the correctness properties of the integration between DialogueHistory
and TypewriterManager using Hypothesis for property-based testing.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from .__main__ import DialogueEntry, DialogueHistory
from .typewriter import TypewriterManager


# Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence
@given(
    text=st.text(min_size=1, max_size=1000),
    speed=st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100)
def test_typewriter_character_sequence_in_dialogue(text: str, speed: int) -> None:
    """Property: Typewriter displays characters sequentially in dialogue history.

    For any dialogue text and typewriter speed setting, the typewriter effect
    shall display characters sequentially from first to last in the dialogue
    history, with each character appearing at the configured interval using
    delta time for consistent animation speed regardless of frame rate.

    Validates: Requirements 1.1, 1.3, 1.4
    """
    history = DialogueHistory()
    manager = TypewriterManager()

    # Add entry to history
    entry = DialogueEntry("Agent", "")
    history.add(entry)

    # Start typewriter effect
    manager.start(text, speed_ms=speed)

    # Simulate frame updates with delta time
    dt = 0.016  # 60 FPS
    displayed_texts = []

    while not manager.is_complete():
        displayed = manager.update(dt)
        history.update_last_text(displayed)
        displayed_texts.append(displayed)

    # Verify displayed text is a prefix of full text
    for displayed in displayed_texts:
        assert text.startswith(displayed), f"'{displayed}' is not a prefix of '{text}'"

    # Verify complete text is displayed
    assert history._entries[-1].text == text
    assert displayed_texts[-1] == text


# Feature: gui-improvements, Property 2: Typewriter Skip Functionality
@given(
    text=st.text(min_size=1, max_size=1000),
    speed=st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100)
def test_typewriter_skip_in_dialogue(text: str, speed: int) -> None:
    """Property: Skipping typewriter immediately displays full text in dialogue.

    For any active typewriter effect in dialogue history, requesting skip shall
    immediately display the full text and terminate the effect.

    Validates: Requirements 1.2
    """
    history = DialogueHistory()
    manager = TypewriterManager()

    # Add entry
    entry = DialogueEntry("Agent", "")
    history.add(entry)

    # Start typewriter
    manager.start(text, speed_ms=speed)

    # Display partial text
    manager.update(0.016)
    history.update_last_text(manager.get_displayed_text())

    # Skip
    manager.skip()
    history.update_last_text(manager.get_displayed_text())

    # Verify full text is displayed
    assert history._entries[-1].text == text
    assert manager.is_complete() is True


# Feature: gui-improvements, Property 13: Motion Sensitivity Support
@given(
    text=st.text(min_size=1, max_size=1000),
)
@settings(max_examples=100)
def test_motion_sensitivity_in_dialogue(text: str) -> None:
    """Property: Motion sensitivity displays text immediately in dialogue.

    For any user with motion sensitivity preferences enabled, the typewriter
    effect shall be disabled, providing immediate text display while maintaining
    functionality in the dialogue history.

    Validates: Requirements 1.7, 12.8
    """
    history = DialogueHistory()
    manager = TypewriterManager(motion_sensitivity_enabled=True)

    # Add entry
    entry = DialogueEntry("Agent", "")
    history.add(entry)

    # Start typewriter with motion sensitivity
    manager.start(text, speed_ms=30)

    # Update dialogue
    displayed = manager.update(0.0)
    history.update_last_text(displayed)

    # Verify text is displayed immediately
    assert history._entries[-1].text == text
    assert manager.is_complete() is True


# Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence (Extended)
@given(
    text=st.text(min_size=1, max_size=500),
    speed=st.integers(min_value=10, max_value=100),
    num_messages=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50)
def test_multiple_typewriter_effects_in_dialogue(text: str, speed: int, num_messages: int) -> None:
    """Property: Multiple typewriter effects display correctly in dialogue.

    For any sequence of typewriter effects applied to dialogue history,
    each message shall display characters sequentially and maintain correct
    state across multiple effects.

    Validates: Requirements 1.1, 1.3, 1.4
    """
    history = DialogueHistory()
    manager = TypewriterManager()

    # Apply multiple typewriter effects
    for i in range(num_messages):
        entry = DialogueEntry(f"Agent{i}", "")
        history.add(entry)

        manager.start(text, speed_ms=speed)
        while not manager.is_complete():
            displayed = manager.update(0.016)
            history.update_last_text(displayed)

    # Verify all messages are correct
    assert len(history._entries) == num_messages
    for entry in history._entries:
        assert entry.text == text


# Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence (Pause/Resume)
@given(
    text=st.text(min_size=1, max_size=500),
    speed=st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100)
def test_typewriter_pause_resume_in_dialogue(text: str, speed: int) -> None:
    """Property: Typewriter pause/resume maintains correct state in dialogue.

    For any typewriter effect with pause/resume operations, the dialogue
    history shall maintain correct text state and display characters
    sequentially after resume.

    Validates: Requirements 1.1, 1.3, 1.4
    """
    history = DialogueHistory()
    manager = TypewriterManager()

    entry = DialogueEntry("Agent", "")
    history.add(entry)

    manager.start(text, speed_ms=speed)

    # Display partial text
    manager.update(0.016)
    history.update_last_text(manager.get_displayed_text())
    text_before_pause = history._entries[-1].text

    # Pause
    manager.pause()
    manager.update(0.1)
    history.update_last_text(manager.get_displayed_text())
    text_during_pause = history._entries[-1].text

    # Verify text didn't change during pause
    assert text_during_pause == text_before_pause

    # Resume and complete
    manager.resume()
    while not manager.is_complete():
        displayed = manager.update(0.016)
        history.update_last_text(displayed)

    # Verify final text is correct
    assert history._entries[-1].text == text
    assert text.startswith(text_before_pause)


# Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence (Speed Variation)
@given(
    text=st.text(min_size=1, max_size=500),
    speed1=st.integers(min_value=10, max_value=50),
    speed2=st.integers(min_value=51, max_value=100),
)
@settings(max_examples=100)
def test_typewriter_speed_variation_in_dialogue(text: str, speed1: int, speed2: int) -> None:
    """Property: Different typewriter speeds display at different rates.

    For any two different typewriter speeds applied to the same text,
    the faster speed shall display more characters in the same time period.

    Validates: Requirements 1.3, 1.4
    """
    # Fast speed
    history_fast = DialogueHistory()
    manager_fast = TypewriterManager()
    entry_fast = DialogueEntry("Agent", "")
    history_fast.add(entry_fast)

    manager_fast.start(text, speed_ms=speed1)
    manager_fast.update(0.05)
    history_fast.update_last_text(manager_fast.get_displayed_text())
    fast_chars = len(history_fast._entries[-1].text)

    # Slow speed
    history_slow = DialogueHistory()
    manager_slow = TypewriterManager()
    entry_slow = DialogueEntry("Agent", "")
    history_slow.add(entry_slow)

    manager_slow.start(text, speed_ms=speed2)
    manager_slow.update(0.05)
    history_slow.update_last_text(manager_slow.get_displayed_text())
    slow_chars = len(history_slow._entries[-1].text)

    # Verify fast displays more characters
    assert fast_chars >= slow_chars


# Feature: gui-improvements, Property 1: Typewriter Effect Character Sequence (Unicode)
@given(
    text=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cc", "Cs"),
            blacklist_characters="\x00",
        ),
        min_size=1,
        max_size=500,
    ),
    speed=st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100)
def test_typewriter_unicode_in_dialogue(text: str, speed: int) -> None:
    """Property: Typewriter handles unicode characters correctly in dialogue.

    For any unicode text, the typewriter effect shall display characters
    sequentially without corruption or encoding errors.

    Validates: Requirements 1.1, 1.3, 1.4
    """
    history = DialogueHistory()
    manager = TypewriterManager()

    entry = DialogueEntry("Agent", "")
    history.add(entry)

    manager.start(text, speed_ms=speed)

    while not manager.is_complete():
        displayed = manager.update(0.016)
        history.update_last_text(displayed)

    # Verify final text matches
    assert history._entries[-1].text == text
    # Verify no corruption
    assert len(history._entries[-1].text) == len(text)
