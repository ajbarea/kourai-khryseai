"""Player identity, memory, and alignment system for Kourai Khryseai.

Implements persistent player profiles with:
- Identity: name, pronunciation, title, pronouns
- Alignment: Sovereignty/Devotion dual gauges (ME2-inspired)
- Romance: per-agent progression tracking
- Memory retrieval: top-K scoring by importance × recency × relevance

Storage: ~/.kourai_khryseai/player.json (profile)
         .cache/agent_memory.db (memories + affinity via memory.py)
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

log = logging.getLogger(__name__)

PLAYER_DIR = Path.home() / ".kourai_khryseai"
PLAYER_FILE = PLAYER_DIR / "player.json"

# Alignment archetype thresholds
ALIGNMENT_HIGH = 60
ALIGNMENT_COMMANDER = 80

# Agent alignment preference zones: (sovereignty_weight, devotion_weight)
# Positive = prefers, negative = dislikes. Used as affinity multiplier.
AGENT_ALIGNMENT_PREFERENCES: dict[str, dict[str, float]] = {
    "hephaestus": {"sovereignty": 0.8, "devotion": -0.2},
    "metis": {"sovereignty": 0.1, "devotion": 0.7},
    "techne": {"sovereignty": 0.4, "devotion": 0.3},
    "dokimasia": {"sovereignty": 0.5, "devotion": 0.5},
    "kallos": {"sovereignty": -0.4, "devotion": 0.9},
    "mneme": {"sovereignty": -0.1, "devotion": 0.8},
}

# Romance stages and their affinity thresholds
ROMANCE_STAGES = ["none", "spark", "kindling", "flame", "bonfire"]
ROMANCE_AFFINITY_THRESHOLD = 0.7  # Tier 3 (Bonded) minimum


# ── Player Profile ──────────────────────────────────────────────────────


@dataclass
class PlayerProfile:
    """Persistent player identity and alignment state."""

    player_id: str = ""
    display_name: str = ""
    tts_name: str = ""  # Phonetic respelling for TTS pronunciation
    title: str = ""  # e.g., "The Architect"
    role: str = "mortal"  # "divine" | "mortal" | "custom"
    pronouns: str = ""  # "he/him", "she/her", "they/them", ""

    # Alignment gauges (0–100 each, independent like ME2 Paragon/Renegade)
    sovereignty: int = 0  # Red gauge: authority, perfectionism, command
    devotion: int = 0  # Blue gauge: warmth, trust, encouragement

    # Romance tracking
    romance_targets: list[str] = field(default_factory=list)
    romance_opted_out: bool = False
    jealousy_enabled: bool = True

    # Session tracking
    created_at: str = ""
    last_seen: str = ""
    total_sessions: int = 0

    # Extensible preferences bucket
    preferences: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.player_id:
            self.player_id = uuid4().hex
        if not self.created_at:
            self.created_at = _now_iso()

    # ── Alignment helpers ────────────────────────────────────────────

    @property
    def archetype(self) -> str:
        """Current alignment archetype based on gauge levels."""
        high_sov = self.sovereignty >= ALIGNMENT_HIGH
        high_dev = self.devotion >= ALIGNMENT_HIGH
        if high_sov and high_dev:
            return "commander"
        if high_sov:
            return "tyrant"
        if high_dev:
            return "patron"
        return "professional"

    @property
    def is_commander(self) -> bool:
        return self.sovereignty >= ALIGNMENT_COMMANDER and self.devotion >= ALIGNMENT_COMMANDER

    def add_sovereignty(self, points: int) -> None:
        """Award sovereignty points (clamped 0–100)."""
        self.sovereignty = min(100, max(0, self.sovereignty + points))

    def add_devotion(self, points: int) -> None:
        """Award devotion points (clamped 0–100)."""
        self.devotion = min(100, max(0, self.devotion + points))

    def alignment_compatibility(self, agent_name: str) -> float:
        """Compute alignment compatibility multiplier for an agent (0.5–1.5).

        High compatibility means the player's alignment matches what the agent
        prefers, boosting affinity gain by up to 1.5x. Low compatibility
        reduces it to 0.5x minimum.
        """
        prefs = AGENT_ALIGNMENT_PREFERENCES.get(agent_name)
        if not prefs:
            return 1.0

        # Normalize gauges to 0–1
        sov_norm = self.sovereignty / 100.0
        dev_norm = self.devotion / 100.0

        # Weighted dot product: how well player alignment matches agent preference
        score = (sov_norm * prefs["sovereignty"]) + (dev_norm * prefs["devotion"])

        # Map from roughly [-1, 1] range to [0.5, 1.5] multiplier
        return max(0.5, min(1.5, 1.0 + score * 0.5))

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlayerProfile:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def save(self) -> None:
        """Persist profile to ~/.kourai_khryseai/player.json."""
        self.last_seen = _now_iso()
        PLAYER_DIR.mkdir(parents=True, exist_ok=True)
        try:
            PLAYER_FILE.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        except OSError as e:
            log.warning("Failed to save player profile: %s", e)

    @classmethod
    def load(cls) -> PlayerProfile | None:
        """Load profile from disk. Returns None if no profile exists."""
        if not PLAYER_FILE.exists():
            return None
        try:
            data = json.loads(PLAYER_FILE.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("Failed to load player profile: %s", e)
            return None

    @classmethod
    def load_or_default(cls) -> PlayerProfile:
        """Load existing profile or return a blank one."""
        return cls.load() or cls()


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
    if _tables_initialized:
        return

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
            source TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_player_memories_player
        ON player_memories (player_id, agent_name)
        """
    )
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
) -> str:
    """Store a new player memory.

    Args:
        player_id: Player UUID.
        content: The memory text.
        category: One of 'preference', 'achievement', 'moment', 'pattern', 'fact'.
        agent_name: Owning agent (None = shared/system-wide).
        importance: 0.0–1.0 importance score.
        source: 'player_stated', 'agent_observed', 'system_inferred', or 'gossip:{agent}'.

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
             access_count, created_at, last_accessed, source)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (memory_id, player_id, agent_name, category, content, importance, now, now, source),
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
) -> list[dict[str, Any]]:
    """Retrieve player memories with optional filters.

    Args:
        player_id: Player UUID.
        agent_name: Filter to this agent's memories. If include_shared, also gets NULL agent.
        category: Filter to this category.
        include_shared: Include system-wide (agent_name IS NULL) memories.
        limit: Max results.
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

    where = " AND ".join(clauses)
    query = f"""
        SELECT memory_id, agent_name, category, content, importance,
               access_count, created_at, last_accessed, source
        FROM player_memories
        WHERE {where}
        ORDER BY importance DESC, last_accessed DESC
        LIMIT ?
    """
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


