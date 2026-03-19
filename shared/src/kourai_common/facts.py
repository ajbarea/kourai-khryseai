"""Player fact discovery system for Kourai Khryseai.

Agents can embed structured facts about the player inside their LLM responses
using a lightweight XML-like tag format:

    <FACT category="preference" confidence="high">Player prefers dark mode interfaces</FACT>

These facts are extracted from agent output, scored, deduplicated, and stored
in the player profile for prompt injection in future sessions.

Spec: designs/PLAYER-PERSONALIZATION-PLAN.md — Phase 2C
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

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


def process_agent_output(
    text: str,
    player_id: str,
    source_agent: str = "unknown",
) -> str:
    """Extract + store facts from agent output, then return clean text.

    Call this on every artifact before forwarding to the VN bridge.
    Returns the text with <FACT> tags stripped so the player sees clean prose.
    """
    facts = extract_facts(text, source_agent=source_agent)
    if facts:
        store_facts(player_id, facts)
    return strip_facts(text)
