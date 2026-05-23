"""Citation artifact data classes + filesystem write/read.

The PaperMetadata fields populated from API responses (title, authors,
year, doi, arxiv_id, urls) are the load-bearing-correctness fields; they
must never be LLM-generated. The frontmatter writer in this module copies
them verbatim from PaperMetadata into the artifact YAML.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PaperMetadata(BaseModel):
    """Verbatim-from-API paper identity.

    Either arxiv_id or doi must be present (or both). Title + authors + year
    + at least one URL are always required.
    """

    title: str
    authors: list[str] = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    venue: str | None = None
    venue_full: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    urls: dict[str, str]  # keys: abs, pdf, html (any subset)

    @model_validator(mode="after")
    def _at_least_one_identifier(self) -> PaperMetadata:
        if not self.arxiv_id and not self.doi:
            raise ValueError(
                "PaperMetadata requires at least one of arxiv_id or doi"
            )
        return self


class TriangulationResult(BaseModel):
    """Outcome of the secondary-source cross-check."""

    verified: bool
    primary_source: str
    secondary_source: str | None
    decisive_fields_checked: list[str]
    decisive_fields_agreed: bool
    notes: list[str] = Field(default_factory=list)
    single_source_verified: bool = False


class ConflictReport(BaseModel):
    """Returned to caller when verify_and_cite refuses to emit a citation."""

    kind: str  # "triangulation_mismatch" | "no_candidates" | "no_supporting_excerpts" | "retries_exhausted" | "text_unavailable"
    field_disagreements: list[tuple[str, Any, Any]] = Field(default_factory=list)
    primary_meta_summary: str | None = None
    secondary_meta_summary: str | None = None
    detail: str | None = None


_DOI_URL_PREFIX_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)
_ARXIV_VERSION_RE = re.compile(r"v\d+$")
_AUTHOR_SUFFIX_RE = re.compile(
    r"\s+(?:jr\.?|sr\.?|iii|iv|ii)$", re.IGNORECASE
)


def normalize_doi(doi: str | None) -> str | None:
    """Canonical DOI form per the DOI Foundation: case-insensitive, no URL prefix."""
    if doi is None:
        return None
    stripped = _DOI_URL_PREFIX_RE.sub("", doi.strip())
    return stripped.lower()


def normalize_arxiv_id(arxiv_id: str | None) -> str | None:
    """Strip version suffix (vN) but preserve category prefix on old-style IDs."""
    if arxiv_id is None:
        return None
    return _ARXIV_VERSION_RE.sub("", arxiv_id.strip())


def normalize_title(title: str) -> str:
    """NFKD unicode + lowercase + strip punctuation + collapse whitespace.

    Used by the rapidfuzz title-match decisive-field check at threshold 0.92.
    """
    # NFKD decomposes accents into base char + combining mark; strip the marks.
    nfkd = unicodedata.normalize("NFKD", title)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_accents.lower()
    # Strip everything that isn't alphanumeric or whitespace
    alphanumeric = re.sub(r"[^\w\s]", " ", lowered)
    # Collapse runs of whitespace
    return re.sub(r"\s+", " ", alphanumeric).strip()


def normalize_surname(surname: str) -> str:
    """NFKD + lowercase + strip accents/hyphens + drop common suffixes (Jr., III)."""
    no_suffix = _AUTHOR_SUFFIX_RE.sub("", surname.strip())
    nfkd = unicodedata.normalize("NFKD", no_suffix)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower().replace("-", "").strip()


_TITLE_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "with"}
)


def _first_significant_word(title: str) -> str:
    """Heuristic first-meaningful-word extraction: skip common stopwords."""
    normalized = normalize_title(title)
    for word in normalized.split():
        if word and word not in _TITLE_STOPWORDS:
            return word
    return "untitled"


def _last_name(author: str) -> str:
    """Heuristic last-name extraction: rightmost whitespace-split token after
    suffix removal. Handles 'First Last', 'First Middle Last', 'El Mhamdi'."""
    no_suffix = _AUTHOR_SUFFIX_RE.sub("", author.strip())
    parts = no_suffix.split()
    if not parts:
        return "unknown"
    return normalize_surname(parts[-1])


def slug_for_paper(meta: PaperMetadata) -> str:
    """Deterministic filesystem-safe slug.

    Format: {paper_id}-{first_author_last_name}-{first_significant_title_word}

    paper_id is arxiv_id (preferred) or doi (slashes → underscores, lowercased).
    """
    if meta.arxiv_id:
        paper_id = normalize_arxiv_id(meta.arxiv_id) or "noid"
    elif meta.doi:
        paper_id = (normalize_doi(meta.doi) or "noid").replace("/", "_")
    else:
        paper_id = "noid"  # validator should prevent this, but be defensive

    surname = _last_name(meta.authors[0])
    keyword = _first_significant_word(meta.title)
    return f"{paper_id}-{surname}-{keyword}"
