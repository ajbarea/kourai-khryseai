"""Player fact discovery system for Kourai Khryseai.

Agents can embed structured facts about the player inside their LLM responses
using a lightweight XML-like tag format:

    <FACT category="preference" confidence="high">Player prefers dark mode interfaces</FACT>

These facts are extracted from agent output, scored, deduplicated, and stored
in the player profile for prompt injection in future sessions via a knowledge graph.

Knowledge Graph Schema:
- Node: A fact (topic, claim, preference)
- Edges: Relationships between facts (refines, contradicts, supports)
- Attributes: confidence, source_agent, reinforcement_count, validity
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

log = logging.getLogger(__name__)

# Regex to extract <FACT ...>...</FACT> tags from agent output.
# Handles optional attributes: category, confidence.
_FACT_RE = re.compile(
    r"<FACT(?P<attrs>[^>]*)>(?P<body>[^<]+)</FACT>",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(r'(\w+)=["\']([^"\']+)["\']')

VALID_CATEGORIES = frozenset(
    {
        "preference",  # "prefers dark mode", "likes Python over JS"
        "identity",  # name spelling, pronouns, title
        "skill",  # "knows Rust", "has 5 years Django experience"
        "context",  # "works at a startup", "building a SaaS product"
        "goal",  # "wants to ship by March"
        "personality",  # "gets frustrated with verbose explanations"
    }
)

VALID_CONFIDENCE = frozenset({"high", "medium", "low"})

CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}


@dataclass
class PlayerFact:
    """A single discovered fact about the player."""

    body: str
    category: str = "preference"
    confidence: str = "medium"
    source_agent: str = "unknown"
    project_id: str | None = None
    """Optional M17 project scope. None = global / cross-project."""
    # Numeric weight for retrieval ranking
    weight: float = field(init=False)

    def __post_init__(self) -> None:
        self.category = self.category if self.category in VALID_CATEGORIES else "preference"
        self.confidence = self.confidence if self.confidence in VALID_CONFIDENCE else "medium"
        self.weight = CONFIDENCE_WEIGHT[self.confidence]

    def to_dict(self) -> dict:
        return {
            "body": self.body,
            "category": self.category,
            "confidence": self.confidence,
            "source_agent": self.source_agent,
            "project_id": self.project_id,
            "weight": self.weight,
        }


@dataclass
class KnowledgeGraphFact:
    """Extended fact with knowledge graph metadata for cross-session learning.

    A node in the player's fact graph. Supports deduplication via
    reinforcement_count and tracks validity across sessions.
    """

    fact_id: str
    """Unique identifier for this fact node (UUID)."""

    player_id: str
    """Player who owns this fact."""

    body: str
    """The fact text."""

    category: str = "preference"
    """Fact category (preference, identity, skill, context, goal, personality)."""

    confidence: float = 0.5
    """Confidence 0.0–1.0 (converted from 'high'→0.9, 'medium'→0.6, 'low'→0.3)."""

    source_agent: str = "unknown"
    """Agent that discovered this fact."""

    reinforcement_count: int = 1
    """How many times has this fact been confirmed."""

    last_reinforced: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    """ISO timestamp of last confirmation."""

    discovered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    """ISO timestamp of initial discovery."""

    validity: str = "active"
    """'active', 'contradicted', or 'archived'. Tracks belief updates."""

    tags: list[str] = field(default_factory=list)
    """Optional tags for clustering (e.g., ['coding_style', 'python'])."""

    related_facts: list[str] = field(default_factory=list)
    """Fact IDs of related nodes (used for graph traversal)."""

    project_id: str | None = None
    """Optional M17 project scope. None = global / cross-project."""

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict for Knowledge Graph storage."""
        return {
            "fact_id": self.fact_id,
            "player_id": self.player_id,
            "body": self.body,
            "category": self.category,
            "confidence": self.confidence,
            "source_agent": self.source_agent,
            "reinforcement_count": self.reinforcement_count,
            "last_reinforced": self.last_reinforced,
            "discovered_at": self.discovered_at,
            "validity": self.validity,
            "tags": self.tags,
            "related_facts": self.related_facts,
            "project_id": self.project_id,
        }

    @classmethod
    def from_player_fact(
        cls,
        player_id: str,
        fact: PlayerFact,
        fact_id: str | None = None,
    ) -> KnowledgeGraphFact:
        """Convert a PlayerFact to a KnowledgeGraphFact."""
        from uuid import uuid4

        return cls(
            fact_id=fact_id or uuid4().hex,
            player_id=player_id,
            body=fact.body,
            category=fact.category,
            confidence=fact.weight,  # weight is 0.0–1.0 already
            source_agent=fact.source_agent,
            project_id=fact.project_id,
        )


