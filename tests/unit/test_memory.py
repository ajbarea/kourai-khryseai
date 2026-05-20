"""Tests for kourai_common.memory primitives shared across agents."""

from __future__ import annotations

import sqlite3

import pytest

from kourai_common import memory as mem


@pytest.fixture(autouse=True)
def _isolate_memory_db(tmp_path, monkeypatch):
    """Each test gets a fresh in-memory SQLite DB so the production
    ``.cache/agent_memory.db`` is never touched and test ordering is
    irrelevant. Mirrors the pattern in ``test_forge_session.py``."""
    db_path = tmp_path / "agent_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    # Recreate the schema add_message etc. expect.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            context_id TEXT,
            agent_name TEXT,
            idx INTEGER,
            role TEXT,
            content TEXT,
            summarized BOOLEAN DEFAULT 0,
            PRIMARY KEY (context_id, agent_name, idx)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_states (
            context_id TEXT,
            agent_name TEXT,
            state_json TEXT,
            PRIMARY KEY (context_id, agent_name)
        )
        """
    )
    conn.commit()

    monkeypatch.setattr(mem, "_conn", conn)
    yield conn
    conn.close()


class TestListAgentsWithHistory:
    """``list_agents_with_history`` powers the ``/compact`` slash command's
    "discover which agent buckets exist for this conversation" step. It
    must return distinct agent names, sorted, scoped to the asked-for
    context_id only."""

    def test_returns_empty_for_unknown_context(self):
        assert mem.list_agents_with_history("unknown-ctx") == []

    def test_returns_distinct_agents_for_a_context(self):
        mem.add_message("ctx-1", "metis", "user", "plan")
        mem.add_message("ctx-1", "metis", "assistant", "spec")
        mem.add_message("ctx-1", "techne", "user", "build")
        assert mem.list_agents_with_history("ctx-1") == ["metis", "techne"]

    def test_does_not_leak_across_contexts(self):
        mem.add_message("ctx-1", "metis", "user", "plan")
        mem.add_message("ctx-2", "techne", "user", "build")
        assert mem.list_agents_with_history("ctx-1") == ["metis"]
        assert mem.list_agents_with_history("ctx-2") == ["techne"]

    def test_returns_sorted_for_stable_ordering(self):
        mem.add_message("ctx-1", "techne", "user", "x")
        mem.add_message("ctx-1", "kallos", "user", "y")
        mem.add_message("ctx-1", "metis", "user", "z")
        # Alpha-sorted so the /compact comms-window roster is deterministic
        assert mem.list_agents_with_history("ctx-1") == ["kallos", "metis", "techne"]


class TestListKnownContexts:
    """Powers ``/session list``."""

    def test_empty_store_returns_empty(self):
        assert mem.list_known_contexts() == []

    def test_busiest_first_ordering(self):
        for _ in range(5):
            mem.add_message("ctx-busy", "metis", "user", "m")
        for _ in range(2):
            mem.add_message("ctx-quiet", "techne", "user", "q")
        rows = mem.list_known_contexts()
        assert rows[0][0] == "ctx-busy"
        assert rows[0][1] == 5
        assert rows[1][0] == "ctx-quiet"
        assert rows[1][1] == 2

    def test_agent_count_distinct(self):
        mem.add_message("ctx-multi", "metis", "user", "a")
        mem.add_message("ctx-multi", "metis", "user", "b")
        mem.add_message("ctx-multi", "techne", "user", "c")
        rows = mem.list_known_contexts()
        assert rows[0] == ("ctx-multi", 3, 2)

    def test_respects_limit(self):
        for i in range(5):
            mem.add_message(f"ctx-{i}", "metis", "user", "msg")
        rows = mem.list_known_contexts(limit=3)
        assert len(rows) == 3


class TestCloneContext:
    """Powers ``/session fork``."""

    def test_clones_messages_and_state(self):
        mem.add_message("src-ctx", "metis", "user", "plan")
        mem.add_message("src-ctx", "metis", "assistant", "spec")
        mem.save_agent_state(
            "src-ctx",
            "metis",
            {
                "thread_id": "src-ctx",
                "goal_hierarchy": ["x"],
                "checkpoints": [],
                "semantic_summary": "",
                "metadata": {},
            },
        )
        count = mem.clone_context("src-ctx", "dst-ctx")
        assert count == 2
        assert mem.get_history("dst-ctx", "metis") == [
            {"role": "user", "content": "plan"},
            {"role": "assistant", "content": "spec"},
        ]
        assert mem.get_agent_state("dst-ctx", "metis")["goal_hierarchy"] == ["x"]

    def test_clone_refuses_to_overwrite(self):
        mem.add_message("src", "metis", "user", "a")
        mem.add_message("dst", "metis", "user", "b")
        with pytest.raises(ValueError, match="already has messages"):
            mem.clone_context("src", "dst")

    def test_clone_preserves_source(self):
        mem.add_message("src", "metis", "user", "a")
        mem.clone_context("src", "dst-new")
        # Source unchanged.
        assert mem.get_history("src", "metis") == [{"role": "user", "content": "a"}]
        # Destination got the copy.
        assert mem.get_history("dst-new", "metis") == [{"role": "user", "content": "a"}]
