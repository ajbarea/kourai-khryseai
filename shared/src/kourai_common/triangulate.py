"""Triangulation gate — cross-source agreement check on decisive fields.

The Judge step of Aletheia's verify-and-cite loop. Compares the chosen
paper's metadata against a secondary source (OpenAlex via DOI, or arXiv
via arxiv_id) and rejects the citation if any decisive field disagrees.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from kourai_common.citation_artifacts import (
    ConflictReport,
    PaperMetadata,
    TriangulationResult,
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


def triangulate(
    primary: PaperMetadata,
    secondary: PaperMetadata | None,
    *,
    primary_source: str,
    secondary_source: str | None,
) -> tuple[TriangulationResult | None, ConflictReport | None]:
    """Cross-check primary against secondary on the decisive fields.

    Returns `(TriangulationResult, None)` on agreement, or
    `(None, ConflictReport)` on any decisive-field mismatch.
    """
    if secondary is None:
        return (
            TriangulationResult(
                verified=True,
                primary_source=primary_source,
                secondary_source=None,
                decisive_fields_checked=[],
                decisive_fields_agreed=True,
                notes=["no_secondary_source_available"],
                single_source_verified=True,
            ),
            None,
        )

    disagreements: list[tuple[str, object, object]] = []
    fields_checked: list[str] = []
    notes: list[str] = []

    # DOI (when both have it)
    doi_match = compare_dois(primary.doi, secondary.doi)
    if doi_match is not None:
        fields_checked.append("doi")
        if not doi_match:
            disagreements.append(("doi", primary.doi, secondary.doi))

    # arXiv ID (when both have it)
    arxiv_match = compare_arxiv_ids(primary.arxiv_id, secondary.arxiv_id)
    if arxiv_match is not None:
        fields_checked.append("arxiv_id")
        if not arxiv_match:
            disagreements.append(("arxiv_id", primary.arxiv_id, secondary.arxiv_id))

    # Title (always checked)
    fields_checked.append("title")
    if not compare_titles(primary.title, secondary.title):
        disagreements.append(("title", primary.title, secondary.title))

    # First-author surname (always checked)
    fields_checked.append("first_author_surname")
    if not compare_first_author_surname(primary.authors[0], secondary.authors[0]):
        disagreements.append(("first_author_surname", primary.authors[0], secondary.authors[0]))

    # Year (always checked)
    fields_checked.append("year")
    if not compare_years(primary.year, secondary.year):
        disagreements.append(("year", primary.year, secondary.year))

    # Venue (non-decisive, but record disagreements as notes)
    if not venues_equivalent(primary.venue, secondary.venue):
        notes.append(f"venue_aliases: '{primary.venue}' vs '{secondary.venue}' (non-decisive)")

    if disagreements:
        return (
            None,
            ConflictReport(
                kind="triangulation_mismatch",
                field_disagreements=disagreements,
                primary_meta_summary=f"{primary.authors[0]}, {primary.year}",
                secondary_meta_summary=f"{secondary.authors[0]}, {secondary.year}",
                detail=f"Decisive-field disagreement between {primary_source} and {secondary_source}.",
            ),
        )

    return (
        TriangulationResult(
            verified=True,
            primary_source=primary_source,
            secondary_source=secondary_source,
            decisive_fields_checked=fields_checked,
            decisive_fields_agreed=True,
            notes=notes,
            single_source_verified=False,
        ),
        None,
    )
