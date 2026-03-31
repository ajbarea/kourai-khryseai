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
        )
        log.info("Stored fact for player %s: %s", player_id[:8], content[:80])


def get_relevant_facts_for_enrichment(
    player_id: str,
    context_keywords: list[str] | None = None,
    agent_name: str | None = None,
    limit: int = 10,
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

    Returns:
        List of fact dicts with body, category, confidence, source_agent.
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
        )

        # Filter by keywords if provided
        if context_keywords:
            keywords_lower = {kw.lower() for kw in context_keywords}
            memories = [
                m
                for m in memories
                if any(kw in m.get("content", "").lower() for kw in keywords_lower)
            ]

        return [
            {
                "body": m["content"].replace("[FACT:", "").split("]", 1)[-1].strip(),
                "category": "fact",
                "confidence": m.get("importance", 0.5),
                "source_agent": m.get("agent_name", "unknown"),
            }
            for m in memories
        ]
    except Exception as e:
        log.warning("Failed to retrieve enrichment facts: %s", e)
        return []


def build_fact_context(
    player_id: str,
    agent_name: str | None = None,
) -> str:
    """Build a prose block of player facts for prompt injection.

    Takes relevant facts from the knowledge graph and formats them
    as natural language context for the agent.

    Args:
        player_id: Player UUID.
        agent_name: Optional agent name for preference filtering.

    Returns:
        Human-readable fact block (empty string if no facts).
    """
    facts = get_relevant_facts_for_enrichment(player_id, agent_name=agent_name, limit=5)
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
