"""Integration tests for DialogueHistory with TypewriterManager.

Tests the integration between DialogueHistory and TypewriterManager,
verifying that typewriter effects update dialogue history in real-time
and handle completion correctly.
"""

from __future__ import annotations

import pygame

from hosts.gui.dialogue import DialogueEntry, DialogueHistory
from hosts.gui.typewriter import TypewriterManager

pygame.init()


class TestDialogueHistoryTypewriterIntegration:
    """Tests for DialogueHistory and TypewriterManager integration."""

    def test_update_last_text_during_typewriter_effect(self) -> None:
        """Test that DialogueHistory updates last message during typewriter effect."""
        history = DialogueHistory()
        manager = TypewriterManager()

        # Add initial entry
        entry = DialogueEntry("Agent", "")
        history.add(entry)

        # Start typewriter effect
        full_text = "Hello World"
        manager.start(full_text, speed_ms=30)

        # Simulate typewriter updates
        displayed_text = ""
        while not manager.is_complete():
            displayed_text = manager.update(0.03)
            history.update_last_text(displayed_text)

        # Verify final text matches
        assert history._entries[-1].text == full_text

    def test_typewriter_effect_updates_dialogue_in_real_time(self) -> None:
        """Test that typewriter effect updates dialogue history in real-time."""
        history = DialogueHistory()
        manager = TypewriterManager()

        # Add entry with empty text
        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "This is a test message"
        manager.start(full_text, speed_ms=30)

        # Track text progression
        texts_seen = []
        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)
            texts_seen.append(displayed)

        # Verify progression
        assert len(texts_seen) > 0
        assert texts_seen[-1] == full_text
        # Verify each text is a prefix of the next
        for i in range(len(texts_seen) - 1):
            assert texts_seen[i + 1].startswith(texts_seen[i])

    def test_multiple_messages_with_typewriter_effects(self) -> None:
        """Test multiple messages with typewriter effects."""
        history = DialogueHistory()
        manager = TypewriterManager()

        messages = ["First message", "Second message", "Third message"]

        for msg in messages:
            # Add entry
            entry = DialogueEntry("Agent", "")
            history.add(entry)

            # Apply typewriter effect
            manager.start(msg, speed_ms=30)
            while not manager.is_complete():
                displayed = manager.update(0.03)
                history.update_last_text(displayed)

        # Verify all messages are in history
        assert len(history._entries) == 3
        assert history._entries[0].text == messages[0]
        assert history._entries[1].text == messages[1]
        assert history._entries[2].text == messages[2]

    def test_typewriter_skip_updates_dialogue_immediately(self) -> None:
        """Test that skipping typewriter updates dialogue immediately."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "This is a long message that would take time to display"
        manager.start(full_text, speed_ms=30)

        # Display partial text
        manager.update(0.03)
        history.update_last_text(manager.get_displayed_text())
        partial_text = history._entries[-1].text

        # Skip to full text
        manager.skip()
        history.update_last_text(manager.get_displayed_text())

        # Verify text was updated
        assert history._entries[-1].text == full_text
        assert len(history._entries[-1].text) > len(partial_text)

    def test_typewriter_completion_handler(self) -> None:
        """Test handling typewriter effect completion."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Complete message"
        manager.start(full_text, speed_ms=30)

        # Simulate effect
        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        # Verify completion
        assert manager.is_complete() is True
        assert history._entries[-1].text == full_text

    def test_typewriter_with_motion_sensitivity(self) -> None:
        """Test typewriter with motion sensitivity enabled."""
        history = DialogueHistory()
        manager = TypewriterManager(motion_sensitivity_enabled=True)

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Motion sensitive text"
        manager.start(full_text, speed_ms=30)

        # With motion sensitivity, text should be displayed immediately
        displayed = manager.update(0.0)
        history.update_last_text(displayed)

        assert history._entries[-1].text == full_text
        assert manager.is_complete() is True

    def test_typewriter_pause_resume_with_dialogue(self) -> None:
        """Test typewriter pause/resume with dialogue history."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Pausable message"
        manager.start(full_text, speed_ms=30)

        # Display partial text
        manager.update(0.03)
        history.update_last_text(manager.get_displayed_text())
        text_before_pause = history._entries[-1].text

        # Pause
        manager.pause()
        manager.update(0.1)
        history.update_last_text(manager.get_displayed_text())
        text_after_pause = history._entries[-1].text

        # Verify text didn't change during pause
        assert text_after_pause == text_before_pause

        # Resume
        manager.resume()
        manager.update(0.1)
        history.update_last_text(manager.get_displayed_text())
        text_after_resume = history._entries[-1].text

        # Verify text progressed after resume
        assert len(text_after_resume) > len(text_before_pause)

    def test_dialogue_history_dirty_flag_with_typewriter(self) -> None:
        """Test that DialogueHistory dirty flag is set during typewriter updates."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        # Initial render
        history._render(pygame.Rect(0, 0, 960, 686))
        assert history._dirty is False

        # Update text during typewriter
        manager.start("Test", speed_ms=30)
        manager.update(0.03)
        history.update_last_text(manager.get_displayed_text())

        # Dirty flag should be set
        assert history._dirty is True

    def test_typewriter_with_special_characters_in_dialogue(self) -> None:
        """Test typewriter with special characters in dialogue."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Special: !@#$%^&*() chars"
        manager.start(full_text, speed_ms=30)

        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        assert history._entries[-1].text == full_text

    def test_typewriter_with_unicode_in_dialogue(self) -> None:
        """Test typewriter with unicode characters in dialogue."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Unicode: こんにちは 世界"
        manager.start(full_text, speed_ms=30)

        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        assert history._entries[-1].text == full_text

    def test_typewriter_with_multiline_text(self) -> None:
        """Test typewriter with multiline text."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Line 1\nLine 2\nLine 3"
        manager.start(full_text, speed_ms=30)

        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        assert history._entries[-1].text == full_text
        assert "\n" in history._entries[-1].text

    def test_typewriter_effect_with_empty_initial_text(self) -> None:
        """Test typewriter effect starting with empty text."""
        history = DialogueHistory()
        manager = TypewriterManager()

        # Add entry with empty text
        entry = DialogueEntry("Agent", "")
        history.add(entry)

        assert history._entries[-1].text == ""

        # Start typewriter
        full_text = "Now with text"
        manager.start(full_text, speed_ms=30)

        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        assert history._entries[-1].text == full_text

    def test_typewriter_effect_preserves_other_entry_properties(self) -> None:
        """Test that typewriter updates preserve other entry properties."""
        history = DialogueHistory()
        manager = TypewriterManager()

        # Add entry with specific properties
        entry = DialogueEntry("TestAgent", "", is_result=True)
        history.add(entry)

        # Verify properties before typewriter
        assert history._entries[-1].agent == "TestAgent"
        assert history._entries[-1].is_result is True

        # Apply typewriter
        full_text = "Result text"
        manager.start(full_text, speed_ms=30)

        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        # Verify properties are preserved
        assert history._entries[-1].agent == "TestAgent"
        assert history._entries[-1].is_result is True
        assert history._entries[-1].text == full_text

    def test_rapid_typewriter_updates(self) -> None:
        """Test rapid typewriter updates to dialogue history."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Rapid updates test"
        manager.start(full_text, speed_ms=10)  # Very fast

        update_count = 0
        while not manager.is_complete():
            displayed = manager.update(0.001)  # Very small delta time
            history.update_last_text(displayed)
            update_count += 1

        # Verify many updates occurred
        assert update_count > 0
        assert history._entries[-1].text == full_text

    def test_typewriter_effect_with_different_agents(self) -> None:
        """Test typewriter effects with different agents."""
        history = DialogueHistory()
        manager = TypewriterManager()

        agents = ["Agent1", "Agent2", "Agent3"]
        messages = ["Message 1", "Message 2", "Message 3"]

        for agent, msg in zip(agents, messages, strict=False):
            entry = DialogueEntry(agent, "")
            history.add(entry)

            manager.start(msg, speed_ms=30)
            while not manager.is_complete():
                displayed = manager.update(0.03)
                history.update_last_text(displayed)

        # Verify all entries
        assert len(history._entries) == 3
        for i, (agent, msg) in enumerate(zip(agents, messages, strict=False)):
            assert history._entries[i].agent == agent
            assert history._entries[i].text == msg

    def test_typewriter_effect_completion_state(self) -> None:
        """Test typewriter effect completion state with dialogue."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        full_text = "Completion test"
        manager.start(full_text, speed_ms=30)

        # Before completion
        assert manager.is_complete() is False

        # Simulate to completion
        while not manager.is_complete():
            displayed = manager.update(0.03)
            history.update_last_text(displayed)

        # After completion
        assert manager.is_complete() is True
        assert history._entries[-1].text == full_text

    def test_update_last_text_with_no_entries(self) -> None:
        """Test update_last_text when no entries exist."""
        history = DialogueHistory()

        # Should not raise error
        history.update_last_text("Some text")
        assert len(history._entries) == 0

    def test_typewriter_effect_with_very_long_text(self) -> None:
        """Test typewriter effect with very long text."""
        history = DialogueHistory()
        manager = TypewriterManager()

        entry = DialogueEntry("Agent", "")
        history.add(entry)

        # Create long text
        full_text = "A" * 1000
        manager.start(full_text, speed_ms=10)

        while not manager.is_complete():
            displayed = manager.update(0.01)
            history.update_last_text(displayed)

        assert history._entries[-1].text == full_text
        assert len(history._entries[-1].text) == 1000
