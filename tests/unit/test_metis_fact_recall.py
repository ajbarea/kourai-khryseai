"""Metis prompt enrichment with project-scoped facts (M17 Phase 1 close-out).

The pause helper landed in #84 (write side); this test surface covers
the read-side that threads ``build_fact_context(project_id=...)`` into
Metis's planning prompt so PAUSE-resolved preferences surface as
``=== PLAYER CONTEXT ===`` entries on the next session for the same
project. Closing the recall half of the Phase 1 DOD: a HOTL answer in
project A is recalled in project A and NOT in project B.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from a2a.types import Message, Part, Role, TextPart

from kourai_common.player import _ensure_player_tables

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def _isolate_player_db(tmp_path, monkeypatch):
    """Sandbox the SQLite player DB so tests never touch the host store."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            context_id TEXT, agent_name TEXT, idx INTEGER,
            role TEXT, content TEXT, summarized BOOLEAN DEFAULT 0,
            PRIMARY KEY (context_id, agent_name, idx)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_states (
            context_id TEXT, agent_name TEXT, state_json TEXT,
            PRIMARY KEY (context_id, agent_name)
        )
        """
    )
    conn.commit()

    import kourai_common.player as player_mod

    player_mod._tables_initialized = False
    _ensure_player_tables(conn)

    monkeypatch.setattr(player_mod, "_get_player_db", lambda: conn)
    yield conn
    conn.close()


# ── Helpers ─────────────────────────────────────────────────────────────


async def _async_gen(items: list[str]):
    for item in items:
        yield item


def _make_context(user_input: str, context_id: str | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_input
    ctx.current_task = None
    ctx.message = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_input or "placeholder"))],
        message_id=str(uuid4()),
        context_id=context_id or uuid4().hex,
    )
    return ctx


def _make_queue() -> AsyncMock:
    return AsyncMock()


# ── Pure-function audit ─────────────────────────────────────────────────


class TestBuildMetisContextParts:
    """Facts go first when present, are skipped when absent."""

    def test_no_player_id_skips_fact_block(self):
        from agents.metis.agent import _build_metis_context_parts

        parts = _build_metis_context_parts(
            project_context="Git status: clean",
            file_contents=None,
            docs_context="",
            player_id=None,
            project_id=None,
        )
        assert not any("PLAYER CONTEXT" in p for p in parts)

    def test_empty_facts_does_not_inject_block(self):
        from agents.metis.agent import _build_metis_context_parts

        with patch("agents.metis.agent.build_fact_context", return_value="") as fact_mock:
            parts = _build_metis_context_parts(
                project_context="",
                file_contents=None,
                docs_context="",
                player_id="player-uuid",
                project_id="abc123def4567890",
            )
        fact_mock.assert_called_once_with(
            "player-uuid", agent_name="metis", project_id="abc123def4567890"
        )
        assert not any("PLAYER CONTEXT" in p for p in parts)

    def test_player_facts_lead_the_context_block(self):
        from agents.metis.agent import _build_metis_context_parts

        with patch(
            "agents.metis.agent.build_fact_context",
            return_value="=== PLAYER CONTEXT ===\n- coverage_target: 80%",
        ):
            parts = _build_metis_context_parts(
                project_context="Git status: clean",
                file_contents={"export.py": "def export(): pass"},
                docs_context="docs",
                player_id="player-uuid",
                project_id="abc123def4567890",
            )
        assert parts[0].startswith("=== PLAYER CONTEXT ===")
        assert any("docs" in p for p in parts)
        assert any("PROJECT CONTEXT" in p for p in parts)
        assert any("export.py" in p for p in parts)


# ── create_spec_stream threading ────────────────────────────────────────


class TestCreateSpecStreamThreadsFacts:
    @pytest.mark.asyncio
    async def test_passes_player_id_and_project_id_to_build_fact_context(self):
        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["messages"] = args[1]
            yield "spec"

        with (
            patch("agents.metis.agent.chat_stream", new=_stream),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                AsyncMock(return_value=""),
            ),
            patch(
                "agents.metis.agent.build_fact_context",
                return_value="=== PLAYER CONTEXT ===\n- coverage_target: 80%",
            ) as fact_mock,
        ):
            from agents.metis.agent import create_spec_stream

            async for _ in create_spec_stream(
                "idea",
                player_id="player-uuid",
                project_id="abc123def4567890",
            ):
                pass

        fact_mock.assert_called_once_with(
            "player-uuid", agent_name="metis", project_id="abc123def4567890"
        )
        user_content = captured["messages"][-1]["content"]
        assert "PLAYER CONTEXT" in user_content
        assert "coverage_target: 80%" in user_content

    @pytest.mark.asyncio
    async def test_no_player_id_does_not_call_build_fact_context(self):
        async def _stream(*args, **kwargs):
            yield "spec"

        with (
            patch("agents.metis.agent.chat_stream", new=_stream),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                AsyncMock(return_value=""),
            ),
            patch("agents.metis.agent.build_fact_context") as fact_mock,
        ):
            from agents.metis.agent import create_spec_stream

            async for _ in create_spec_stream("idea"):
                pass
        fact_mock.assert_not_called()


# ── Executor wiring ─────────────────────────────────────────────────────


class TestExecutorRecallWiring:
    @pytest.mark.asyncio
    async def test_executor_passes_player_id_and_project_id_when_tag_present(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            yield "spec"

        ctx = _make_context("[project_root: /var/forge/proj-a]\nimplement CSV export")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        fake_profile = MagicMock(player_id="player-uuid")
        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch("agents.metis.agent_executor.create_spec_stream", new=_stream),
            patch("agents.metis.agent_executor.send_working_status"),
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=fake_profile,
            ),
        ):
            await executor.execute(ctx, queue)

        assert captured["kwargs"].get("player_id") == "player-uuid"
        assert captured["kwargs"].get("project_id") is not None

    @pytest.mark.asyncio
    async def test_executor_passes_none_project_id_when_no_tag(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            yield "spec"

        ctx = _make_context("just plan a CSV exporter — no project tag")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        fake_profile = MagicMock(player_id="player-uuid")
        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch("agents.metis.agent_executor.create_spec_stream", new=_stream),
            patch("agents.metis.agent_executor.send_working_status"),
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=fake_profile,
            ),
        ):
            await executor.execute(ctx, queue)

        assert captured["kwargs"].get("project_id") is None

    @pytest.mark.asyncio
    async def test_executor_passes_none_player_id_when_no_profile(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            yield "spec"

        ctx = _make_context("[project_root: /var/forge/proj-a]\nplan a feature")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch("agents.metis.agent_executor.create_spec_stream", new=_stream),
            patch("agents.metis.agent_executor.send_working_status"),
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute(ctx, queue)

        assert captured["kwargs"].get("player_id") is None


# ── Phase 1 DOD recall property ─────────────────────────────────────────


class TestM17Phase1RecallProperty:
    """The Phase 1 DOD half this PR closes — production recall path.

    Persistence-then-recall through ``create_spec_stream``'s prompt
    construction (LLM stream stays mocked).
    """

    @pytest.mark.asyncio
    async def test_metis_recalls_project_a_fact_only_in_project_a(self, _isolate_player_db):
        from kourai_common.facts import PlayerFact, store_facts

        proj_a = "abc123def4567890"
        proj_b = "fedcba9876543210"

        store_facts(
            "recall-test",
            [
                PlayerFact(
                    body="coverage_target: 80%",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id=proj_a,
                )
            ],
        )

        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["messages"] = args[1]
            yield "spec"

        from agents.metis.agent import create_spec_stream

        with (
            patch("agents.metis.agent.chat_stream", new=_stream),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                AsyncMock(return_value=""),
            ),
        ):
            async for _ in create_spec_stream(
                "plan a CSV exporter",
                player_id="recall-test",
                project_id=proj_a,
            ):
                pass
            content_a = captured["messages"][-1]["content"]

            async for _ in create_spec_stream(
                "plan a CSV exporter",
                player_id="recall-test",
                project_id=proj_b,
            ):
                pass
            content_b = captured["messages"][-1]["content"]

        assert "coverage_target: 80%" in content_a, (
            "Metis should recall project A's preference in project A"
        )
        assert "coverage_target: 80%" not in content_b, (
            "Metis should NOT recall project A's preference in project B"
        )
