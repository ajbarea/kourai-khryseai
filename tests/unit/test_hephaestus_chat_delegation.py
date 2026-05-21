"""Hephaestus chat delegation: real A2A invocation of the target agent.

These tests pin the contract that a `CHAT:<agent>: ...` route opens
a real `RemoteAgentConnection` against the target's container and
forwards its status / result events back through Hephaestus's task
updater — replacing the prior ventriloquy where Hephaestus narrated
the router's gloss with the target's emoji and never invoked the
target's executor.

Each test patches `RemoteAgentConnection` so no live network is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.hephaestus.agent_executor import HephaestusAgentExecutor
from agents.hephaestus.remote_connections import AgentInputRequired

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_executor() -> HephaestusAgentExecutor:
    return HephaestusAgentExecutor()


def _make_task() -> MagicMock:
    task = MagicMock()
    task.context_id = "ctx-test"
    return task


def _make_updater() -> MagicMock:
    return MagicMock()


def _async_iter_from(events: list[tuple[str, str]]) -> Any:
    async def gen(*_args: Any, **_kwargs: Any) -> AsyncIterator[tuple[str, str]]:
        for ev in events:
            yield ev

    return gen


class TestDelegateChatHappyPath:
    @pytest.mark.asyncio
    async def test_companion_status_and_result_forwarded(self):
        """Aidos's status + result both reach Hephaestus's updater."""
        with patch(
            "agents.hephaestus.agent_executor.RemoteAgentConnection",
        ) as mock_conn_cls:
            conn = AsyncMock()
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            conn.send = _async_iter_from(
                [
                    ("status", "\U0001f50d Scanning for slop..."),
                    ("result", "FOUND 2 slop word(s): blazingly fast, leverage"),
                ]
            )
            mock_conn_cls.return_value = conn

            with patch(
                "agents.hephaestus.agent_executor.send_working_status",
                new_callable=AsyncMock,
            ) as mock_status:
                executor = _make_executor()
                result = await executor._delegate_chat_to_agent(
                    "aidos",
                    user_input="@aidos check this for jargon",
                    chat_body="Player wants jargon-checking.",
                    task=_make_task(),
                    updater=_make_updater(),
                    forge_meta=None,
                )

                assert result.input_required is False
                assert "FOUND 2 slop" in result.result_text

                forwarded = [c.args[2] for c in mock_status.call_args_list]
                assert any("Scanning for slop" in m for m in forwarded)
                assert any("FOUND 2 slop" in m for m in forwarded)

    @pytest.mark.asyncio
    async def test_connection_target_url_is_companion(self):
        """The RemoteAgentConnection is built for the routed agent, not Hephaestus."""
        with patch(
            "agents.hephaestus.agent_executor.RemoteAgentConnection",
        ) as mock_conn_cls:
            conn = AsyncMock()
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            conn.send = _async_iter_from([("result", "ok")])
            mock_conn_cls.return_value = conn

            with patch(
                "agents.hephaestus.agent_executor.send_working_status",
                new_callable=AsyncMock,
            ):
                executor = _make_executor()
                await executor._delegate_chat_to_agent(
                    "puck",
                    user_input="@puck what's the workflow?",
                    chat_body="Tutorial request.",
                    task=_make_task(),
                    updater=_make_updater(),
                    forge_meta=None,
                )

                args, _ = mock_conn_cls.call_args
                assert args[0] == "puck"
                assert "puck:" in args[1]


class TestDelegateChatFallback:
    @pytest.mark.asyncio
    async def test_unreachable_companion_falls_back_to_hephaestus_voice(self):
        """If the companion's container is down, Hephaestus covers explicitly."""
        with patch(
            "agents.hephaestus.agent_executor.RemoteAgentConnection",
        ) as mock_conn_cls:
            conn = AsyncMock()
            conn.connect = AsyncMock(side_effect=ConnectionError("aidos down"))
            conn.close = AsyncMock()
            mock_conn_cls.return_value = conn

            with patch(
                "agents.hephaestus.agent_executor.send_working_status",
                new_callable=AsyncMock,
            ) as mock_status:
                executor = _make_executor()
                result = await executor._delegate_chat_to_agent(
                    "aidos",
                    user_input="@aidos check this",
                    chat_body="Player wants jargon-checking.",
                    task=_make_task(),
                    updater=_make_updater(),
                    forge_meta=None,
                )

                assert result.input_required is False
                assert "jargon-checking" in result.result_text

                emitted = [c.args[2] for c in mock_status.call_args_list]
                assert any("aidos is asleep" in m for m in emitted)

    @pytest.mark.asyncio
    async def test_mid_stream_error_falls_back(self):
        """If conn.send() raises after connect succeeded, Hephaestus covers."""

        async def boom(*_a: Any, **_kw: Any) -> AsyncIterator[tuple[str, str]]:
            yield ("status", "\U0001f50d Scanning...")
            raise RuntimeError("upstream blew up")

        with patch(
            "agents.hephaestus.agent_executor.RemoteAgentConnection",
        ) as mock_conn_cls:
            conn = AsyncMock()
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            conn.send = boom
            mock_conn_cls.return_value = conn

            with patch(
                "agents.hephaestus.agent_executor.send_working_status",
                new_callable=AsyncMock,
            ) as mock_status:
                executor = _make_executor()
                result = await executor._delegate_chat_to_agent(
                    "aletheia",
                    user_input="@aletheia verify this",
                    chat_body="Citation request.",
                    task=_make_task(),
                    updater=_make_updater(),
                    forge_meta=None,
                )

                assert result.input_required is False
                emitted = [c.args[2] for c in mock_status.call_args_list]
                assert any("dropped the thread" in m for m in emitted)


class TestDelegateChatInputRequired:
    @pytest.mark.asyncio
    async def test_companion_input_required_bubbles_up(self):
        """If the companion raises AgentInputRequired, it surfaces as INPUT_REQUIRED."""

        async def needs_input(*_a: Any, **_kw: Any) -> AsyncIterator[tuple[str, str]]:
            if False:  # pragma: no cover — keeps function an async generator
                yield ("status", "")
            raise AgentInputRequired("cupid", "Whose affinity should I read?")

        with patch(
            "agents.hephaestus.agent_executor.RemoteAgentConnection",
        ) as mock_conn_cls:
            conn = AsyncMock()
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            conn.send = needs_input
            mock_conn_cls.return_value = conn

            with (
                patch(
                    "agents.hephaestus.agent_executor.send_working_status",
                    new_callable=AsyncMock,
                ),
                patch(
                    "agents.hephaestus.agent_executor.send_input_required",
                    new_callable=AsyncMock,
                ) as mock_input_req,
            ):
                executor = _make_executor()
                result = await executor._delegate_chat_to_agent(
                    "cupid",
                    user_input="@cupid how are things?",
                    chat_body="Affinity inquiry.",
                    task=_make_task(),
                    updater=_make_updater(),
                    forge_meta=None,
                )

                assert result.input_required is True
                assert mock_input_req.call_count == 1
                question_text = mock_input_req.call_args.args[2]
                assert "cupid needs your input" in question_text
                assert "Whose affinity" in question_text
