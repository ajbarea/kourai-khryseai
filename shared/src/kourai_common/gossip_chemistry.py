"""Gossip pair chemistry metadata.

Pre-defined dynamics between agent pairs, used to flavor gossip system prompts.
"""

from __future__ import annotations

# ── Gossip pair chemistry ───────────────────────────────────────────────

# Pre-defined pair dynamics: (agent_a, agent_b) -> description
# Used to flavor the gossip system prompt.
GOSSIP_PAIRS: dict[tuple[str, str], str] = {
    ("metis", "kallos"): (
        "Strategist and aesthete — intellectual tea-spilling, respectful but competitive. "
        "Metis is analytical; Kallos is expressive. They admire each other but love to one-up."
    ),
    ("metis", "mneme"): (
        "Planner and scribe — the record-keepers. They bond over thoroughness but argue "
        "over whose documentation is better. Fond, bookish energy."
    ),
    ("kallos", "dokimasia"): (
        "Beauty and strength — opposites-attract banter. Kallos teases Dokimasia's "
        "bluntness; Dokimasia calls Kallos vain. Underneath, mutual respect."
    ),
    ("dokimasia", "mneme"): (
        "Guardian and historian — the serious pair. Wholesome: they worry about the player "
        "together and compare notes on what went well or poorly."
    ),
    ("techne", "kallos"): (
        "Builder and stylist — creative rivalry. 'My code is art!' 'Your code NEEDS art.' "
        "Playful competition over who makes things more beautiful."
    ),
    ("techne", "dokimasia"): (
        "Builder and tester — sibling rivalry. 'I bet my code passes first try!' "
        "'It never does~' Competitive but deeply familiar with each other."
    ),
    ("metis", "techne"): (
        "Planner and builder — the design-vs-implementation debate. Metis plans, "
        "Techne improvises. They argue but make a lethal combo."
    ),
    ("kallos", "mneme"): (
        "Aesthete and archivist — they bond over appreciation of fine details. "
        "Kallos loves beauty; Mneme loves precision. Quiet, warm friendship."
    ),
    ("metis", "dokimasia"): (
        "Strategist and guardian — both protective of quality. Metis plans defense; "
        "Dokimasia enforces it. Respect-based, slightly formal."
    ),
    ("techne", "mneme"): (
        "Builder and scribe — Techne creates, Mneme documents. Techne finds docs boring; "
        "Mneme finds undocumented code criminal. Bickering partners."
    ),
}


def _normalize_pair(a: str, b: str) -> tuple[str, str]:
    """Normalize agent pair to canonical order for lookup."""
    return (min(a, b), max(a, b))


def get_pair_chemistry(agent_a: str, agent_b: str) -> str:
    """Get the chemistry description for a gossip pair."""
    pair = _normalize_pair(agent_a, agent_b)
    return GOSSIP_PAIRS.get(pair, f"{pair[0].title()} and {pair[1].title()} chat casually.")
