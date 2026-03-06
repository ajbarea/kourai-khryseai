"""Property-based tests for KeyboardShortcuts using Hypothesis."""

import pygame
from hypothesis import given, settings, strategies as st

from hosts.gui.keyboard_shortcuts import KeyboardShortcuts


# Feature: gui-improvements, Property 7: Keyboard Shortcut Response
class TestKeyboardShortcutResponseProperty:
    """Property-based tests for keyboard shortcuts."""

    @given(
        shortcut=st.sampled_from(
            [
                (pygame.K_k, pygame.KMOD_CTRL, {"action": "focus"}),
                (pygame.K_l, pygame.KMOD_CTRL, {"action": "clear"}),
                (pygame.K_UP, 0, {"action": "navigate"}),
                (pygame.K_DOWN, 0, {"action": "navigate"}),
            ]
        )
    )
    @settings(max_examples=100)
    def test_keyboard_shortcut_actions(self, shortcut):
        """Property: For any keyboard shortcut (Ctrl+K, Ctrl+L, Up/Down arrows), the GUI shall
        respond."""
        key, mod, expected_action = shortcut
        shortcuts = KeyboardShortcuts()

        shortcuts.add_message("Test message 1")
        shortcuts.add_message("Test message 2")

        event = pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)
        action = shortcuts.handle_key(event, current_text="")

        assert action is not None
        assert action["action"] == expected_action["action"]
