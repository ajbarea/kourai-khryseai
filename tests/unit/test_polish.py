"""Kourai common: LLM timeout handling, graceful degradation, CLI flags."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kourai_common.llm import LLMError, LLMResponseError, LLMTimeoutError


class TestLLMExceptions:
    """Test custom LLM exception hierarchy."""

    def test_timeout_error_fields(self):
        exc = LLMTimeoutError("techne", 120.0)
        assert exc.agent_name == "techne"
        assert exc.timeout == 120.0
        assert "120" in str(exc)

    def test_response_error_fields(self):
        exc = LLMResponseError("mneme", "empty response")
        assert exc.agent_name == "mneme"
        assert "empty response" in str(exc)

    def test_inheritance(self):
        assert issubclass(LLMTimeoutError, LLMError)
        assert issubclass(LLMResponseError, LLMError)
        assert issubclass(LLMError, Exception)


class TestChatTimeout:
    """Test LLM chat with timeout wrapping."""

    @pytest.mark.asyncio
    async def test_chat_raises_timeout(self):
        async def slow_completion(**kwargs):
            await asyncio.sleep(10)

        with patch("kourai_common.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = slow_completion
            with patch("kourai_common.llm.AGENT_TIMEOUTS", {"mneme": 0.01}):
                from kourai_common.llm import chat

                with pytest.raises(LLMTimeoutError) as exc_info:
                    await chat("mneme", [{"role": "user", "content": "hi"}])
                assert exc_info.value.agent_name == "mneme"

    @pytest.mark.asyncio
    async def test_chat_raises_on_empty_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""

        with patch("kourai_common.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            from kourai_common.llm import chat

            with pytest.raises(LLMResponseError):
                await chat("mneme", [{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_chat_returns_content(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"

        with patch("kourai_common.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            from kourai_common.llm import chat

            result = await chat("mneme", [{"role": "user", "content": "hi"}])
            assert result == "Hello!"


class TestGracefulDegradation:
    """Test pipeline skipping unreachable agents."""

    @pytest.mark.asyncio
    async def test_skips_unreachable_agent(self):
        """Unreachable agent is skipped, pipeline continues with remaining agents."""
        mock_card = MagicMock()
        mock_card.name = "TestAgent"

        call_order = []

        def make_conn(agent_name, url):
            conn = AsyncMock()
            conn.card = mock_card
            conn.close = AsyncMock()
            if agent_name == "kallos":
                conn.connect = AsyncMock(side_effect=ConnectionError("refused"))
            else:
                conn.connect = AsyncMock()

                async def send_fn(text, ctx_id, _name=agent_name):
                    call_order.append(_name)
                    return f"output from {_name}"

                conn.send = AsyncMock(side_effect=send_fn)
            return conn

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["techne", "kallos", "mneme"], "implement X"
            ):
                statuses.append((agent, status))

            # Kallos should be skipped
            skip_msgs = [s for s in statuses if "Skipped" in s[1]]
            assert len(skip_msgs) == 1
            assert skip_msgs[0][0] == "kallos"

            # Pipeline should still complete
            complete_msgs = [s for s in statuses if s[1] == "Pipeline complete"]
            assert len(complete_msgs) == 1

            # Techne and mneme should have run
            assert "techne" in call_order
            assert "mneme" in call_order

    @pytest.mark.asyncio
    async def test_aborts_when_all_agents_unreachable(self):
        """Pipeline aborts if no agents can be reached."""

        def make_conn(agent_name, url):
            conn = AsyncMock()
            conn.card = MagicMock()
            conn.connect = AsyncMock(side_effect=ConnectionError("refused"))
            conn.close = AsyncMock()
            return conn

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["techne", "kallos"], "implement X"
            ):
                statuses.append((agent, status))

            abort_msgs = [s for s in statuses if "No agents reachable" in s[1]]
            assert len(abort_msgs) == 1


class TestChatStreamFallback:
    """Test chat_stream behavior for non-standard streaming payloads."""

    @pytest.mark.asyncio
    async def test_chat_stream_falls_back_when_stream_has_no_text(self):
        """If stream chunks carry no text, fallback non-stream completion is used."""
        from kourai_common.llm import chat_stream

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = None
        chunk.choices[0].message = MagicMock()
        chunk.choices[0].message.content = None

        async def empty_text_stream():
            yield chunk

        fallback_response = MagicMock()
        fallback_response.choices = [MagicMock()]
        fallback_response.choices[0].message.content = "MOCK RESPONSE"

        with (
            patch(
                "kourai_common.llm._build_contextual_messages",
                AsyncMock(return_value=[{"role": "user", "content": "hi"}]),
            ),
            patch(
                "kourai_common.llm._execute_completion",
                AsyncMock(side_effect=[empty_text_stream(), fallback_response]),
            ),
            patch("kourai_common.llm.add_message"),
        ):
            chunks = [
                c
                async for c in chat_stream(
                    "mneme",
                    [{"role": "user", "content": "hi"}],
                    context_id="ctx-1",
                )
            ]

        assert chunks == ["MOCK RESPONSE"]


class TestCLIVerboseFlag:
    """Test CLI --verbose option exists and formats output."""

    def test_main_accepts_verbose(self):
        """CLI main command accepts --verbose flag."""
        pytest.importorskip("asyncclick")
        from hosts.cli.__main__ import main

        # Verify the click command has the verbose parameter
        param_names = [p.name for p in main.params]
        assert "verbose" in param_names

    def test_main_accepts_v_shorthand(self):
        """CLI main command accepts -v shorthand."""
        pytest.importorskip("asyncclick")
        from hosts.cli.__main__ import main

        for p in main.params:
            if p.name == "verbose":
                assert "-v" in (p.opts or []) or any("-v" in o for o in (p.secondary_opts or []))
                break
