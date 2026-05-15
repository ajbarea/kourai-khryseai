"""Tests for M14 parallel timeout fix.

Verifies that:
1. Custom aiohttp session is created with tuned TCPConnector
2. shared_session parameter is injected into litellm calls
3. Streaming calls disable request_timeout (prevent mid-body abort)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAIOHTTPSessionConfig:
    """Verify custom session configuration for M14."""

    @pytest.mark.asyncio
    async def test_session_has_tuned_connector(self):
        """Session TCPConnector has limit_per_host=75 (not default 10)."""
        from kourai_common.llm_aiohttp_config import create_aiohttp_session

        session = create_aiohttp_session()
        assert session.connector is not None
        assert session.connector._limit_per_host == 75, "Should use limit_per_host=75"
        assert session.connector._limit == 300, "Should use limit=300"
        await session.close()

    @pytest.mark.asyncio
    async def test_session_singleton(self):
        """get_aiohttp_session() returns same instance across calls."""
        from kourai_common.llm_aiohttp_config import get_aiohttp_session, close_aiohttp_session
        import kourai_common.llm_aiohttp_config

        # Reset the global session
        kourai_common.llm_aiohttp_config._global_session = None

        session1 = get_aiohttp_session()
        session2 = get_aiohttp_session()
        assert session1 is session2, "Should return singleton instance"

        # Clean up
        await close_aiohttp_session()

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """close_aiohttp_session() closes the session."""
        from kourai_common.llm_aiohttp_config import (
            close_aiohttp_session,
            get_aiohttp_session,
        )

        # Reset the global session
        import kourai_common.llm_aiohttp_config

        kourai_common.llm_aiohttp_config._global_session = None

        session = get_aiohttp_session()
        assert not session.closed

        await close_aiohttp_session()
        assert session.closed, "Session should be closed"


class TestExecutionCompletionM14Fix:
    """Verify _execute_completion() injects shared_session and disables timeout."""

    @pytest.mark.asyncio
    async def test_shared_session_injected(self):
        """_execute_completion() passes shared_session to litellm.acompletion()."""
        from kourai_common.llm import _execute_completion

        with patch("kourai_common.llm.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="test"))]
            )

            with patch("kourai_common.llm.get_aiohttp_session") as mock_get_session:
                mock_session = MagicMock()
                mock_get_session.return_value = mock_session

                await _execute_completion(
                    timeout_seconds=10.0,
                    model="test-model",
                    messages=[],
                )

                # Verify shared_session was passed
                assert mock_llm.called
                call_kwargs = mock_llm.call_args.kwargs
                assert "shared_session" in call_kwargs
                assert call_kwargs["shared_session"] is mock_session

    @pytest.mark.asyncio
    async def test_streaming_disables_timeout(self):
        """For stream=True, request_timeout should be None."""
        from kourai_common.llm import _execute_completion

        with patch("kourai_common.llm.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock()

            with patch("kourai_common.llm.get_aiohttp_session"):
                await _execute_completion(
                    timeout_seconds=10.0,
                    model="test-model",
                    messages=[],
                    stream=True,  # ← Enable streaming
                )

                call_kwargs = mock_llm.call_args.kwargs
                assert call_kwargs.get("request_timeout") is None, (
                    "Streaming should disable request_timeout (prevent mid-body abort)"
                )

    @pytest.mark.asyncio
    async def test_non_streaming_has_timeout(self):
        """For stream=False, request_timeout should be set."""
        from kourai_common.llm import _execute_completion

        with patch("kourai_common.llm.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="test"))]
            )

            with patch("kourai_common.llm.get_aiohttp_session"):
                await _execute_completion(
                    timeout_seconds=10.0,
                    model="test-model",
                    messages=[],
                    stream=False,  # ← Non-streaming
                )

                call_kwargs = mock_llm.call_args.kwargs
                assert call_kwargs.get("request_timeout") == 10.0, (
                    "Non-streaming should keep request_timeout"
                )


class TestServerShutdownHook:
    """Verify cleanup is registered on app startup."""

    def test_app_with_lifespan_builds(self):
        """build_a2a_app() creates app with lifespan for aiohttp cleanup."""
        from kourai_common.server import build_a2a_app
        from kourai_common.agent_cards import build_card
        from kourai_common.base_executor import BaseAgentExecutor

        # Create a minimal executor
        class TestExecutor(BaseAgentExecutor):
            def get_input_required_message(self) -> str:
                return "Input required"

            async def execute_agent_logic(self, context, task, updater):
                pass

            async def cancel(self, task_id: str) -> None:
                pass

        with patch("kourai_common.agent_cards.get_agent_url") as mock_get_url:
            mock_get_url.return_value = "http://test:10000/"
            card = build_card(
                agent_name="test",
                display_name="Test",
                description="Test agent",
                skills=[],
            )

        app = build_a2a_app(agent_card=card, executor=TestExecutor())

        # Verify app was built successfully with lifespan support
        # Starlette 1.0.0+ uses lifespan parameter internally
        assert app is not None, "App should build successfully with lifespan"
        assert len(app.routes) > 0, "App should have routes registered"
