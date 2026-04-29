"""Player memory system — CRUD, retrieval scoring, gossip transfer, and decay.

Split from player.py for focused responsibility. Manages the player_memories
table in agent_memory.db with importance-weighted heuristic retrieval.
"""

from __future__ import annotations

import contextlib
import logging
import math
import sqlite3
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from kourai_common.player_constants import _now_iso

log = logging.getLogger(__name__)


# ── Player Memory DB ────────────────────────────────────────────────────


def _get_player_db() -> sqlite3.Connection:
    """Get a connection to the player memory database (shared with agent_memory.db)."""
    from kourai_common.memory import _get_db

    conn = _get_db()
    _ensure_player_tables(conn)
    return conn


_tables_initialized = False


def _ensure_player_tables(conn: sqlite3.Connection) -> None:
    """Create player memory and affinity tables if they don't exist."""
    global _tables_initialized

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS player_memories (
            memory_id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            agent_name TEXT,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            created_at TEXT,
            last_accessed TEXT,
            expires_at TEXT,
            source TEXT,
            project_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_player_memories_player
        ON player_memories (player_id, agent_name)
        """
    )
    # Backwards compat: pre-M17 databases lack the project_id column.
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE player_memories ADD COLUMN project_id TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_affinity (
            player_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            affinity_score REAL DEFAULT 0.0,
            interaction_count INTEGER DEFAULT 0,
            last_interaction TEXT,
            romance_stage TEXT DEFAULT 'none',
            memorable_quotes TEXT DEFAULT '[]',
            PRIMARY KEY (player_id, agent_name)
        )
        """
    )
    conn.commit()
    _tables_initialized = True


# ── Memory CRUD ─────────────────────────────────────────────────────────


def add_player_memory(
    player_id: str,
    content: str,
    category: str,
    agent_name: str | None = None,
    importance: float = 0.5,
    source: str = "agent_observed",
    project_id: str | None = None,
) -> str:
    """Store a new player memory.

    Args:
        player_id: Player UUID.
        content: The memory text.
        category: One of 'preference', 'achievement', 'moment', 'pattern', 'fact'.
        agent_name: Owning agent (None = shared/system-wide).
        importance: 0.0–1.0 importance score.
        source: 'player_stated', 'agent_observed', 'system_inferred', or 'gossip:{agent}'.
        project_id: Optional project scope (M17). None = global / cross-project.

    Returns:
        The generated memory_id.
    """
    conn = _get_player_db()
    memory_id = uuid4().hex
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO player_memories
            (memory_id, player_id, agent_name, category, content, importance,
             access_count, created_at, last_accessed, source, project_id)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            memory_id,
            player_id,
            agent_name,
            category,
            content,
            importance,
            now,
            now,
            source,
            project_id,
        ),
    )
    conn.commit()
    log.debug("Stored player memory [%s] cat=%s agent=%s", memory_id[:8], category, agent_name)
    return memory_id