def extract_facts(text: str, source_agent: str = "unknown") -> list[PlayerFact]:
    """Extract all <FACT> tags from agent-generated text.

    Args:
        text: Raw LLM output that may contain <FACT> tags.
        source_agent: Name of the agent that produced this text.

    Returns:
        List of extracted PlayerFact objects (may be empty).
    """
    facts: list[PlayerFact] = []
    for match in _FACT_RE.finditer(text):
        attrs_raw = match.group("attrs")
        body = match.group("body").strip()
        if not body:
            continue

        attrs: dict[str, str] = dict(_ATTR_RE.findall(attrs_raw))
        fact = PlayerFact(
            body=body,
            category=attrs.get("category", "preference").lower(),
            confidence=attrs.get("confidence", "medium").lower(),
            source_agent=source_agent,
            project_id=attrs.get("project_id"),
        )
        facts.append(fact)
        log.debug("Extracted fact [%s/%s]: %s", fact.category, fact.confidence, body[:80])

    return facts


def strip_facts(text: str) -> str:
    """Remove <FACT> tags from text before displaying to the player.

    The player should see clean natural-language output, not the markup.
    """
    return _FACT_RE.sub("", text).strip()


def store_facts(player_id: str, facts: list[PlayerFact]) -> None:
    """Persist extracted facts to the player's memory store.

    Uses ``add_player_memory`` from kourai_common.player so facts live
    alongside episodic memories and surface via the same retrieval path.
    """
    if not facts or not player_id:
        return

    # Import here to avoid circular imports at module level
    from kourai_common.player import add_player_memory

    for fact in facts:
        content = f"[FACT:{fact.category}/{fact.confidence}] {fact.body}"
        add_player_memory(
            player_id=player_id,
            agent_name=fact.source_agent,
            category="fact",
            content=content,
            importance=fact.weight,
            project_id=fact.project_id,
        )
        log.info("Stored fact for player %s: %s", player_id[:8], content[:80])


def get_relevant_facts_for_enrichment(
    player_id: str,
    context_keywords: list[str] | None = None,
    agent_name: str | None = None,
    limit: int = 10,
    project_id: str | None = None,
) -> list[dict]:
    """Retrieve relevant player facts for prompt enrichment.

    Uses the player memory system to fetch facts that should be injected
    into an agent's system prompt for context (e.g., player preferences,
    identity, past solutions).

    Args:
        player_id: Player UUID.
        context_keywords: Optional keywords to filter facts (e.g., ['async', 'Python']).
        agent_name: Optional agent name to prioritize agent-specific facts.
        limit: Max facts to return.
        project_id: Optional M17 project scope. When set, results include facts tagged
            with this project AND global facts, with project-tagged preferred at equal
            retrieval score. When None, no project axis is applied.

    Returns:
        List of fact dicts with body, category, confidence, source_agent, project_id.
    """
    from kourai_common.player import get_player_memories

    try:
        # Retrieve facts from player memory with category filter
        memories = get_player_memories(
            player_id=player_id,
            agent_name=agent_name,
            category="fact",
            include_shared=True,
            limit=limit,
            project_id=project_id,
        )

        # Filter by keywords if provided
        if context_keywords:
            keywords_lower = {kw.lower() for kw in context_keywords}
            memories = [
                m
                for m in memories
                if any(kw in m.get("content", "").lower() for kw in keywords_lower)
            ]

        # M17 Phase 2 item 9: drop preference facts that have decayed past
        # the floor. Non-preference facts (skill / identity / free-form)
        # pass through unchanged — the decay window only applies to the
        # closed-vocab preference axis where ``set`` / PAUSE re-confirmation
        # is the natural reset signal.
        memories = [
            m
            for m in memories
            if not _is_preference_decayed_to_skip(m.get("content", ""), m.get("created_at"))
        ]

        return [
            {
                "body": m["content"].replace("[FACT:", "").split("]", 1)[-1].strip(),
                "category": "fact",
                "confidence": m.get("importance", 0.5),
                "source_agent": m.get("agent_name", "unknown"),
                "project_id": m.get("project_id"),
            }
            for m in memories
        ]
    except Exception as e:
        log.warning("Failed to retrieve enrichment facts: %s", e)
        return []


def build_fact_context(
    player_id: str,
    agent_name: str | None = None,
    project_id: str | None = None,
) -> str:
    """Build a prose block of player facts for prompt injection.

    Takes relevant facts from the knowledge graph and formats them
    as natural language context for the agent.

    Args:
        player_id: Player UUID.
        agent_name: Optional agent name for preference filtering.
        project_id: Optional M17 project scope. When set, project-scoped facts
            are preferred over global ones at equal retrieval score.

    Returns:
        Human-readable fact block (empty string if no facts).
    """
    facts = get_relevant_facts_for_enrichment(
        player_id, agent_name=agent_name, limit=5, project_id=project_id
    )
    if not facts:
        return ""

    lines = ["=== PLAYER CONTEXT ==="]
    for fact in facts:
        confidence_label = (
            "confident"
            if fact["confidence"] > 0.7
            else "fairly sure"
            if fact["confidence"] > 0.4
            else "uncertain"
        )
        lines.append(
            f"- {fact['body']} (you're {confidence_label} about this, "
            f"learned from {fact['source_agent']})"
        )

    return "\n".join(lines)