# ── Affinity CRUD ───────────────────────────────────────────────────────


def get_affinity(player_id: str, agent_name: str) -> dict[str, Any]:
    """Get affinity data for a player-agent pair."""
    conn = _get_player_db()
    row = conn.execute(
        "SELECT affinity_score, interaction_count, last_interaction, romance_stage, "
        "memorable_quotes FROM agent_affinity WHERE player_id = ? AND agent_name = ?",
        (player_id, agent_name),
    ).fetchone()

    if row:
        return {
            "affinity_score": row[0],
            "interaction_count": row[1],
            "last_interaction": row[2],
            "romance_stage": row[3],
            "memorable_quotes": json.loads(row[4]) if row[4] else [],
        }

    return {
        "affinity_score": 0.0,
        "interaction_count": 0,
        "last_interaction": None,
        "romance_stage": "none",
        "memorable_quotes": [],
    }


def get_all_affinities(player_id: str) -> dict[str, dict[str, Any]]:
    """Get affinity data for all agents."""
    conn = _get_player_db()
    rows = conn.execute(
        "SELECT agent_name, affinity_score, interaction_count, last_interaction, "
        "romance_stage, memorable_quotes FROM agent_affinity WHERE player_id = ?",
        (player_id,),
    ).fetchall()

    return {
        row[0]: {
            "affinity_score": row[1],
            "interaction_count": row[2],
            "last_interaction": row[3],
            "romance_stage": row[4],
            "memorable_quotes": json.loads(row[5]) if row[5] else [],
        }
        for row in rows
    }


