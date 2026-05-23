"""Citation artifact data classes + filesystem write/read.

The PaperMetadata fields populated from API responses (title, authors,
year, doi, arxiv_id, urls) are the load-bearing-correctness fields; they
must never be LLM-generated. The frontmatter writer in this module copies
them verbatim from PaperMetadata into the artifact YAML.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


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
            raise ValueError("PaperMetadata requires at least one of arxiv_id or doi")
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
_AUTHOR_SUFFIX_RE = re.compile(r"\s+(?:jr\.?|sr\.?|iii|iv|ii)$", re.IGNORECASE)


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


_TITLE_STOPWORDS = frozenset({"a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "with"})

_SLUG_SAFE_RE = re.compile(r"[^a-z0-9_-]")


def _filesystem_safe(s: str, fallback: str) -> str:
    """Filter string to filesystem-safe chars [a-z0-9_-], fallback if empty."""
    cleaned = _SLUG_SAFE_RE.sub("", s)
    return cleaned or fallback


def _first_significant_word(title: str) -> str:
    """Heuristic first-meaningful-word extraction: skip common stopwords."""
    normalized = normalize_title(title)
    for word in normalized.split():
        if word and word not in _TITLE_STOPWORDS:
            return _filesystem_safe(word, "untitled")
    return "untitled"


def _last_name(author: str) -> str:
    """Last whitespace-split token after suffix removal — works for
    'First Last', 'First Middle Last', and 'El Mhamdi'-style prefixes."""
    no_suffix = _AUTHOR_SUFFIX_RE.sub("", author.strip())
    parts = no_suffix.split()
    if not parts:
        return "unknown"
    normalized = normalize_surname(parts[-1])
    return _filesystem_safe(normalized, "unknown")


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


def _bibtex_for(meta: PaperMetadata) -> str:
    """Generate a minimal BibTeX entry for the artifact body."""
    surname = _last_name(meta.authors[0])
    keyword = _first_significant_word(meta.title)
    bib_key = f"{surname}{meta.year}{keyword}"
    authors_and = " and ".join(meta.authors)
    if meta.arxiv_id:
        return (
            f"@article{{{bib_key},\n"
            f"  title={{{meta.title}}},\n"
            f"  author={{{authors_and}}},\n"
            f"  journal={{arXiv preprint arXiv:{meta.arxiv_id}}},\n"
            f"  year={{{meta.year}}}\n"
            f"}}"
        )
    return (
        f"@article{{{bib_key},\n"
        f"  title={{{meta.title}}},\n"
        f"  author={{{authors_and}}},\n"
        f"  year={{{meta.year}}},\n"
        f"  doi={{{meta.doi}}}\n"
        f"}}"
    )


def _citation_snippet(meta: PaperMetadata) -> str:
    authors_str = ", ".join(meta.authors)
    if meta.arxiv_id:
        suffix = f"arXiv:{meta.arxiv_id} ({meta.year})."
    else:
        suffix = f"DOI {meta.doi} ({meta.year})."
    return f"{authors_str}. *{meta.title}*. {suffix}"


def write_citation_artifact(
    *,
    meta: PaperMetadata,
    claim: str,
    excerpts: Iterable[tuple[str, str]],  # (quote, location_ref)
    triangulation: TriangulationResult,
    abstract: str,
    project_root: Path,
    verified_at: dt.datetime | None = None,
    human_overridden: bool = False,
    override_reason: str | None = None,
    verification_version: str = "1.0",
) -> Path:
    """Write `docs/citations/{slug}.md` under project_root.

    Frontmatter fields title/authors/year/arxiv_id/doi/urls come VERBATIM
    from `meta` (which the caller must have populated from API JSON).
    """
    slug = slug_for_paper(meta)
    artifact_dir = project_root / "docs" / "citations"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{slug}.md"

    verified_at = verified_at or dt.datetime.now(dt.UTC)
    sources = [triangulation.primary_source]
    if triangulation.secondary_source:
        sources.append(triangulation.secondary_source)

    frontmatter: dict[str, object] = {
        "title": meta.title,
        "authors": list(meta.authors),
        "year": meta.year,
        "venue": meta.venue,
        "venue_full": meta.venue_full,
        "arxiv_id": meta.arxiv_id,
        "doi": meta.doi,
        "urls": dict(meta.urls),
        "sources_consulted": sources,
        "triangulation": {
            "primary_source": triangulation.primary_source,
            "secondary_source": triangulation.secondary_source,
            "decisive_fields_agreed": triangulation.decisive_fields_agreed,
            "decisive_fields_checked": list(triangulation.decisive_fields_checked),
            "notes": list(triangulation.notes),
        },
        "single_source_verified": triangulation.single_source_verified,
        "verified_by": "aletheia",
        "verified_at": verified_at.isoformat(),
        "verification_version": verification_version,
        "human_overridden": human_overridden,
        "override_reason": override_reason,
        "claim_supported": claim,
    }

    body_parts = [
        "---",
        yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).rstrip(),
        "---",
        "",
        "## Abstract",
        "",
        abstract or "_(abstract unavailable)_",
        "",
        "## Excerpts supporting the claim",
        "",
    ]
    if excerpts:
        for quote, ref in excerpts:
            body_parts.extend(f"> {line}" for line in quote.splitlines() or [quote])
            body_parts.append(f"> ({ref})")
            body_parts.append("")
    else:
        body_parts.append("_(no verbatim excerpts captured; see triangulation status)_")
        body_parts.append("")
    body_parts.append("## Citation snippet")
    body_parts.append("")
    body_parts.append(_citation_snippet(meta))
    body_parts.append("")
    body_parts.append("## BibTeX")
    body_parts.append("")
    body_parts.append("```bibtex")
    body_parts.append(_bibtex_for(meta))
    body_parts.append("```")

    artifact_path.write_text("\n".join(body_parts), encoding="utf-8")
    return artifact_path


def read_citation_artifact(path: Path) -> tuple[PaperMetadata, TriangulationResult]:
    """Parse the frontmatter back into PaperMetadata + TriangulationResult."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path}: unterminated YAML frontmatter")
    fm = yaml.safe_load(text[4:end])

    meta = PaperMetadata(
        title=fm["title"],
        authors=list(fm["authors"]),
        year=fm["year"],
        venue=fm.get("venue"),
        venue_full=fm.get("venue_full"),
        arxiv_id=fm.get("arxiv_id"),
        doi=fm.get("doi"),
        urls=dict(fm["urls"]),
    )
    t = fm["triangulation"]
    triang = TriangulationResult(
        verified=t["decisive_fields_agreed"],
        primary_source=t["primary_source"],
        secondary_source=t.get("secondary_source"),
        decisive_fields_checked=list(t.get("decisive_fields_checked", [])),
        decisive_fields_agreed=t["decisive_fields_agreed"],
        notes=list(t.get("notes", [])),
        single_source_verified=fm.get("single_source_verified", False),
    )
    return meta, triang