def process_agent_output(
    text: str,
    player_id: str,
    source_agent: str = "unknown",
) -> str:
    """Extract + store facts from agent output, then return clean text.

    Call this on every artifact before forwarding to the VN bridge.
    Returns the text with <FACT> tags stripped so the player sees clean prose.

    Facts are stored in the player's knowledge graph via the memory system,
    enabling cross-session learning and enrichment.
    """
    facts = extract_facts(text, source_agent=source_agent)
    if facts:
        store_facts(player_id, facts)
    return strip_facts(text)


# ── M17 Phase 2 item 9: confidence decay ────────────────────────────────
#
# Lazy compute on top of ``created_at``. No scheduled sweep, no schema
# change — read-time tier-step. ``last_accessed`` deliberately does NOT
# reset the timer (passive recall would otherwise hold preferences alive
# forever); only player-driven re-confirmation (``set`` or PAUSE answer)
# writes a fresh row with a new ``created_at``.

PROJECT_FACT_DECAY_DAYS = 90
"""Days between confidence-tier drops on stored project preferences.

A fact at ``high`` becomes ``medium`` after this many days, ``low`` after
2× this, and ``skip`` after 3×. Floor at ``skip`` — the recall path
filters those out, the listing surfaces the decayed tier so the player
can see it. Mirrors mem0's "memory depth" concept without taking on the
embedding-vector dependency.
"""

# Order matters: index 0 is the floor, index 3 is the ceiling.
_TIER_LADDER: tuple[str, ...] = ("skip", "low", "medium", "high")

# ``[FACT:preference/<confidence>] <kind>: <value>`` — write shape produced
# by ``store_facts`` for closed-vocab preferences. Re-used by both the
# CRUD listing and the decay-aware recall filter; defined here so the
# decay helpers can stay co-located with their dependencies.
_PREF_BODY_RE = re.compile(
    r"^\[FACT:preference/(?P<confidence>\w+)\]\s+(?P<kind>[A-Za-z_]+):\s*(?P<value>.+)$"
)