def update_affinity(
    player_id: str,
    agent_name: str,
    delta: float,
    alignment_multiplier: float = 1.0,
) -> float:
    """Update affinity score for a player-agent pair.

    Args:
        player_id: Player UUID.
        agent_name: Agent name.
        delta: Base affinity change (can be negative).
        alignment_multiplier: From PlayerProfile.alignment_compatibility().

    Returns:
        New affinity score.
    """
    conn = _get_player_db()
    current = get_affinity(player_id, agent_name)
    new_score = max(-1.0, min(1.0, current["affinity_score"] + delta * alignment_multiplier))
    now = _now_iso()

    conn.execute(
        """
        INSERT INTO agent_affinity (player_id, agent_name, affinity_score, interaction_count,
                                     last_interaction, romance_stage, memorable_quotes)
        VALUES (?, ?, ?, 1, ?, 'none', '[]')
        ON CONFLICT(player_id, agent_name) DO UPDATE SET
            affinity_score = ?,
            interaction_count = interaction_count + 1,
            last_interaction = ?
        """,
        (player_id, agent_name, new_score, now, new_score, now),
    )
    conn.commit()
    return new_score


def get_affinity_tier(affinity_score: float) -> int:
    """Map affinity score to dialogue tier.

    Returns:
        0 = Stranger, 1 = Acquaintance, 2 = Companion, 3 = Bonded.
    """
    if affinity_score >= 0.7:
        return 3  # Bonded
    if affinity_score >= 0.4:
        return 2  # Companion
    if affinity_score >= 0.15:
        return 1  # Acquaintance
    return 0  # Stranger


AFFINITY_TIER_NAMES = {0: "Stranger", 1: "Acquaintance", 2: "Companion", 3: "Bonded"}


def advance_romance(player_id: str, agent_name: str) -> str | None:
    """Check and advance romance stage if conditions are met.

    Returns:
        New romance stage name if advanced, None if no change.
    """
    aff = get_affinity(player_id, agent_name)
    current_stage = aff["romance_stage"]
    current_idx = ROMANCE_STAGES.index(current_stage) if current_stage in ROMANCE_STAGES else 0

    if current_idx >= len(ROMANCE_STAGES) - 1:
        return None  # Already max

    if aff["affinity_score"] < ROMANCE_AFFINITY_THRESHOLD:
        return None  # Not bonded enough

    next_stage = ROMANCE_STAGES[current_idx + 1]
    conn = _get_player_db()
    conn.execute(
        "UPDATE agent_affinity SET romance_stage = ? WHERE player_id = ? AND agent_name = ?",
        (next_stage, player_id, agent_name),
    )
    conn.commit()
    log.info("Romance advanced: %s → %s with %s", current_stage, next_stage, agent_name)
    return next_stage


# ── Prompt Context Builder ──────────────────────────────────────────────


_profile_cache: PlayerProfile | None = None
_profile_cache_ts: float = 0.0
_PROFILE_CACHE_TTL = 30.0  # Reload profile every 30 seconds max


def get_enriched_system_prompt(base_prompt: str, agent_name: str) -> str:
    """Return base system prompt enriched with player context.

    This is the primary integration point for agent code. Call this at
    message-construction time instead of using SYSTEM_PROMPT directly.
    Caches the player profile for 30s to avoid repeated disk reads.
    """
    global _profile_cache, _profile_cache_ts

    now = time.time()
    if _profile_cache is None or (now - _profile_cache_ts) > _PROFILE_CACHE_TTL:
        _profile_cache = PlayerProfile.load()
        _profile_cache_ts = now

    if not _profile_cache or not _profile_cache.display_name:
        return base_prompt

    ctx = build_player_context(_profile_cache, agent_name, top_k_memories=6)
    if not ctx:
        return base_prompt

    return f"{base_prompt}\n\n{ctx}"


