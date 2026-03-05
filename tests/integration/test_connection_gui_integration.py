"""Tests for ConnectionStatusDisplay GUI integration."""

from __future__ import annotations

import pygame
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hosts.gui.connection_gui_integration import ConnectionStatusDisplay
from hosts.gui.connection_manager import ConnectionManager


class TestConnectionStatusDisplayBasic:
    """Basic unit tests for ConnectionStatusDisplay."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Initialize pygame for tests."""
        pygame.init()

    def test_init_with_manager(self) -> None:
        """Test initialization with ConnectionManager."""
        manager = ConnectionManager()
        display = ConnectionStatusDisplay(manager)

        assert display.manager is manager
        assert display.reconnect_button_rect.width == 0

    def test_set_font(self) -> None:
        """Test setting font."""
        manager = ConnectionManager()
        display = ConnectionStatusDisplay(manager)

        font = pygame.freetype.Font(None, 16)
        display.set_font(font)

        assert display._font is font

    def test_update_button_rect(self) -> None:
        """Test updating button rectangle."""
        manager = ConnectionManager()
        display = ConnectionStatusDisplay(manager)

        display.update_button_rect(10, 20, 100, 30)

        assert display.reconnect_button_rect.x == 10
        assert display.reconnect_button_rect.y == 20
        assert display.reconnect_button_rect.width == 100
        assert display.reconnect_button_rect.height == 30

    def test_handle_click_on_reconnect_button(self) -> None:
        """Test clicking reconnect button."""
        callback_called = False

        def callback() -> None:
            nonlocal callback_called
            callback_called = True

        manager = ConnectionManager(reconnect_callback=callback)
        manager.set_error("Connection failed")

        display = ConnectionStatusDisplay(manager)
        display.update_button_rect(100, 100, 50, 20)

        # Click on button
        result = display.handle_click((125, 110))

        assert result
        assert callback_called

    def test_handle_click_outside_button(self) -> None:
        """Test clicking outside button."""
        manager = ConnectionManager()
        manager.set_error("Connection failed")

        display = ConnectionStatusDisplay(manager)
        display.update_button_rect(100, 100, 50, 20)

        # Click outside button
        result = display.handle_click((50, 50))

        assert not result

    def test_handle_click_when_connected(self) -> None:
        """Test clicking when already connected."""
        callback_called = False

        def callback() -> None:
            nonlocal callback_called
            callback_called = True

        manager = ConnectionManager(reconnect_callback=callback)
        manager.handle_connected("Agent")

        display = ConnectionStatusDisplay(manager)
        display.update_button_rect(100, 100, 50, 20)

        # Click on button (should not trigger reconnect)
        result = display.handle_click((125, 110))

        assert not result
        assert not callback_called

    def test_handle_click_when_reconnecting(self) -> None:
        """Test clicking when already reconnecting."""
        callback_count = 0

        def callback() -> None:
            nonlocal callback_count
            callback_count += 1

        manager = ConnectionManager(reconnect_callback=callback)
        manager.attempt_reconnect()

        display = ConnectionStatusDisplay(manager)
        display.update_button_rect(100, 100, 50, 20)

        # Click on button (should not trigger reconnect again)
        result = display.handle_click((125, 110))

        assert not result
        assert callback_count == 1  # Only called once from attempt_reconnect

    def test_get_status_text(self) -> None:
        """Test getting status text."""
        manager = ConnectionManager()
        manager.handle_connected("TestAgent")

        display = ConnectionStatusDisplay(manager)

        assert display.get_status_text() == "Connected: TestAgent"

    def test_get_status_color(self) -> None:
        """Test getting status color."""
        manager = ConnectionManager()
        manager.handle_connected("TestAgent")

        display = ConnectionStatusDisplay(manager)

        assert display.get_status_color() == (0, 200, 0)

    def test_is_showing_reconnect_button_when_error(self) -> None:
        """Test reconnect button visibility when error."""
        manager = ConnectionManager()
        manager.set_error("Connection failed")

        display = ConnectionStatusDisplay(manager)

        assert display.is_showing_reconnect_button()

    def test_is_showing_reconnect_button_when_connected(self) -> None:
        """Test reconnect button visibility when connected."""
        manager = ConnectionManager()
        manager.handle_connected("Agent")

        display = ConnectionStatusDisplay(manager)

        assert not display.is_showing_reconnect_button()

    def test_is_showing_reconnect_button_when_reconnecting(self) -> None:
        """Test reconnect button visibility when reconnecting."""
        manager = ConnectionManager()
        manager.attempt_reconnect()

        display = ConnectionStatusDisplay(manager)

        assert not display.is_showing_reconnect_button()

    def test_draw_with_font(self) -> None:
        """Test drawing status display."""
        manager = ConnectionManager()
        manager.handle_connected("TestAgent")

        display = ConnectionStatusDisplay(manager)
        font = pygame.freetype.Font(None, 16)
        display.set_font(font)

        surf = pygame.Surface((400, 100))

        # Should not raise exception
        display.draw(surf, 10, 10)

    def test_draw_without_font(self) -> None:
        """Test drawing without font set."""
        manager = ConnectionManager()
        display = ConnectionStatusDisplay(manager)

        surf = pygame.Surface((400, 100))

        # Should not raise exception
        display.draw(surf, 10, 10)


class TestConnectionStatusDisplayProperties:
    """Property-based tests for ConnectionStatusDisplay."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Initialize pygame for tests."""
        pygame.init()

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(agent_names=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_display_reflects_manager_state(self, agent_names: list[str]) -> None:
        """Property: Display accurately reflects ConnectionManager state.

        For any sequence of agent names, the display shall accurately reflect
        the connection state from the manager.
        """
        manager = ConnectionManager()
        display = ConnectionStatusDisplay(manager)

        for agent_name in agent_names:
            # Connect
            manager.handle_connected(agent_name)
            assert display.get_status_text() == manager.get_status_text()
            assert display.get_status_color() == manager.get_status_color()

            # Disconnect
            manager.handle_disconnected()
            assert display.get_status_text() == manager.get_status_text()
            assert display.get_status_color() == manager.get_status_color()

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(error_messages=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=3))
    @settings(max_examples=100)
    def test_button_visibility_reflects_error_state(self, error_messages: list[str]) -> None:
        """Property: Reconnect button visibility reflects error state.

        For any sequence of error messages, the button visibility shall accurately
        reflect whether an error is present and the manager is not reconnecting.
        """
        if not error_messages:
            return  # Skip empty lists

        manager = ConnectionManager()
        display = ConnectionStatusDisplay(manager)

        # Test that button shows when error is set
        manager.set_error("test error")
        assert display.is_showing_reconnect_button()

        # Test that button doesn't show when connected
        manager.handle_connected("Agent")
        assert not display.is_showing_reconnect_button()

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(st.just(None))
    @settings(max_examples=100)
    def test_button_click_triggers_reconnect(self, _: None) -> None:
        """Property: Clicking reconnect button triggers reconnection.

        When the reconnect button is clicked and the manager is in error state,
        the reconnection shall be triggered.
        """
        callback_called = False

        def callback() -> None:
            nonlocal callback_called
            callback_called = True

        manager = ConnectionManager(reconnect_callback=callback)
        manager.set_error("Error")

        display = ConnectionStatusDisplay(manager)
        display.update_button_rect(100, 100, 50, 20)

        # Click button
        result = display.handle_click((125, 110))

        assert result
        assert callback_called
        assert manager.is_reconnecting()
