"""Tests for ConnectionManager class."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from hosts.gui.connection_manager import ConnectionManager


class TestConnectionManagerBasic:
    """Basic unit tests for ConnectionManager."""

    def test_init_disconnected_by_default(self) -> None:
        """Test that ConnectionManager initializes in disconnected state."""
        manager = ConnectionManager()
        assert not manager.connected
        assert not manager.reconnecting
        assert manager.error_message == ""

    def test_init_with_callback(self) -> None:
        """Test that ConnectionManager accepts reconnect callback."""
        callback_called = False

        def callback() -> None:
            nonlocal callback_called
            callback_called = True

        manager = ConnectionManager(reconnect_callback=callback)
        assert manager._reconnect_callback is callback

    def test_handle_connected(self) -> None:
        """Test handle_connected sets connected state."""
        manager = ConnectionManager()
        manager.handle_connected("TestAgent")

        assert manager.connected
        assert not manager.reconnecting
        assert manager.error_message == ""
        assert manager._agent_name == "TestAgent"

    def test_handle_disconnected(self) -> None:
        """Test handle_disconnected clears connection state."""
        manager = ConnectionManager()
        manager.handle_connected("TestAgent")
        manager.handle_disconnected()

        assert not manager.connected
        assert not manager.reconnecting
        assert manager.error_message == ""
        assert manager._agent_name == ""

    def test_attempt_reconnect_sets_reconnecting(self) -> None:
        """Test attempt_reconnect sets reconnecting state."""
        manager = ConnectionManager()
        manager.attempt_reconnect()

        assert manager.reconnecting
        assert not manager.connected

    def test_attempt_reconnect_calls_callback(self) -> None:
        """Test attempt_reconnect invokes callback."""
        callback_called = False

        def callback() -> None:
            nonlocal callback_called
            callback_called = True

        manager = ConnectionManager(reconnect_callback=callback)
        manager.attempt_reconnect()

        assert callback_called

    def test_attempt_reconnect_ignores_duplicate(self) -> None:
        """Test attempt_reconnect ignores duplicate calls."""
        call_count = 0

        def callback() -> None:
            nonlocal call_count
            call_count += 1

        manager = ConnectionManager(reconnect_callback=callback)
        manager.attempt_reconnect()
        manager.attempt_reconnect()

        assert call_count == 1

    def test_set_error_clears_reconnecting(self) -> None:
        """Test set_error clears reconnecting state."""
        manager = ConnectionManager()
        manager.attempt_reconnect()
        manager.set_error("Connection failed")

        assert not manager.reconnecting
        assert manager.error_message == "Connection failed"

    def test_get_status_text_connected(self) -> None:
        """Test get_status_text when connected."""
        manager = ConnectionManager()
        manager.handle_connected("Hephaestus")

        assert manager.get_status_text() == "Connected: Hephaestus"

    def test_get_status_text_disconnected(self) -> None:
        """Test get_status_text when disconnected."""
        manager = ConnectionManager()

        assert manager.get_status_text() == "Disconnected"

    def test_get_status_text_reconnecting(self) -> None:
        """Test get_status_text when reconnecting."""
        manager = ConnectionManager()
        manager.attempt_reconnect()

        assert manager.get_status_text() == "Reconnecting..."

    def test_get_status_text_error(self) -> None:
        """Test get_status_text when error occurs."""
        manager = ConnectionManager()
        manager.set_error("Network timeout")

        assert manager.get_status_text() == "Error: Network timeout"

    def test_get_status_color_connected(self) -> None:
        """Test get_status_color when connected (green)."""
        manager = ConnectionManager()
        manager.handle_connected("Hephaestus")

        assert manager.get_status_color() == (0, 200, 0)

    def test_get_status_color_disconnected(self) -> None:
        """Test get_status_color when disconnected (gray)."""
        manager = ConnectionManager()

        assert manager.get_status_color() == (128, 128, 128)

    def test_get_status_color_reconnecting(self) -> None:
        """Test get_status_color when reconnecting (yellow)."""
        manager = ConnectionManager()
        manager.attempt_reconnect()

        assert manager.get_status_color() == (255, 200, 0)

    def test_get_status_color_error(self) -> None:
        """Test get_status_color when error occurs (red)."""
        manager = ConnectionManager()
        manager.set_error("Connection failed")

        assert manager.get_status_color() == (200, 0, 0)

    def test_is_connected(self) -> None:
        """Test is_connected method."""
        manager = ConnectionManager()
        assert not manager.is_connected()

        manager.handle_connected("Hephaestus")
        assert manager.is_connected()

        manager.handle_disconnected()
        assert not manager.is_connected()

    def test_is_reconnecting(self) -> None:
        """Test is_reconnecting method."""
        manager = ConnectionManager()
        assert not manager.is_reconnecting()

        manager.attempt_reconnect()
        assert manager.is_reconnecting()

        manager.set_error("Failed")
        assert not manager.is_reconnecting()

    def test_has_error(self) -> None:
        """Test has_error method."""
        manager = ConnectionManager()
        assert not manager.has_error()

        manager.set_error("Connection failed")
        assert manager.has_error()

        manager.handle_connected("Hephaestus")
        assert not manager.has_error()

    def test_state_transitions(self) -> None:
        """Test valid state transitions."""
        manager = ConnectionManager()

        # Disconnected -> Connected
        manager.handle_connected("Hephaestus")
        assert manager.connected

        # Connected -> Reconnecting
        manager.attempt_reconnect()
        assert manager.reconnecting

        # Reconnecting -> Error
        manager.set_error("Failed")
        assert manager.error_message == "Failed"

        # Error -> Connected
        manager.handle_connected("Hephaestus")
        assert manager.connected
        assert manager.error_message == ""


class TestConnectionManagerProperties:
    """Property-based tests for ConnectionManager."""

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(agent_names=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_connection_status_reflects_state(self, agent_names: list[str]) -> None:
        """Property: Connection status accurately reflects current state.

        For any sequence of agent names, the connection status shall accurately
        reflect whether the manager is connected, disconnected, or reconnecting.
        """
        manager = ConnectionManager()

        for agent_name in agent_names:
            # Connect
            manager.handle_connected(agent_name)
            assert manager.is_connected()
            assert manager.get_status_text() == f"Connected: {agent_name}"
            assert manager.get_status_color() == (0, 200, 0)

            # Disconnect
            manager.handle_disconnected()
            assert not manager.is_connected()
            assert manager.get_status_text() == "Disconnected"
            assert manager.get_status_color() == (128, 128, 128)

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(error_messages=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_error_status_reflects_errors(self, error_messages: list[str]) -> None:
        """Property: Error status accurately reflects error state.

        For any sequence of error messages, the connection status shall accurately
        reflect the error state with appropriate status text and color.
        """
        manager = ConnectionManager()

        for error_msg in error_messages:
            manager.set_error(error_msg)
            assert manager.has_error()
            assert manager.get_status_text() == f"Error: {error_msg}"
            assert manager.get_status_color() == (200, 0, 0)
            assert not manager.is_connected()

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(st.just(None))
    @settings(max_examples=100)
    def test_reconnecting_status_reflects_state(self, _: None) -> None:
        """Property: Reconnecting status accurately reflects reconnection state.

        When attempting to reconnect, the connection status shall accurately
        reflect the reconnecting state with appropriate status text and color.
        """
        manager = ConnectionManager()

        manager.attempt_reconnect()
        assert manager.is_reconnecting()
        assert manager.get_status_text() == "Reconnecting..."
        assert manager.get_status_color() == (255, 200, 0)

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(agent_name=st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_connected_state_clears_errors(self, agent_name: str) -> None:
        """Property: Connecting clears error state.

        For any agent name, when connecting after an error, the error state
        shall be cleared and the status shall reflect the connected state.
        """
        manager = ConnectionManager()

        # Set error
        manager.set_error("Previous error")
        assert manager.has_error()

        # Connect
        manager.handle_connected(agent_name)
        assert not manager.has_error()
        assert manager.is_connected()
        assert manager.error_message == ""

    # Feature: gui-improvements, Property 6: Connection Status Accuracy
    @given(st.just(None))
    @settings(max_examples=100)
    def test_disconnected_state_clears_all(self, _: None) -> None:
        """Property: Disconnecting clears all state.

        When disconnecting, all connection state (connected, reconnecting, errors)
        shall be cleared.
        """
        manager = ConnectionManager()

        # Set up various states
        manager.handle_connected("Agent")
        manager.attempt_reconnect()
        manager.set_error("Error")

        # Disconnect
        manager.handle_disconnected()

        assert not manager.is_connected()
        assert not manager.is_reconnecting()
        assert not manager.has_error()
        assert manager._agent_name == ""
        assert manager.error_message == ""