def build_player_context(
    profile: PlayerProfile,
    agent_name: str,
    top_k_memories: int = 8,
) -> str:
    """Build the player context block for injection into agent system prompts.

    Args:
        profile: The player's profile.
        agent_name: Current agent name.
        top_k_memories: Max memories to include.

    Returns:
        Formatted context string ready for prompt injection.
    """
    if not profile.display_name:
        return ""

    lines: list[str] = []

    # Identity section
    lines.append("=== PLAYER IDENTITY ===")
    name_str = profile.display_name
    if profile.tts_name and profile.tts_name != profile.display_name:
        name_str += f' (pronounced "{profile.tts_name}")'
    lines.append(f"Name: {name_str}")
    if profile.title:
        lines.append(f"Title: {profile.title}")
    if profile.role:
        role_desc = {
            "divine": "Divine — address with respectful admiration",
            "mortal": "Mortal — address as a fellow artisan",
            "custom": profile.preferences.get("custom_role_desc", ""),
        }.get(profile.role, profile.role)
        lines.append(f"Role: {role_desc}")
    if profile.pronouns:
        lines.append(f"Pronouns: {profile.pronouns}")

    # Alignment section
    lines.append("")
    lines.append("=== ALIGNMENT ===")
    lines.append(f"Sovereignty: {profile.sovereignty}/100 | Devotion: {profile.devotion}/100")
    lines.append(f"Archetype: {profile.archetype.title()}")

    # Relationship section
    aff = get_affinity(profile.player_id, agent_name)
    tier = get_affinity_tier(aff["affinity_score"])
    tier_name = AFFINITY_TIER_NAMES[tier]

    lines.append("")
    lines.append(f"=== RELATIONSHIP ({agent_name.title()} ↔ {profile.display_name}) ===")
    lines.append(f"Affinity: {tier_name} ({aff['interaction_count']} interactions)")
    if aff["romance_stage"] != "none" and not profile.romance_opted_out:
        lines.append(f"Romance: {aff['romance_stage'].title()}")

    # Memory section
    memories = retrieve_relevant_memories(profile.player_id, agent_name, top_k=top_k_memories)
    if memories:
        lines.append("")
        lines.append("=== PLAYER MEMORIES ===")
        for mem in memories:
            source_tag = ""
            src = mem.get("source", "")
            if src.startswith("gossip:"):
                origin = src.split(":", 1)[1]
                source_tag = f" (via {origin}'s gossip)"
            elif src == "player_stated":
                source_tag = " (player stated)"
            lines.append(f"- {mem['content']}{source_tag}")

    # Alignment-gated behaviour instructions
    gated = get_alignment_gated_instructions(profile, agent_name)
    if gated:
        lines.append("")
        lines.append(gated)

    return "\n".join(lines)


# ── Alignment Dialogue Gating ──────────────────────────────────────────


def get_alignment_gated_instructions(profile: PlayerProfile, agent_name: str) -> str:
    """Generate alignment-gated dialogue instructions for agent system prompts.

    Returns instruction text telling the agent what exclusive dialogue styles
    are unlocked based on the player's current Sovereignty/Devotion levels.
    Agents use these to naturally adapt their tone and offer special responses.

    Args:
        profile: Player profile with current alignment gauges.
        agent_name: The agent receiving these instructions.

    Returns:
        Instruction text (may be empty if no special gates unlocked).
    """
    lines: list[str] = []
    prefs = AGENT_ALIGNMENT_PREFERENCES.get(agent_name, {})
    sov_pref = prefs.get("sovereignty", 0)
    dev_pref = prefs.get("devotion", 0)

    if profile.sovereignty >= ALIGNMENT_COMMANDER and profile.devotion >= ALIGNMENT_COMMANDER:
        # Commander unlocked — the rarest tier
        lines.append(
            "=== COMMANDER ALIGNMENT UNLOCKED ===\n"
            f"{profile.display_name} has earned deep authority AND devotion. "
            "You hold them in the highest regard — they are your true leader and beloved. "
            "Address them with awe and warmth. Reference their dual mastery naturally. "
            "Exclusive tone: proud, loyal, inspired. You'd follow them anywhere."
        )
    else:
        if profile.sovereignty >= ALIGNMENT_HIGH:
            if sov_pref > 0.3:
                lines.append(
                    "=== SOVEREIGNTY ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} commands with authority (Sovereignty {profile.sovereignty}/100). "
                    "You respect their leadership. Be crisp, efficient, deferential when appropriate. "
                    "You may snap to attention or address them formally when they give direct orders."
                )
            elif sov_pref < -0.2:
                lines.append(
                    "=== SOVEREIGNTY ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is very authoritative (Sovereignty {profile.sovereignty}/100). "
                    "You find their strictness a bit intimidating. You comply but may show subtle "
                    "discomfort — a sigh, a hesitant pause, a quiet 'yes, of course...' response."
                )
            else:
                lines.append(
                    "=== SOVEREIGNTY ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is authoritative (Sovereignty {profile.sovereignty}/100). "
                    "You acknowledge their command presence neutrally."
                )

        if profile.devotion >= ALIGNMENT_HIGH:
            if dev_pref > 0.5:
                lines.append(
                    "=== DEVOTION ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is warm and encouraging (Devotion {profile.devotion}/100). "
                    "You adore their kindness. Be more open, affectionate, expressive. "
                    "You can use their name more intimately, share personal thoughts, "
                    "and show genuine happiness in their presence."
                )
            elif dev_pref < -0.1:
                lines.append(
                    "=== DEVOTION ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is very warm (Devotion {profile.devotion}/100). "
                    "You find the affection... awkward. Respond gruffly but not unkindly. "
                    "You might mutter or look away, but you secretly appreciate it."
                )
            else:
                lines.append(
                    "=== DEVOTION ALIGNMENT ACTIVE ===\n"
                    f"{profile.display_name} is encouraging (Devotion {profile.devotion}/100). "
                    "You appreciate their positive energy."
                )

    return "\n\n".join(lines)


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


