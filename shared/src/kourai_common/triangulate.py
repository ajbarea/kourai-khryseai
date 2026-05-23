"""Triangulation gate — cross-source agreement check on decisive fields.

The Judge step of Aletheia's verify-and-cite loop. Compares the chosen
paper's metadata against a secondary source (OpenAlex via DOI, or arXiv
via arxiv_id) and rejects the citation if any decisive field disagrees.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from kourai_common.citation_artifacts import (
    normalize_arxiv_id,
    normalize_doi,
    normalize_surname,
    normalize_title,
)


def compare_dois(a: str | None, b: str | None) -> bool | None:
    """None means 'no comparison possible'; True/False is a verdict."""
    if a is None or b is None:
        return None
    return normalize_doi(a) == normalize_doi(b)


def compare_arxiv_ids(a: str | None, b: str | None) -> bool | None:
    if a is None or b is None:
        return None
    return normalize_arxiv_id(a) == normalize_arxiv_id(b)


# Title-match threshold per the design spec: 0.92 = high-precision tier
# (Vikranth3140 citation-hallucination-detection pipeline; pdfmux 2026
# benchmark identified 0.85-0.90 as "everything is duplicate" tier).
_TITLE_THRESHOLD = 92.0


def compare_titles(a: str, b: str) -> bool:
    score = fuzz.ratio(normalize_title(a), normalize_title(b))
    return score >= _TITLE_THRESHOLD


def _surname_only(author: str) -> str:
    """Last whitespace-split token, normalized."""
    parts = author.strip().split()
    if not parts:
        return ""
    return normalize_surname(parts[-1])


def compare_first_author_surname(a: str, b: str) -> bool:
    return _surname_only(a) == _surname_only(b)


def compare_years(a: int, b: int) -> bool:
    return a == b


# Hand-maintained venue aliases. Add cases as the corpus reveals them.
# Format: each list is one equivalence class; venues_equivalent returns
# True iff both venues fall into the same class.
VENUE_ALIASES: list[frozenset[str]] = [
    frozenset(
        {
            "neurips",
            "nips",
            "advances in neural information processing systems",
        }
    ),
    frozenset(
        {
            "icml",
            "international conference on machine learning",
            "proceedings of machine learning research",
        }
    ),
    frozenset(
        {
            "iclr",
            "international conference on learning representations",
        }
    ),
    frozenset(
        {
            "usenix security",
            "usenix security symposium",
        }
    ),
    frozenset(
        {
            "ieee transactions on signal processing",
            "ieee tsp",
            "tsp",
        }
    ),
    frozenset(
        {
            "esorics",
            "european symposium on research in computer security",
        }
    ),
]


def _normalize_venue(v: str) -> str:
    """Lowercase + strip year tokens + strip punctuation."""
    no_year = re.sub(r"\b(19|20)\d{2}\b", "", v)
    return normalize_title(no_year)


def venues_equivalent(a: str | None, b: str | None) -> bool:
    """Non-decisive: None on either side means we can't reject."""
    if a is None or b is None:
        return True
    na = _normalize_venue(a)
    nb = _normalize_venue(b)
    if na == nb:
        return True
    for alias_set in VENUE_ALIASES:
        in_a = any(alias in na for alias in alias_set)
        in_b = any(alias in nb for alias in alias_set)
        if in_a and in_b:
            return True
    return False