def get_player_memories(
    player_id: str,
    agent_name: str | None = None,
    category: str | None = None,
    include_shared: bool = True,
    limit: int = 50,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve player memories with optional filters.

    Args:
        player_id: Player UUID.
        agent_name: Filter to this agent's memories. If include_shared, also gets NULL agent.
        category: Filter to this category.
        include_shared: Include system-wide (agent_name IS NULL) memories.
        limit: Max results.
        project_id: Optional M17 project scope. When provided, results include matching-
            project memories AND global (project_id IS NULL) memories, with matching-
            project rows preferred at equal score. When None, no project filter is
            applied (backwards compatible — returns all scopes for the player).
    """
    conn = _get_player_db()
    clauses = ["player_id = ?"]
    params: list[Any] = [player_id]

    if agent_name is not None:
        if include_shared:
            clauses.append("(agent_name = ? OR agent_name IS NULL)")
            params.append(agent_name)
        else:
            clauses.append("agent_name = ?")
            params.append(agent_name)

    if category is not None:
        clauses.append("category = ?")
        params.append(category)

    if project_id is not None:
        clauses.append("(project_id = ? OR project_id IS NULL)")
        params.append(project_id)

    # ORDER BY: when scoped, project-matching rows beat global rows at equal score.
    if project_id is not None:
        order_clause = (
            "CASE WHEN project_id = ? THEN 1 ELSE 0 END DESC, importance DESC, last_accessed DESC"
        )
        order_params: list[Any] = [project_id]
    else:
        order_clause = "importance DESC, last_accessed DESC"
        order_params = []

    where = " AND ".join(clauses)
    query = f"""
        SELECT memory_id, agent_name, category, content, importance,
               access_count, created_at, last_accessed, source, project_id
        FROM player_memories
        WHERE {where}
        ORDER BY {order_clause}
        LIMIT ?
    """  # noqa: S608
    params.extend(order_params)
    params.append(limit)

    rows = conn.execute(query, tuple(params)).fetchall()
    return [
        {
            "memory_id": r[0],
            "agent_name": r[1],
            "category": r[2],
            "content": r[3],
            "importance": r[4],
            "access_count": r[5],
            "created_at": r[6],
            "last_accessed": r[7],
            "source": r[8],
            "project_id": r[9],
        }
        for r in rows
    ]


def retrieve_relevant_memories(
    player_id: str,
    agent_name: str,
    query_hint: str = "",
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve the most relevant memories for prompt injection.

    Scores each memory by: importance × recency × access_frequency.
    This is a heuristic scorer — no embeddings needed.

    Args:
        player_id: Player UUID.
        agent_name: Current agent (gets private + shared + gossip-received memories).
        query_hint: Optional current task context for future semantic matching.
        top_k: Number of memories to return.
    """
    memories = get_player_memories(player_id, agent_name=agent_name, include_shared=True, limit=200)

    now_ts = time.time()
    scored: list[tuple[float, dict[str, Any]]] = []

    for mem in memories:
        importance = mem["importance"]

        # Recency decay: half-life of 7 days
        try:
            last = datetime.fromisoformat(mem["last_accessed"]).timestamp()
        except (ValueError, TypeError):
            last = now_ts
        age_days = (now_ts - last) / 86400.0
        recency = math.exp(-0.1 * age_days)  # ~0.5 at 7 days

        # Access boost: frequently accessed memories are more important
        access_boost = min(1.0, 0.5 + 0.05 * mem["access_count"])

        score = importance * recency * access_boost
        scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [mem for _, mem in scored[:top_k]]

    # Update access counts for retrieved memories
    if top:
        conn = _get_player_db()
        now = _now_iso()
        for mem in top:
            conn.execute(
                "UPDATE player_memories SET access_count = access_count + 1, last_accessed = ? "
                "WHERE memory_id = ?",
                (now, mem["memory_id"]),
            )
        conn.commit()

    return top


def delete_player_memory(memory_id: str) -> None:
    """Delete a specific memory."""
    conn = _get_player_db()
    conn.execute("DELETE FROM player_memories WHERE memory_id = ?", (memory_id,))
    conn.commit()


def wipe_player_memories(player_id: str) -> None:
    """Delete ALL memories for a player."""
    conn = _get_player_db()
    conn.execute("DELETE FROM player_memories WHERE player_id = ?", (player_id,))
    conn.execute("DELETE FROM agent_affinity WHERE player_id = ?", (player_id,))
    conn.commit()
    log.info("Wiped all memories for player %s", player_id[:8])


def transfer_gossip_memories(
    from_agent: str,
    to_agents: list[str],
    memory_ids: list[str],
) -> int:
    """Copy private memories to other agents via gossip.

    This is the ONLY mechanism for private memory transfer between agents.
    Copies are tagged with source='gossip:{from_agent}' so agents can
    reference the gossip origin naturally in dialogue.

    Returns:
        Number of memories transferred.
    """
    conn = _get_player_db()
    transferred = 0

    for mid in memory_ids:
        row = conn.execute(
            "SELECT player_id, category, content, importance FROM player_memories WHERE memory_id = ?",
            (mid,),
        ).fetchone()
        if not row:
            continue

        player_id, category, content, importance = row
        gossip_source = f"gossip:{from_agent}"
        now = _now_iso()

        for to_agent in to_agents:
            # Don't duplicate if agent already has this memory content
            existing = conn.execute(
                "SELECT 1 FROM player_memories WHERE player_id = ? AND agent_name = ? "
                "AND content = ?",
                (player_id, to_agent, content),
            ).fetchone()
            if existing:
                continue

            conn.execute(
                """
                INSERT INTO player_memories
                    (memory_id, player_id, agent_name, category, content, importance,
                     access_count, created_at, last_accessed, source)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    player_id,
                    to_agent,
                    category,
                    content,
                    importance,
                    now,
                    now,
                    gossip_source,
                ),
            )
            transferred += 1

    conn.commit()
    log.debug("Gossip transfer: %d memories from %s to %s", transferred, from_agent, to_agents)
    return transferred


def decay_memories(
    player_id: str,
    half_life_days: float = 30.0,
    min_importance: float = 0.05,
    protect_categories: tuple[str, ...] = ("achievement", "preference"),
) -> int:
    """Apply time-based importance decay to player memories.

    Memories that fall below min_importance are deleted.
    Achievements and stated preferences are protected from decay.

    Args:
        player_id: Player UUID.
        half_life_days: Number of days for importance to halve.
        min_importance: Memories below this threshold are pruned.
        protect_categories: Categories exempt from decay.

    Returns:
        Number of memories pruned.
    """
    conn = _get_player_db()
    now_ts = time.time()
    decay_rate = 0.693 / half_life_days  # ln(2) / half_life

    rows = conn.execute(
        """
        SELECT memory_id, category, importance, last_accessed, access_count
        FROM player_memories
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchall()

    pruned = 0
    for memory_id, category, importance, last_accessed, access_count in rows:
        if category in protect_categories:
            continue

        try:
            last_ts = datetime.fromisoformat(last_accessed).timestamp()
        except (ValueError, TypeError):
            last_ts = now_ts
        age_days = (now_ts - last_ts) / 86400.0

        # Frequently accessed memories decay slower
        access_shield = min(1.0, 0.3 + 0.07 * access_count)
        decayed_importance = importance * math.exp(-decay_rate * age_days) * access_shield

        if decayed_importance < min_importance:
            conn.execute("DELETE FROM player_memories WHERE memory_id = ?", (memory_id,))
            pruned += 1
        elif decayed_importance < importance * 0.95:
            conn.execute(
                "UPDATE player_memories SET importance = ? WHERE memory_id = ?",
                (round(decayed_importance, 4), memory_id),
            )

    conn.commit()
    if pruned:
        log.info("Memory decay: pruned %d memories for player %s", pruned, player_id[:8])
    return pruned