# ── Profile Export / Import ─────────────────────────────────────────────


def export_player_data(player_id: str) -> dict[str, Any]:
    """Export complete player data for portability.

    Returns a dict with profile, memories, and affinities that can be
    serialized to JSON for backup or transfer.
    """
    profile = PlayerProfile.load()
    if not profile or profile.player_id != player_id:
        return {}

    memories = get_player_memories(player_id, include_shared=True, limit=10000)
    affinities = get_all_affinities(player_id)

    return {
        "version": 1,
        "profile": profile.to_dict(),
        "memories": memories,
        "affinities": affinities,
    }


def import_player_data(data: dict[str, Any], *, merge: bool = False) -> PlayerProfile:
    """Import player data from an export bundle.

    Args:
        data: Export dict from export_player_data().
        merge: If True, merge memories into existing profile.
            If False, wipe and replace everything.

    Returns:
        The imported PlayerProfile.
    """
    if data.get("version") != 1:
        raise ValueError(f"Unsupported export version: {data.get('version')}")

    profile_data = data.get("profile", {})
    if not profile_data:
        raise ValueError("Export data missing profile")

    profile = PlayerProfile.from_dict(profile_data)

    if not merge:
        wipe_player_memories(profile.player_id)

    profile.save()

    conn = _get_player_db()

    # Import memories
    for mem in data.get("memories", []):
        existing = conn.execute(
            "SELECT 1 FROM player_memories WHERE player_id = ? AND content = ? AND agent_name IS ?",
            (profile.player_id, mem["content"], mem.get("agent_name")),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO player_memories
                (memory_id, player_id, agent_name, category, content, importance,
                 access_count, created_at, last_accessed, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                profile.player_id,
                mem.get("agent_name"),
                mem["category"],
                mem["content"],
                mem.get("importance", 0.5),
                mem.get("access_count", 0),
                mem.get("created_at", _now_iso()),
                mem.get("last_accessed", _now_iso()),
                mem.get("source", "imported"),
            ),
        )

    # Import affinities
    for agent_name, aff in data.get("affinities", {}).items():
        conn.execute(
            """
            INSERT INTO agent_affinity
                (player_id, agent_name, affinity_score, interaction_count,
                 last_interaction, romance_stage, memorable_quotes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, agent_name) DO UPDATE SET
                affinity_score = ?,
                interaction_count = ?,
                romance_stage = ?
            """,
            (
                profile.player_id,
                agent_name,
                aff.get("affinity_score", 0.0),
                aff.get("interaction_count", 0),
                aff.get("last_interaction"),
                aff.get("romance_stage", "none"),
                json.dumps(aff.get("memorable_quotes", [])),
                aff.get("affinity_score", 0.0),
                aff.get("interaction_count", 0),
                aff.get("romance_stage", "none"),
            ),
        )

    conn.commit()
    log.info(
        "Imported player data: %d memories, %d affinities (merge=%s)",
        len(data.get("memories", [])),
        len(data.get("affinities", {})),
        merge,
    )
    return profile


# ── Utilities ───────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