def _decayed_confidence(original: str, age_days: float) -> str:
    """Drop one ladder rung per ``PROJECT_FACT_DECAY_DAYS`` of age.

    ``original`` outside the ladder (legacy data, manual edit) returns
    unchanged so decay is purely additive — never silently rewriting a
    confidence string the caller set on purpose.
    """
    if original not in _TIER_LADDER:
        return original
    drops = max(0, int(age_days // PROJECT_FACT_DECAY_DAYS))
    idx = max(0, _TIER_LADDER.index(original) - drops)
    return _TIER_LADDER[idx]


def _age_days(iso_timestamp: str | None) -> float:
    """Days since ``iso_timestamp`` (UTC). Missing / malformed → 0.0."""
    if not iso_timestamp:
        return 0.0
    try:
        ts = datetime.fromisoformat(iso_timestamp).timestamp()
    except (ValueError, TypeError):
        return 0.0
    return max(0.0, (datetime.now(UTC).timestamp() - ts) / 86400.0)


def _is_preference_decayed_to_skip(content: str, created_at: str | None) -> bool:
    """True iff ``content`` is a preference fact that decayed past the floor.

    Non-preference fact rows (skill, identity, free-form observations)
    pass through unchanged — only the closed-vocab preference axis is
    subject to the M17 decay window. Recall callers wrap their listings
    in this check so a stale preference doesn't keep landing in
    Metis's planning prompt months after it was last reinforced.
    """
    match = _PREF_BODY_RE.match(content.strip())
    if match is None:
        return False
    return _decayed_confidence(match.group("confidence"), _age_days(created_at)) == "skip"


# ── M17 Phase 2 item 7: /preferences CRUD primitives ────────────────────
#
# The CLI surface for browsing, deleting, and overriding the closed-vocab
# preference facts that PAUSE-resolution writes through
# ``synthesise_fact_from_pause``. Right-to-forget is non-negotiable for
# player trust and for GDPR/CCPA-aligned defaults — every fact has to be
# removable by the player without an operator step.


def list_preference_facts(player_id: str, project_id: str | None) -> list[dict]:
    """Return closed-vocab preference facts for the active scope.

    A row is included when it parses as ``<kind>: <value>`` with ``<kind>``
    in ``VALID_PREFERENCE_KINDS``. Free-form preference observations
    extracted by ``process_agent_output`` (skill claims, identity hints,
    pattern guesses) deliberately fall outside that gate so the
    ``/preferences`` UI stays a player-facing surface for things the
    player explicitly answered or set.

    The returned dicts carry ``memory_id`` so the caller can hand it to
    ``delete_player_memory`` for targeted forgets, and ``scope`` so the
    CLI can render project-vs-global rows with distinct visual weight.

    Args:
        player_id: Player UUID.
        project_id: Active project scope, or ``None`` for global view.
            When set, the listing includes both project-scoped rows and
            global rows; when ``None``, only global rows surface.

    Returns:
        List of dicts: ``{memory_id, kind, value, confidence, source_agent,
        project_id, scope, last_accessed}``.
    """
    from kourai_common.hooks_interaction import VALID_PREFERENCE_KINDS
    from kourai_common.player import get_player_memories

    rows = get_player_memories(
        player_id=player_id,
        category="fact",
        include_shared=True,
        limit=200,
        project_id=project_id,
    )

    out: list[dict] = []
    for row in rows:
        match = _PREF_BODY_RE.match(row.get("content", "").strip())
        if match is None:
            continue
        kind = match.group("kind")
        if kind not in VALID_PREFERENCE_KINDS:
            continue
        row_project = row.get("project_id")
        # When the caller passed ``project_id=None`` the SQL layer returns
        # all scopes for the player; here we narrow to global-only so the
        # bare-list UI doesn't surface project rows under "global".
        if project_id is None and row_project is not None:
            continue
        confidence = match.group("confidence")
        created_at = row.get("created_at")
        out.append(
            {
                "memory_id": row["memory_id"],
                "kind": kind,
                "value": match.group("value").strip(),
                "confidence": confidence,
                "decayed_confidence": _decayed_confidence(confidence, _age_days(created_at)),
                "source_agent": row.get("agent_name") or "unknown",
                "project_id": row_project,
                "scope": "project" if row_project is not None else "global",
                "created_at": created_at,
                "last_accessed": row.get("last_accessed"),
            }
        )
    return out


def forget_preference_fact(player_id: str, project_id: str | None, kind: str) -> int:
    """Delete every preference fact in ``(scope, kind)``.

    Right-to-forget primitive: the player has unconditional authority to
    remove anything stored under their id. Returns the number of rows
    removed so the caller can render an honest "removed N rows" message
    rather than always claiming success.

    Args:
        player_id: Player UUID.
        project_id: Project scope to clear, or ``None`` for global.
            Project and global rows are never co-deleted; the caller
            issues two calls if they want both gone.
        kind: Preference kind (closed vocab). Unknown kinds are tolerated
            here — an old kind that's been retired from
            ``VALID_PREFERENCE_KINDS`` still needs to be deletable.

    Returns:
        Number of rows deleted.
    """
    from kourai_common.player import delete_player_memory

    count = 0
    for row in list_preference_facts(player_id, project_id=project_id):
        if row["kind"] != kind:
            continue
        if row["project_id"] != project_id:
            continue
        delete_player_memory(row["memory_id"])
        count += 1
    return count


def set_preference_fact(
    player_id: str,
    project_id: str | None,
    kind: str,
    value: str,
    source_agent: str = "player",
) -> bool:
    """Override a preference fact for ``(scope, kind)``.

    Forgets any existing same-scope same-kind row first so the listing
    stays single-row-per-kind. Without that, repeated ``set`` calls would
    accumulate rows and ``list_preference_facts`` would surface every
    historical override.

    Args:
        player_id: Player UUID.
        project_id: Active scope, or ``None`` for global.
        kind: One of ``VALID_PREFERENCE_KINDS``. Unknown kinds are
            rejected — preventing arbitrary writes is the same gate that
            ``synthesise_fact_from_pause`` enforces on the PAUSE path.
        value: The override value. Whitespace-only values are rejected.
        source_agent: Stamped on the row so the recall narrator can
            distinguish "Metis asked, you answered" (``metis``) from
            "you set this directly" (default ``player``).

    Returns:
        ``True`` on write, ``False`` on validation rejection.
    """
    from kourai_common.hooks_interaction import VALID_PREFERENCE_KINDS

    if not player_id or not value or not value.strip():
        return False
    if kind not in VALID_PREFERENCE_KINDS:
        return False

    forget_preference_fact(player_id, project_id=project_id, kind=kind)
    fact = PlayerFact(
        body=f"{kind}: {value.strip()}",
        category="preference",
        confidence="high",
        source_agent=source_agent,
        project_id=project_id,
    )
    store_facts(player_id, [fact])
    return True
