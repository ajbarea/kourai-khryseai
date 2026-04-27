"""Memory management for Kourai agents, including episodic (message history) and semantic (structured state) memory.
- Episodic Memory: Stores raw message history (role, content) for each agent and context. Supports retrieval with limits and summarization tracking.
- Semantic Memory: Stores a structured state object (thread_id, goal_hierarchy, checkpoints, semantic_summary, metadata) for each agent and context. Provides get/set functions for state management.
- Uses SQLite for persistence, with a simple schema for messages and agent states.
"""

import contextlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, TypedDict

log = logging.getLogger(__name__)

DB_PATH = Path(".cache/agent_memory.db")
_conn = None


class AgentState(TypedDict):
    thread_id: str
    goal_hierarchy: list[str]
    checkpoints: list[dict]
    semantic_summary: str
    metadata: dict[str, Any]


def _get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute(
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
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_states (
                context_id TEXT,
                agent_name TEXT,
                state_json TEXT,
                PRIMARY KEY (context_id, agent_name)
            )
            """
        )

        # Ensure 'summarized' column exists for backwards compatibility if table already existed
        with contextlib.suppress(sqlite3.OperationalError):
            _conn.execute("ALTER TABLE messages ADD COLUMN summarized BOOLEAN DEFAULT 0")

        _conn.commit()
    return _conn


def get_agent_state(context_id: str, agent_name: str) -> AgentState:
    """Retrieve the structured state object for a given context and agent."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT state_json FROM agent_states WHERE context_id = ? AND agent_name = ?",
        (context_id, agent_name),
    )
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])

    return {
        "thread_id": context_id,
        "goal_hierarchy": [],
        "checkpoints": [],
        "semantic_summary": "",
        "metadata": {},
    }


def save_agent_state(context_id: str, agent_name: str, state: AgentState) -> None:
    """Persist the structured state object."""
    conn = _get_db()
    conn.execute(
        """
        INSERT INTO agent_states (context_id, agent_name, state_json)
        VALUES (?, ?, ?)
        ON CONFLICT(context_id, agent_name) DO UPDATE SET state_json=excluded.state_json
        """,
        (context_id, agent_name, json.dumps(state)),
    )
    conn.commit()


def get_history(
    context_id: str, agent_name: str, limit: int | None = None, include_summarized: bool = True
) -> list[dict[str, Any]]:
    """Retrieve message history (Episodic/Working memory).

    Args:
        context_id: Thread/context ID.
        agent_name: Name of the agent.
        limit: Max number of recent messages to return (Working Memory limit).
        include_summarized: If False, only returns messages that haven't been summarized yet.
    """
    conn = _get_db()
    query = "SELECT role, content, idx FROM messages WHERE context_id = ? AND agent_name = ?"
    params = [context_id, agent_name]

    if not include_summarized:
        query += " AND summarized = 0"

    query += " ORDER BY idx DESC"

    if limit is not None:
        query += f" LIMIT {limit}"

    cursor = conn.execute(query, tuple(params))

    # We ordered descending to get the most recent, now reverse to chronological
    rows = cursor.fetchall()
    rows.reverse()

    history = []
    for role, content_str, _ in rows:
        try:
            content = json.loads(content_str)
        except json.JSONDecodeError:
            content = content_str
        history.append({"role": role, "content": content})
    return history


def get_unsummarized_messages(context_id: str, agent_name: str) -> list[dict[str, Any]]:
    """Get all messages that haven't been summarized into the semantic memory yet."""
    return get_history(context_id, agent_name, include_summarized=False)


def mark_messages_summarized(context_id: str, agent_name: str, max_idx_inclusive: int) -> None:
    """Mark older messages as summarized."""
    conn = _get_db()
    conn.execute(
        "UPDATE messages SET summarized = 1 WHERE context_id = ? AND agent_name = ? AND idx <= ?",
        (context_id, agent_name, max_idx_inclusive),
    )
    conn.commit()


def get_max_unsummarized_idx(context_id: str, agent_name: str) -> int:
    """Get the highest index of unsummarized messages."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT MAX(idx) FROM messages WHERE context_id = ? AND agent_name = ? AND summarized = 0",
        (context_id, agent_name),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] is not None else -1


def list_agents_with_history(context_id: str) -> list[str]:
    """Return distinct ``agent_name`` values that have any messages stored
    against ``context_id``.

    Used by the player-triggered ``/compact`` slash command in the CLI to
    discover which per-agent buckets to roll forward into semantic memory
    without hard-coding the agent roster.
    """
    conn = _get_db()
    cursor = conn.execute(
        "SELECT DISTINCT agent_name FROM messages WHERE context_id = ? ORDER BY agent_name",
        (context_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def add_message(context_id: str, agent_name: str, role: str, content: Any) -> None:
    """Add a message to the episodic history."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT COALESCE(MAX(idx), -1) + 1 FROM messages WHERE context_id = ? AND agent_name = ?",
        (context_id, agent_name),
    )
    idx = cursor.fetchone()[0]

    content_str = json.dumps(content)

    conn.execute(
        "INSERT INTO messages (context_id, agent_name, idx, role, content, summarized) "
        "VALUES (?, ?, ?, ?, ?, 0)",
        (context_id, agent_name, idx, role, content_str),
    )
    conn.commit()
