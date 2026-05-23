# Aletheia v2 — Citation Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Specialize the existing Aletheia agent with a mechanical, artifact-first academic-citation verification path that catches the 5 classes of citation hallucination identified in the design spec.

**Architecture:** 5-tool decomposition driven by Claude native tool-use (`extract_claim` / `search_papers` / `fetch_paper_text` / `match_evidence` / `triangulate`), three direct-HTTP backends (Semantic Scholar primary retrieval, OpenAlex triangulation gate, arXiv preprints + HTML5 text), per-project `docs/citations/{slug}.md` artifacts with CFF-aligned YAML frontmatter and verbatim-substring-verified excerpts.

**Tech Stack:** Python 3.12, httpx + tenacity (HTTP), rapidfuzz (title fuzzy match), docling (PDF→Markdown, Apache 2.0), pydantic (frontmatter schema), pyyaml (frontmatter parsing), pytest + hypothesis + pytest-recording/vcrpy (testing). Reuses kourai's existing `chat_with_tools` agent loop.

**Spec reference:** [`docs/architecture/2026-05-23-aletheia-v2-citation-verification-design.md`](./2026-05-23-aletheia-v2-citation-verification-design.md)

---

## File structure

Six PRs land in dependency order. Each PR produces working, tested software on its own.

| PR | New files | Modified files | Depends on |
| --- | --- | --- | --- |
| 1 | `shared/src/kourai_common/citation_artifacts.py`, `tests/unit/test_citation_artifacts.py`, fixtures | `pyproject.toml` (new deps) | — |
| 2 | `shared/src/kourai_common/triangulate.py`, `tests/unit/test_triangulate.py` | — | PR 1 |
| 3 | `shared/src/kourai_common/academic_search.py`, `tests/integration/test_academic_search.py`, `tests/cassettes/*.yaml` | `pyproject.toml` (new deps) | PR 1 |
| 4 | `tests/integration/test_aletheia_verify_cite.py`, `tests/nightly/test_api_contracts.py` | `agents/aletheia/agent.py` | PR 1, 2, 3 |
| 5 | `scripts/check_citations.py`, `tests/unit/test_check_citations.py`, `.github/workflows/check-citations.yml` | `.pre-commit-config.yaml` (new file if absent) | PR 1 |
| 6 | `docs/agents/aletheia.md`, `docs/architecture/aletheia-v2-architecture.md` (small overview) | `docs/agents/specialists.md` (link), `mkdocs.yml`/`zensical.toml` (nav) | PR 4 |

PR 5 (mechanical CI check) only depends on PR 1 (artifact schema); can be developed in parallel with PR 2/3 if desired.

---

## PR 1 — Citation artifacts foundation

**Scope:** `PaperMetadata` schema + slug generation + frontmatter write/read + the five normalization helpers. No HTTP. No LLM. Pure data + filesystem.

### Task 1.1: Add runtime dependencies

**Files:**
- Modify: `pyproject.toml` — add `httpx`, `tenacity`, `rapidfuzz`, `docling`, `pyyaml` (if not present)

- [ ] **Step 1: Inspect current deps**

Run: `grep -E "httpx|tenacity|rapidfuzz|docling|pyyaml|pydantic" pyproject.toml`

Expected: `pydantic` and `pyyaml` likely present (kourai uses both); `httpx`, `tenacity`, `rapidfuzz`, `docling` likely absent.

- [ ] **Step 2: Add missing deps**

Edit `pyproject.toml` `[project] dependencies` (or `[project.optional-dependencies] aletheia-v2` for an opt-in extra; prefer the latter to avoid bloating non-Aletheia users):

```toml
[project.optional-dependencies]
aletheia-v2 = [
    "httpx>=0.28",
    "tenacity>=9.0",
    "rapidfuzz>=3.10",
    "docling>=2.10",
    # pyyaml + pydantic already in core
]
```

- [ ] **Step 3: Lock and sync**

Run: `uv lock && uv sync --extra aletheia-v2`

Expected: lockfile updated, packages installed, `uv run python -c "import httpx, tenacity, rapidfuzz, docling, yaml, pydantic"` succeeds.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(aletheia-v2): add citation-verification runtime deps (httpx, tenacity, rapidfuzz, docling)"
```

---

### Task 1.2: PaperMetadata + TriangulationResult + ConflictReport dataclasses

**Files:**
- Create: `shared/src/kourai_common/citation_artifacts.py`
- Test: `tests/unit/test_citation_artifacts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_citation_artifacts.py`:

```python
"""Tests for citation_artifacts data classes + helpers."""

from __future__ import annotations

import pytest

from kourai_common.citation_artifacts import (
    ConflictReport,
    PaperMetadata,
    TriangulationResult,
)


class TestPaperMetadata:
    def test_required_fields(self):
        meta = PaperMetadata(
            title="SoK: Benchmarking Poisoning Attacks",
            authors=["Heyi Zhang", "Yule Liu"],
            year=2025,
            urls={"abs": "https://arxiv.org/abs/2502.03801"},
            arxiv_id="2502.03801",
        )
        assert meta.title.startswith("SoK")
        assert meta.authors[0] == "Heyi Zhang"
        assert meta.year == 2025
        assert meta.arxiv_id == "2502.03801"
        assert meta.doi is None
        assert meta.venue is None

    def test_requires_arxiv_or_doi(self):
        with pytest.raises(ValueError, match="arxiv_id or doi"):
            PaperMetadata(
                title="No identifier paper",
                authors=["Anon"],
                year=2025,
                urls={},
                arxiv_id=None,
                doi=None,
            )


class TestTriangulationResult:
    def test_verified_true(self):
        result = TriangulationResult(
            verified=True,
            primary_source="semantic_scholar",
            secondary_source="openalex",
            decisive_fields_checked=["title", "year"],
            decisive_fields_agreed=True,
        )
        assert result.verified is True
        assert result.notes == []

    def test_skipped_case(self):
        result = TriangulationResult(
            verified=True,
            primary_source="semantic_scholar",
            secondary_source=None,
            decisive_fields_checked=[],
            decisive_fields_agreed=True,
            notes=["no_secondary_source_available"],
            single_source_verified=True,
        )
        assert result.single_source_verified is True


class TestConflictReport:
    def test_field_disagreements(self):
        conflict = ConflictReport(
            kind="triangulation_mismatch",
            field_disagreements=[
                ("first_author_surname", "Zhang", "Liu"),
                ("year", 2025, 2024),
            ],
            primary_meta_summary="Heyi Zhang, 2025",
            secondary_meta_summary="Yule Liu, 2024",
        )
        assert len(conflict.field_disagreements) == 2
        assert conflict.field_disagreements[0][0] == "first_author_surname"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'kourai_common.citation_artifacts'`.

- [ ] **Step 3: Write the data classes**

Create `shared/src/kourai_common/citation_artifacts.py`:

```python
"""Citation artifact data classes + filesystem write/read.

The PaperMetadata fields populated from API responses (title, authors,
year, doi, arxiv_id, urls) are the load-bearing-correctness fields; they
must never be LLM-generated. The frontmatter writer in this module copies
them verbatim from PaperMetadata into the artifact YAML.
"""

from __future__ import annotations

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/src/kourai_common/citation_artifacts.py tests/unit/test_citation_artifacts.py
git commit -m "feat(aletheia-v2): PaperMetadata + TriangulationResult + ConflictReport schemas"
```

---

### Task 1.3: Normalization helpers (DOI, title, surname, arxiv_id)

**Files:**
- Modify: `shared/src/kourai_common/citation_artifacts.py` (add helpers)
- Modify: `tests/unit/test_citation_artifacts.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_citation_artifacts.py`:

```python
from kourai_common.citation_artifacts import (
    normalize_arxiv_id,
    normalize_doi,
    normalize_surname,
    normalize_title,
)


class TestNormalizeDoi:
    def test_lowercase(self):
        assert normalize_doi("10.1109/TSP.2022.3153135") == "10.1109/tsp.2022.3153135"

    def test_strips_url_prefix(self):
        assert normalize_doi("https://doi.org/10.1109/TSP.2022.3153135") == "10.1109/tsp.2022.3153135"

    def test_strips_http_prefix(self):
        assert normalize_doi("http://dx.doi.org/10.1109/TSP.2022.3153135") == "10.1109/tsp.2022.3153135"

    def test_idempotent(self):
        once = normalize_doi("https://doi.org/10.1109/TSP.2022.3153135")
        twice = normalize_doi(once)
        assert once == twice

    def test_none_returns_none(self):
        assert normalize_doi(None) is None


class TestNormalizeArxivId:
    def test_strips_version_v1(self):
        assert normalize_arxiv_id("2502.03801v1") == "2502.03801"

    def test_strips_version_v9(self):
        assert normalize_arxiv_id("1902.06156v9") == "1902.06156"

    def test_no_version_unchanged(self):
        assert normalize_arxiv_id("2502.03801") == "2502.03801"

    def test_old_style_id_with_category(self):
        # Pre-2007 arxiv IDs use category/YYMMnnn format
        assert normalize_arxiv_id("cs.LG/0306024") == "cs.LG/0306024"

    def test_none_returns_none(self):
        assert normalize_arxiv_id(None) is None


class TestNormalizeTitle:
    def test_lowercase(self):
        assert normalize_title("Hello World") == "hello world"

    def test_collapse_whitespace(self):
        assert normalize_title("Hello\n  World") == "hello world"

    def test_strip_punctuation(self):
        assert normalize_title("SoK: Benchmarking, Attacks!") == "sok benchmarking attacks"

    def test_unicode_nfkd(self):
        # "Café" → "cafe" after NFKD + accent strip
        assert normalize_title("Café Federated") == "cafe federated"

    def test_idempotent(self):
        once = normalize_title("Hello, WORLD!")
        twice = normalize_title(once)
        assert once == twice


class TestNormalizeSurname:
    def test_lowercase_strip_accents(self):
        assert normalize_surname("García") == "garcia"

    def test_strip_hyphens(self):
        assert normalize_surname("El-Mhamdi") == "elmhamdi"

    def test_strip_jr_suffix(self):
        assert normalize_surname("Smith Jr.") == "smith"

    def test_strip_iii_suffix(self):
        assert normalize_surname("Smith III") == "smith"

    def test_strip_leading_trailing_whitespace(self):
        assert normalize_surname("  Zhang  ") == "zhang"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v -k "Normalize"`

Expected: ImportError or FAIL — normalizers not yet defined.

- [ ] **Step 3: Implement the helpers**

Append to `shared/src/kourai_common/citation_artifacts.py`:

```python
import re
import unicodedata

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v`

Expected: all tests pass (Task 1.2 + Task 1.3 tests, 19 total).

- [ ] **Step 5: Commit**

```bash
git add shared/src/kourai_common/citation_artifacts.py tests/unit/test_citation_artifacts.py
git commit -m "feat(aletheia-v2): DOI/arxiv-id/title/surname normalization helpers"
```

---

### Task 1.4: Slug generation

**Files:**
- Modify: `shared/src/kourai_common/citation_artifacts.py`
- Modify: `tests/unit/test_citation_artifacts.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_citation_artifacts.py`:

```python
from kourai_common.citation_artifacts import slug_for_paper


class TestSlugForPaper:
    def test_arxiv_id_slug(self):
        meta = PaperMetadata(
            title="SoK: Benchmarking Poisoning Attacks in FL",
            authors=["Heyi Zhang"],
            year=2025,
            urls={"abs": "https://arxiv.org/abs/2502.03801"},
            arxiv_id="2502.03801",
        )
        assert slug_for_paper(meta) == "2502.03801-zhang-sok"

    def test_doi_slug_with_slash_to_underscore(self):
        meta = PaperMetadata(
            title="Robust Aggregation for Federated Learning",
            authors=["Krishna Pillutla"],
            year=2022,
            urls={"abs": "https://doi.org/10.1109/TSP.2022.3153135"},
            doi="10.1109/TSP.2022.3153135",
        )
        # DOI slash → underscore, lowercase
        assert slug_for_paper(meta) == "10.1109_tsp.2022.3153135-pillutla-robust"

    def test_skips_articles_in_title_keyword(self):
        # "A", "The", "An" should not be the title keyword
        meta = PaperMetadata(
            title="The Hidden Vulnerability of Distributed Learning",
            authors=["El Mhamdi"],
            year=2018,
            urls={"abs": "https://arxiv.org/abs/1802.07927"},
            arxiv_id="1802.07927",
        )
        assert slug_for_paper(meta) == "1802.07927-mhamdi-hidden"

    def test_uses_last_name_when_full_name_provided(self):
        meta = PaperMetadata(
            title="Krum",
            authors=["Peva Blanchard", "El Mahdi El Mhamdi"],
            year=2017,
            urls={"abs": "https://papers.nips.cc/paper/6617"},
            arxiv_id="1703.02757",
        )
        assert slug_for_paper(meta) == "1703.02757-blanchard-krum"

    def test_deterministic(self):
        meta = PaperMetadata(
            title="Same Paper",
            authors=["First Author"],
            year=2025,
            urls={"abs": "https://arxiv.org/abs/2025.0001"},
            arxiv_id="2025.0001",
        )
        assert slug_for_paper(meta) == slug_for_paper(meta)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v -k "Slug"`

Expected: ImportError on `slug_for_paper`.

- [ ] **Step 3: Implement slug_for_paper**

Append to `shared/src/kourai_common/citation_artifacts.py`:

```python
_TITLE_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "with"}
)


def _first_significant_word(title: str) -> str:
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
```

- [ ] **Step 4: Run to verify**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v`

Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/src/kourai_common/citation_artifacts.py tests/unit/test_citation_artifacts.py
git commit -m "feat(aletheia-v2): slug_for_paper deterministic artifact filename generator"
```

---

### Task 1.5: Artifact write/read round-trip + hypothesis property tests

**Files:**
- Modify: `shared/src/kourai_common/citation_artifacts.py`
- Modify: `tests/unit/test_citation_artifacts.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_citation_artifacts.py`:

```python
import datetime as dt
from pathlib import Path

from hypothesis import given, strategies as st

from kourai_common.citation_artifacts import (
    read_citation_artifact,
    write_citation_artifact,
)


class TestWriteReadRoundTrip:
    def test_round_trip_arxiv_paper(self, tmp_path: Path):
        meta = PaperMetadata(
            title="SoK: Benchmarking Poisoning Attacks",
            authors=["Heyi Zhang", "Yule Liu", "Xinlei He"],
            year=2025,
            venue="arXiv preprint",
            urls={
                "abs": "https://arxiv.org/abs/2502.03801",
                "pdf": "https://arxiv.org/pdf/2502.03801",
            },
            arxiv_id="2502.03801",
        )
        triangulation = TriangulationResult(
            verified=True,
            primary_source="semantic_scholar",
            secondary_source="openalex",
            decisive_fields_checked=["title", "first_author_surname", "year", "arxiv_id"],
            decisive_fields_agreed=True,
        )
        path = write_citation_artifact(
            meta=meta,
            claim="FLPoison includes ALIE and Fang attacks",
            excerpts=[("We evaluate 15 representative attacks", "Abstract")],
            triangulation=triangulation,
            abstract="This survey benchmarks 15 representative attacks...",
            project_root=tmp_path,
        )

        assert path.exists()
        assert path.parent.name == "citations"
        assert "2502.03801-zhang-sok" in path.name

        loaded_meta, loaded_triang = read_citation_artifact(path)
        assert loaded_meta.title == meta.title
        assert loaded_meta.authors == meta.authors
        assert loaded_meta.year == meta.year
        assert loaded_meta.arxiv_id == meta.arxiv_id
        assert loaded_triang.verified is True
        assert loaded_triang.decisive_fields_agreed is True


# Property-based: any valid PaperMetadata round-trips
@st.composite
def paper_metadata_strategy(draw):
    return PaperMetadata(
        title=draw(st.text(min_size=3, max_size=80, alphabet=st.characters(min_codepoint=32, max_codepoint=126))),
        authors=draw(st.lists(st.text(min_size=2, max_size=40, alphabet=st.characters(min_codepoint=32, max_codepoint=126)), min_size=1, max_size=10)),
        year=draw(st.integers(min_value=1900, max_value=2100)),
        urls={"abs": "https://example.com/paper"},
        arxiv_id=draw(st.sampled_from(["2502.03801", "1902.06156", None])),
        doi=draw(st.sampled_from(["10.1109/TSP.2022.3153135", None])),
    )


@given(meta=paper_metadata_strategy())
def test_round_trip_property(meta: PaperMetadata, tmp_path: Path):
    triangulation = TriangulationResult(
        verified=True,
        primary_source="semantic_scholar",
        secondary_source=None,
        decisive_fields_checked=[],
        decisive_fields_agreed=True,
        single_source_verified=True,
    )
    path = write_citation_artifact(
        meta=meta,
        claim="property test",
        excerpts=[],
        triangulation=triangulation,
        abstract="prop abstract",
        project_root=tmp_path,
    )
    loaded_meta, _ = read_citation_artifact(path)
    assert loaded_meta.title == meta.title
    assert loaded_meta.authors == meta.authors
    assert loaded_meta.year == meta.year
    assert loaded_meta.arxiv_id == meta.arxiv_id
    assert loaded_meta.doi == meta.doi
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v -k "RoundTrip or round_trip"`

Expected: ImportError on `write_citation_artifact` / `read_citation_artifact`.

- [ ] **Step 3: Implement writer + reader**

Append to `shared/src/kourai_common/citation_artifacts.py`:

```python
import datetime as dt
from pathlib import Path
from typing import Iterable

import yaml


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
            for line in quote.splitlines() or [quote]:
                body_parts.append(f"> {line}")
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
```

- [ ] **Step 4: Run to verify**

Run: `uv run pytest tests/unit/test_citation_artifacts.py -v`

Expected: all tests pass (24 from earlier + ~3 round-trip + property test = ~28).

- [ ] **Step 5: Commit**

```bash
git add shared/src/kourai_common/citation_artifacts.py tests/unit/test_citation_artifacts.py
git commit -m "feat(aletheia-v2): write_citation_artifact + read_citation_artifact round-trip"
```

---

### Task 1.6: Open PR 1, wait for green CI, merge

- [ ] **Step 1: Push branch and open PR**

```bash
git push -u origin feat/aletheia-v2-pr1-artifacts
gh pr create --title "feat(aletheia-v2): citation_artifacts module + unit tests (PR 1/6)" --body "$(cat <<'EOF'
PR 1 of 6 implementing the Aletheia v2 citation-verification design (see docs/architecture/2026-05-23-aletheia-v2-citation-verification-design.md).

## What this PR ships

- New module: shared/src/kourai_common/citation_artifacts.py
  - PaperMetadata, TriangulationResult, ConflictReport pydantic schemas
  - normalize_doi / normalize_arxiv_id / normalize_title / normalize_surname helpers
  - slug_for_paper deterministic filename generator
  - write_citation_artifact / read_citation_artifact frontmatter round-trip
- New deps in [aletheia-v2] optional extra: httpx, tenacity, rapidfuzz, docling
- ~28 unit tests including hypothesis property test on the round-trip invariant

## Anti-hallucination guarantee landed in this PR

PaperMetadata fields title/authors/year/doi/arxiv_id are written into artifact YAML verbatim from the source (caller's responsibility to populate from API JSON, never LLM). The writer code is the proof — diff review confirms no LLM-call path in this module.

## What's NOT in this PR

- API HTTP layer (PR 3)
- Triangulation logic (PR 2)
- Agent integration (PR 4)
- CI mechanical check (PR 5)
- Documentation (PR 6)
EOF
)"
```

- [ ] **Step 2: Monitor CI**

Run: `gh pr checks --watch` until all required checks are green (or open the PR URL in browser).

- [ ] **Step 3: Squash-merge**

```bash
gh pr merge --squash --delete-branch
```

- [ ] **Step 4: Sync local main**

```bash
git checkout main && git pull
```

---

## PR 2 — Triangulation module

**Scope:** `triangulate()` + per-field comparison helpers + `VENUE_ALIASES`. Pure logic over `PaperMetadata` instances from PR 1. No HTTP, no LLM.

### Task 2.1: Branch and field-level comparison primitives

**Files:**
- Create: `shared/src/kourai_common/triangulate.py`
- Test: `tests/unit/test_triangulate.py`

- [ ] **Step 1: Create branch**

```bash
git checkout -b feat/aletheia-v2-pr2-triangulate
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_triangulate.py`:

```python
"""Tests for the triangulation gate."""

from __future__ import annotations

import pytest

from kourai_common.citation_artifacts import PaperMetadata
from kourai_common.triangulate import (
    VENUE_ALIASES,
    compare_arxiv_ids,
    compare_dois,
    compare_first_author_surname,
    compare_titles,
    compare_years,
    venues_equivalent,
)


class TestCompareDois:
    def test_exact(self):
        assert compare_dois("10.1109/TSP.2022.3153135", "10.1109/tsp.2022.3153135") is True

    def test_url_prefix_ignored(self):
        assert compare_dois("https://doi.org/10.1109/TSP.2022.3153135", "10.1109/tsp.2022.3153135") is True

    def test_different_dois(self):
        assert compare_dois("10.1109/TSP.2022.3153135", "10.1109/TSP.2022.9999999") is False

    def test_none_returns_none(self):
        # None means "no comparison possible", not False
        assert compare_dois(None, "10.1109/TSP.2022.3153135") is None
        assert compare_dois("10.1109/TSP.2022.3153135", None) is None


class TestCompareArxivIds:
    def test_exact(self):
        assert compare_arxiv_ids("2502.03801", "2502.03801") is True

    def test_version_stripped(self):
        assert compare_arxiv_ids("2502.03801v1", "2502.03801v2") is True

    def test_different(self):
        assert compare_arxiv_ids("2502.03801", "1902.06156") is False

    def test_none(self):
        assert compare_arxiv_ids(None, "2502.03801") is None


class TestCompareTitles:
    def test_exact(self):
        assert compare_titles("Hello World", "Hello World") is True

    def test_case_insensitive(self):
        assert compare_titles("Hello World", "HELLO WORLD") is True

    def test_punctuation_insensitive(self):
        assert compare_titles("SoK: Benchmarking", "SoK Benchmarking") is True

    def test_whitespace_normalized(self):
        assert compare_titles("Hello  World", "Hello World") is True

    def test_above_92_threshold_accepts(self):
        # Very close: minor word missing
        assert compare_titles(
            "SoK: Benchmarking Poisoning Attacks and Defenses in Federated Learning",
            "Benchmarking Poisoning Attacks and Defenses in Federated Learning",
        ) is True

    def test_below_92_threshold_rejects(self):
        # Completely different
        assert compare_titles("Hello World", "Goodbye Cruel Universe") is False


class TestCompareFirstAuthorSurname:
    def test_exact(self):
        assert compare_first_author_surname("Heyi Zhang", "Heyi Zhang") is True

    def test_last_name_only_accepted(self):
        # Different first name formatting, same surname
        assert compare_first_author_surname("H. Zhang", "Heyi Zhang") is True

    def test_different_surname(self):
        assert compare_first_author_surname("Heyi Zhang", "Yifei Liu") is False

    def test_accent_normalized(self):
        assert compare_first_author_surname("José García", "Jose Garcia") is True


class TestCompareYears:
    def test_exact(self):
        assert compare_years(2025, 2025) is True

    def test_different(self):
        assert compare_years(2025, 2024) is False


class TestVenuesEquivalent:
    def test_alias_match(self):
        assert venues_equivalent("NeurIPS 2019", "NIPS 2019") is True
        assert venues_equivalent(
            "Advances in Neural Information Processing Systems 32",
            "NeurIPS 2019",
        ) is True

    def test_non_alias_different(self):
        assert venues_equivalent("ICML 2019", "NeurIPS 2019") is False

    def test_none_returns_true(self):
        # Missing venue is non-decisive — never rejects
        assert venues_equivalent(None, "NeurIPS 2019") is True
        assert venues_equivalent("NeurIPS 2019", None) is True
```

- [ ] **Step 3: Run to verify fail**

Run: `uv run pytest tests/unit/test_triangulate.py -v`

Expected: ImportError on `kourai_common.triangulate`.

- [ ] **Step 4: Implement the comparison primitives**

Create `shared/src/kourai_common/triangulate.py`:

```python
"""Triangulation gate — cross-source agreement check on decisive fields.

The Judge step of Aletheia's verify-and-cite loop. Compares the chosen
paper's metadata against a secondary source (OpenAlex via DOI, or arXiv
via arxiv_id) and rejects the citation if any decisive field disagrees.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from kourai_common.citation_artifacts import (
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
    frozenset({
        "neurips",
        "nips",
        "advances in neural information processing systems",
    }),
    frozenset({
        "icml",
        "international conference on machine learning",
        "proceedings of machine learning research",
    }),
    frozenset({
        "iclr",
        "international conference on learning representations",
    }),
    frozenset({
        "usenix security",
        "usenix security symposium",
    }),
    frozenset({
        "ieee transactions on signal processing",
        "ieee tsp",
        "tsp",
    }),
    frozenset({
        "esorics",
        "european symposium on research in computer security",
    }),
]


def _normalize_venue(v: str) -> str:
    """Lowercase + strip year tokens + strip punctuation."""
    import re
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
```

- [ ] **Step 5: Run to verify**

Run: `uv run pytest tests/unit/test_triangulate.py -v`

Expected: all comparison-primitive tests pass (~20).

- [ ] **Step 6: Commit**

```bash
git add shared/src/kourai_common/triangulate.py tests/unit/test_triangulate.py
git commit -m "feat(aletheia-v2): field-level comparison primitives + VENUE_ALIASES"
```

---

### Task 2.2: triangulate() orchestrator

**Files:**
- Modify: `shared/src/kourai_common/triangulate.py`
- Modify: `tests/unit/test_triangulate.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_triangulate.py`:

```python
from kourai_common.citation_artifacts import ConflictReport
from kourai_common.triangulate import triangulate


def _meta(
    *, title="Sample Title", authors=("First Author",), year=2025,
    arxiv_id="2025.0001", doi=None, venue=None,
) -> PaperMetadata:
    return PaperMetadata(
        title=title,
        authors=list(authors),
        year=year,
        venue=venue,
        urls={"abs": "https://example.com"},
        arxiv_id=arxiv_id,
        doi=doi,
    )


class TestTriangulate:
    def test_all_decisive_agree(self):
        primary = _meta()
        secondary = _meta()
        result, conflict = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result is not None
        assert conflict is None
        assert result.verified is True
        assert result.decisive_fields_agreed is True

    def test_first_author_mismatch_rejects(self):
        primary = _meta(authors=("Heyi Zhang",))
        secondary = _meta(authors=("Yifei Liu",))
        result, conflict = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result is None
        assert conflict is not None
        assert conflict.kind == "triangulation_mismatch"
        assert any(f[0] == "first_author_surname" for f in conflict.field_disagreements)

    def test_year_mismatch_rejects(self):
        primary = _meta(year=2025)
        secondary = _meta(year=2024)
        result, conflict = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result is None
        assert conflict is not None
        assert any(f[0] == "year" for f in conflict.field_disagreements)

    def test_arxiv_id_mismatch_rejects(self):
        primary = _meta(arxiv_id="2502.03801")
        secondary = _meta(arxiv_id="1902.06156")
        result, conflict = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result is None
        assert conflict is not None
        assert any(f[0] == "arxiv_id" for f in conflict.field_disagreements)

    def test_title_well_above_threshold_accepts(self):
        primary = _meta(title="SoK: Benchmarking Poisoning Attacks")
        # Trivial punctuation difference
        secondary = _meta(title="SoK Benchmarking Poisoning Attacks")
        result, _ = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result is not None
        assert result.verified is True

    def test_title_well_below_threshold_rejects(self):
        primary = _meta(title="SoK: Benchmarking Poisoning Attacks")
        secondary = _meta(title="A Different Paper Entirely")
        result, conflict = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result is None
        assert any(f[0] == "title" for f in conflict.field_disagreements)

    def test_venue_alias_does_not_reject(self):
        primary = _meta(venue="NeurIPS 2019")
        secondary = _meta(venue="NIPS 2019")
        result, _ = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        assert result.verified is True
        # No notes about venue since they're aliased
        assert not any("venue" in n for n in result.notes)

    def test_venue_non_alias_recorded_as_note(self):
        primary = _meta(venue="NeurIPS 2019")
        secondary = _meta(venue="ICML 2019")
        result, _ = triangulate(primary, secondary, primary_source="s2", secondary_source="openalex")
        # Venue is non-decisive — still verified
        assert result.verified is True
        # But recorded as a note
        assert any("venue" in n.lower() for n in result.notes)

    def test_single_source_no_secondary(self):
        primary = _meta()
        result, _ = triangulate(primary, None, primary_source="s2", secondary_source=None)
        assert result.verified is True
        assert result.single_source_verified is True
        assert "no_secondary_source_available" in result.notes
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/test_triangulate.py -v -k Triangulate`

Expected: ImportError on `triangulate`.

- [ ] **Step 3: Implement triangulate()**

Append to `shared/src/kourai_common/triangulate.py`:

```python
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
        disagreements.append(
            ("first_author_surname", primary.authors[0], secondary.authors[0])
        )

    # Year (always checked)
    fields_checked.append("year")
    if not compare_years(primary.year, secondary.year):
        disagreements.append(("year", primary.year, secondary.year))

    # Venue (non-decisive, but record disagreements as notes)
    if not venues_equivalent(primary.venue, secondary.venue):
        notes.append(
            f"venue_aliases: '{primary.venue}' vs '{secondary.venue}' (non-decisive)"
        )

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
```

- [ ] **Step 4: Run to verify**

Run: `uv run pytest tests/unit/test_triangulate.py -v`

Expected: all triangulate tests pass.

- [ ] **Step 5: Commit + push + PR**

```bash
git add shared/src/kourai_common/triangulate.py tests/unit/test_triangulate.py
git commit -m "feat(aletheia-v2): triangulate() orchestrator + decisive-field checks"
git push -u origin feat/aletheia-v2-pr2-triangulate
gh pr create --title "feat(aletheia-v2): triangulate module + unit tests (PR 2/6)" --body "PR 2 of 6 — see docs/architecture/2026-05-23-aletheia-v2-implementation-plan.md"
gh pr checks --watch
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

## PR 3 — Academic search HTTP layer

**Scope:** S2 + OpenAlex + arXiv HTTP clients with tenacity retries. Cassette-based integration tests via vcrpy / pytest-recording.

### Task 3.1: Branch + dev-deps + cassette infrastructure

**Files:**
- Modify: `pyproject.toml` — add `pytest-recording` to `dev` group
- Create: `tests/cassettes/.gitkeep`
- Create: `tests/conftest.py` cassette config (or append if exists)

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/aletheia-v2-pr3-academic-search
```

- [ ] **Step 2: Add pytest-recording**

Edit `pyproject.toml` `[dependency-groups] dev` (or `[tool.uv] dev-dependencies`):

```toml
[dependency-groups]
dev = [
    # ... existing ...
    "pytest-recording>=0.13",  # vcrpy wrapper for pytest
]
```

Run: `uv lock && uv sync --extra aletheia-v2`

- [ ] **Step 3: Create cassette dir + conftest**

Create `tests/cassettes/.gitkeep` (empty file).

If `tests/conftest.py` exists, append; otherwise create:

```python
"""Test configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def vcr_config():
    """vcrpy / pytest-recording cassette config — scrub auth headers."""
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("api-key", "REDACTED"),
            ("x-api-key", "REDACTED"),
        ],
        "record_mode": "none",  # CI must never hit live API
    }
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock tests/cassettes/.gitkeep tests/conftest.py
git commit -m "feat(aletheia-v2): pytest-recording + cassette infra for HTTP tests"
```

---

### Task 3.2: Semantic Scholar client + cassette test

**Files:**
- Create: `shared/src/kourai_common/academic_search.py`
- Create: `tests/integration/test_academic_search.py`
- Create: `tests/cassettes/test_search_semantic_scholar_baruch_alie.yaml` (recorded on first run)

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_academic_search.py`:

```python
"""Integration tests for the academic_search HTTP layer.

Uses pytest-recording / vcrpy: first run hits real APIs and records to
tests/cassettes/*.yaml; subsequent runs replay from disk. CI replays.

Refresh: uv run pytest --record-mode=rewrite tests/integration/test_academic_search.py
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

from kourai_common.academic_search import search_semantic_scholar


@pytest.mark.vcr
async def test_search_semantic_scholar_baruch_alie():
    """Search for the ALIE paper should return Baruch et al. as top hit."""
    candidates = await search_semantic_scholar(
        "A Little Is Enough Circumventing Defenses for Distributed Learning",
        limit=5,
    )
    assert len(candidates) >= 1
    top = candidates[0]
    assert top.year == 2019
    assert "baruch" in top.authors[0].lower()
    assert top.arxiv_id == "1902.06156"


@pytest.mark.vcr
async def test_search_semantic_scholar_zhang_flpoison():
    """Search for the FLPoison SoK should return Heyi Zhang as first author."""
    candidates = await search_semantic_scholar(
        "SoK Benchmarking Poisoning Attacks Federated Learning",
        limit=5,
    )
    assert len(candidates) >= 1
    top = candidates[0]
    assert top.year == 2025
    assert "zhang" in top.authors[0].lower()
    assert top.arxiv_id == "2502.03801"
```

- [ ] **Step 2: Run to verify fail (no cassette yet)**

Run: `uv run pytest tests/integration/test_academic_search.py -v`

Expected: ImportError on `search_semantic_scholar` OR cassette-missing error.

- [ ] **Step 3: Implement Semantic Scholar client**

Create `shared/src/kourai_common/academic_search.py`:

```python
"""HTTP clients for academic citation lookup.

Three direct REST backends — no MCP wrapper (per design spec: May 2026
100-MCP study showed median 71% pass rate; direct HTTP is more reliable).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from kourai_common.citation_artifacts import PaperMetadata

# Polite User-Agent per API guidance (S2, OpenAlex both ask for it)
_KOURAI_UA = (
    "kourai-khryseai/aletheia-v2 (+mailto:ajbareaa@gmail.com)"
)

_RETRY = retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    reraise=True,
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": _KOURAI_UA},
        timeout=httpx.Timeout(15.0),
    )


def _s2_paper_to_meta(p: dict[str, Any]) -> PaperMetadata:
    """Convert a Semantic Scholar paper dict to PaperMetadata.

    Field names follow S2's /graph/v1/paper response schema.
    """
    authors = [a.get("name", "") for a in p.get("authors", [])]
    ext = p.get("externalIds") or {}
    urls: dict[str, str] = {}
    if p.get("openAccessPdf"):
        urls["pdf"] = p["openAccessPdf"]["url"]
    if ext.get("DOI"):
        urls["doi"] = f"https://doi.org/{ext['DOI']}"
    if ext.get("ArXiv"):
        urls["abs"] = f"https://arxiv.org/abs/{ext['ArXiv']}"
    elif p.get("url"):
        urls["abs"] = p["url"]

    return PaperMetadata(
        title=p["title"],
        authors=authors or ["Unknown"],
        year=p.get("year") or 0,
        venue=p.get("venue") or None,
        arxiv_id=ext.get("ArXiv"),
        doi=ext.get("DOI"),
        urls=urls,
    )


@_RETRY
async def search_semantic_scholar(
    query: str, *, limit: int = 5, year_hint: int | None = None,
) -> list[PaperMetadata]:
    """Search S2's /graph/v1/paper/search endpoint."""
    params: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,venue,externalIds,openAccessPdf,url",
    }
    if year_hint:
        # S2 accepts year as a range like "2024-2026"
        params["year"] = f"{year_hint - 1}-{year_hint + 1}"

    async with _client() as client:
        r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    out: list[PaperMetadata] = []
    for paper in data.get("data", []):
        try:
            out.append(_s2_paper_to_meta(paper))
        except (KeyError, ValueError):
            continue  # skip malformed entries
    return out
```

- [ ] **Step 4: Record cassette on first run**

Run: `uv run pytest tests/integration/test_academic_search.py -v --record-mode=once`

Expected: tests pass, `tests/cassettes/test_search_semantic_scholar_baruch_alie.yaml` and `test_search_semantic_scholar_zhang_flpoison.yaml` are created.

Verify: `ls tests/cassettes/`

- [ ] **Step 5: Replay verifies green**

Run: `uv run pytest tests/integration/test_academic_search.py -v`

Expected: tests pass without network (cassettes replayed).

- [ ] **Step 6: Commit**

```bash
git add shared/src/kourai_common/academic_search.py tests/integration/test_academic_search.py tests/cassettes/*.yaml
git commit -m "feat(aletheia-v2): search_semantic_scholar + cassette-replay tests"
```

---

### Task 3.3: arXiv API client + cassette tests

**Files:**
- Modify: `shared/src/kourai_common/academic_search.py` (add functions)
- Modify: `tests/integration/test_academic_search.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_academic_search.py`:

```python
from kourai_common.academic_search import (
    fetch_arxiv_html,
    lookup_arxiv_metadata,
)


@pytest.mark.vcr
async def test_lookup_arxiv_metadata_baruch_alie():
    meta = await lookup_arxiv_metadata("1902.06156")
    assert meta is not None
    assert meta.year == 2019
    assert "baruch" in meta.authors[0].lower()
    assert meta.arxiv_id == "1902.06156"


@pytest.mark.vcr
async def test_fetch_arxiv_html_returns_paper_text():
    text = await fetch_arxiv_html("1902.06156")
    assert text is not None
    # The ALIE abstract mentions "Byzantine" — verify text content
    assert "byzantine" in text.lower()
```

- [ ] **Step 2: Implement arXiv functions**

Append to `shared/src/kourai_common/academic_search.py`:

```python
import xml.etree.ElementTree as ET


_ARXIV_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _arxiv_entry_to_meta(entry: ET.Element) -> PaperMetadata:
    title = (entry.findtext("atom:title", default="", namespaces=_ARXIV_ATOM_NS) or "").strip()
    authors = [
        (e.findtext("atom:name", default="", namespaces=_ARXIV_ATOM_NS) or "").strip()
        for e in entry.findall("atom:author", _ARXIV_ATOM_NS)
    ]
    published = entry.findtext("atom:published", default="", namespaces=_ARXIV_ATOM_NS) or ""
    year = int(published[:4]) if len(published) >= 4 else 0
    link_abs = entry.findtext("atom:id", default="", namespaces=_ARXIV_ATOM_NS) or ""
    arxiv_id = link_abs.rsplit("/", 1)[-1].split("v")[0] if link_abs else None
    urls = {"abs": link_abs} if link_abs else {}
    if arxiv_id:
        urls["pdf"] = f"https://arxiv.org/pdf/{arxiv_id}"
        urls["html"] = f"https://arxiv.org/html/{arxiv_id}"
    return PaperMetadata(
        title=title,
        authors=authors or ["Unknown"],
        year=year,
        urls=urls,
        arxiv_id=arxiv_id,
    )


@_RETRY
async def lookup_arxiv_metadata(arxiv_id: str) -> PaperMetadata | None:
    """Fetch one paper's metadata via arXiv's Atom API."""
    async with _client() as client:
        r = await client.get(
            "http://export.arxiv.org/api/query",
            params={"id_list": arxiv_id, "max_results": 1},
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
    entries = root.findall("atom:entry", _ARXIV_ATOM_NS)
    if not entries:
        return None
    return _arxiv_entry_to_meta(entries[0])


@_RETRY
async def fetch_arxiv_html(arxiv_id: str) -> str | None:
    """Fetch the arXiv HTML5 rendering of a paper (preferred over PDF).

    Available for most submissions since late 2023 via LaTeXML.
    """
    async with _client() as client:
        r = await client.get(f"https://arxiv.org/html/{arxiv_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text
```

- [ ] **Step 3: Record cassettes**

Run: `uv run pytest tests/integration/test_academic_search.py::test_lookup_arxiv_metadata_baruch_alie tests/integration/test_academic_search.py::test_fetch_arxiv_html_returns_paper_text -v --record-mode=once`

- [ ] **Step 4: Commit**

```bash
git add shared/src/kourai_common/academic_search.py tests/integration/test_academic_search.py tests/cassettes/*.yaml
git commit -m "feat(aletheia-v2): arXiv API metadata + HTML5 paper-text client"
```

---

### Task 3.4: OpenAlex client + cassette test + PDF→Markdown fallback

**Files:**
- Modify: `shared/src/kourai_common/academic_search.py`
- Modify: `tests/integration/test_academic_search.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_academic_search.py`:

```python
from kourai_common.academic_search import (
    fetch_paper_pdf_text,
    lookup_openalex_by_doi,
)


@pytest.mark.vcr
async def test_lookup_openalex_pillutla_rfa():
    meta = await lookup_openalex_by_doi("10.1109/TSP.2022.3153135")
    assert meta is not None
    assert meta.year == 2022
    assert "pillutla" in meta.authors[0].lower()
    assert meta.doi == "10.1109/TSP.2022.3153135"


@pytest.mark.vcr
async def test_lookup_openalex_missing_returns_none():
    meta = await lookup_openalex_by_doi("10.0000/nonexistent")
    assert meta is None


@pytest.mark.vcr
async def test_fetch_paper_pdf_via_docling():
    """Fetch the FLPoison PDF and extract its text via docling."""
    text = await fetch_paper_pdf_text("https://arxiv.org/pdf/2502.03801")
    assert text is not None
    # Should mention "Federated Learning" prominently
    assert "federated" in text.lower()
```

- [ ] **Step 2: Implement OpenAlex + PDF helpers**

Append to `shared/src/kourai_common/academic_search.py`:

```python
import io


def _openalex_work_to_meta(w: dict[str, Any]) -> PaperMetadata:
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in w.get("authorships", [])
    ]
    doi_raw = w.get("doi") or None
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
    arxiv_id = None
    if w.get("locations"):
        for loc in w["locations"]:
            src = (loc.get("source") or {}).get("display_name", "") or ""
            if "arxiv" in src.lower() and loc.get("landing_page_url"):
                page = loc["landing_page_url"]
                if "/abs/" in page:
                    arxiv_id = page.rsplit("/abs/", 1)[-1].split("v")[0]
                    break

    urls: dict[str, str] = {}
    if w.get("doi"):
        urls["doi"] = w["doi"]
    pdf = w.get("open_access", {}).get("oa_url")
    if pdf:
        urls["pdf"] = pdf
    if arxiv_id:
        urls.setdefault("abs", f"https://arxiv.org/abs/{arxiv_id}")

    return PaperMetadata(
        title=w.get("title", ""),
        authors=authors or ["Unknown"],
        year=w.get("publication_year") or 0,
        venue=(w.get("primary_location", {}).get("source", {}) or {}).get("display_name"),
        arxiv_id=arxiv_id,
        doi=doi,
        urls=urls,
    )


@_RETRY
async def lookup_openalex_by_doi(doi: str) -> PaperMetadata | None:
    """OpenAlex /works/doi:{doi} lookup.

    Requires API key from openalex.org/signup (30-second registration).
    Set OPENALEX_API_KEY env var.
    """
    api_key = os.environ.get("OPENALEX_API_KEY")
    headers = {"User-Agent": _KOURAI_UA}
    if api_key:
        headers["api_key"] = api_key

    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(15.0)) as client:
        r = await client.get(f"https://api.openalex.org/works/doi:{doi}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return _openalex_work_to_meta(r.json())


@_RETRY
async def fetch_paper_pdf_text(pdf_url: str) -> str | None:
    """Download a PDF and extract its text via Docling (Apache 2.0).

    Async download + sync docling parse offloaded to thread pool.
    """
    import asyncio

    from docling.document_converter import DocumentConverter

    async with _client() as client:
        r = await client.get(pdf_url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        pdf_bytes = r.content

    def _convert() -> str:
        # Docling reads from a file path; write to a NamedTemporaryFile
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name
        try:
            result = DocumentConverter().convert(tmp_path)
            return result.document.export_to_markdown()
        finally:
            os.unlink(tmp_path)

    return await asyncio.to_thread(_convert)
```

- [ ] **Step 3: Record cassettes (PDF cassette will be large)**

Run: `uv run pytest tests/integration/test_academic_search.py::test_lookup_openalex_pillutla_rfa tests/integration/test_academic_search.py::test_lookup_openalex_missing_returns_none tests/integration/test_academic_search.py::test_fetch_paper_pdf_via_docling -v --record-mode=once`

Note: the docling test cassette will store the full PDF response (~1-2 MB) — large but acceptable.

- [ ] **Step 4: Commit + PR**

```bash
git add shared/src/kourai_common/academic_search.py tests/integration/test_academic_search.py tests/cassettes/*.yaml
git commit -m "feat(aletheia-v2): OpenAlex DOI lookup + Docling PDF extraction"
git push -u origin feat/aletheia-v2-pr3-academic-search
gh pr create --title "feat(aletheia-v2): academic_search HTTP layer + cassette tests (PR 3/6)" --body "PR 3 of 6 — direct S2 + arXiv + OpenAlex clients via httpx + tenacity; Docling PDF parsing. Cassette-replay tests for hermetic CI."
gh pr checks --watch
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

## PR 4 — Aletheia agent integration

**Scope:** `verify_and_cite()` + the five tool implementations + `audit_existing_citations()` + end-to-end agent tests with FakeLLM.

### Task 4.1: Branch + FakeLLM fixture

**Files:**
- Create: `tests/integration/conftest_aletheia.py` (or extend existing conftest with the fixture)

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/aletheia-v2-pr4-agent-integration
```

- [ ] **Step 2: Add FakeLLM fixture**

Inspect existing kourai LLM call surface:

Run: `grep -n "def chat\|def chat_with_tools" shared/src/kourai_common/llm.py | head -5`

Add to `tests/integration/conftest.py` (create if absent):

```python
"""Integration-test fixtures, including FakeLLM for deterministic agent tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest


class FakeLLM:
    """Deterministic stand-in for kourai_common.llm.chat / chat_with_tools.

    Scripted responses queued by the test; each call pops the next one.
    Anthropic-guidance pattern (May 2026): mock the LLM, run real tool
    paths, get fast/cheap/deterministic agent tests.
    """

    def __init__(self) -> None:
        self.responses: list[str | dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []

    def queue(self, response: str | dict[str, Any]) -> None:
        self.responses.append(response)

    async def chat(self, _agent: str, messages: list[dict], **kwargs) -> str:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("FakeLLM exhausted (no queued response)")
        nxt = self.responses.pop(0)
        return nxt if isinstance(nxt, str) else str(nxt)

    async def chat_with_tools(
        self,
        agent: str,
        messages: list[dict],
        tools: list[dict],
        tool_handlers: dict[str, Callable],
        **kwargs,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Sequential tool-call playback: each queued response is either
        a string (final answer) or a dict (tool call with name + args).
        """
        log: list[dict[str, Any]] = []
        while self.responses:
            nxt = self.responses.pop(0)
            if isinstance(nxt, str):
                return nxt, log
            tool_name = nxt["tool"]
            tool_args = nxt.get("args", {})
            result = await tool_handlers[tool_name](**tool_args)
            log.append({"tool": tool_name, "args": tool_args, "result": result})
        raise AssertionError("FakeLLM exhausted before producing a final response")


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/conftest.py
git commit -m "feat(aletheia-v2): FakeLLM fixture for deterministic agent tests"
```

---

### Task 4.2: extract_claim + search_papers tools

**Files:**
- Modify: `agents/aletheia/agent.py` (add functions)
- Create: `tests/integration/test_aletheia_verify_cite.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_aletheia_verify_cite.py`:

```python
"""End-to-end tests for Aletheia's verify_and_cite agent loop."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

from kourai_common.citation_artifacts import PaperMetadata
from agents.aletheia.agent import (
    aletheia_extract_claim,
    aletheia_search_papers,
)


@pytest.mark.asyncio
async def test_extract_claim_strips_to_assertion(fake_llm):
    fake_llm.queue("ALIE is a defense-evading Byzantine attack")
    result = await aletheia_extract_claim(
        "The ALIE attack by Baruch is defense-evading...",
        llm=fake_llm,
    )
    assert "alie" in result.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_search_papers_returns_candidates():
    candidates = await aletheia_search_papers(
        "A Little Is Enough Circumventing Defenses Distributed Learning",
        year_hint=2019,
        limit=3,
    )
    assert len(candidates) >= 1
    assert "baruch" in candidates[0].authors[0].lower()
```

- [ ] **Step 2: Implement extract_claim + search_papers in aletheia/agent.py**

Append to `agents/aletheia/agent.py`:

```python
from kourai_common.academic_search import search_semantic_scholar
from kourai_common.citation_artifacts import PaperMetadata


async def aletheia_extract_claim(
    text: str,
    *,
    llm=None,
) -> str:
    """Distill the assertion in `text` that needs grounding.

    `llm` defaults to kourai_common.llm.chat; pass a FakeLLM for tests.
    """
    if llm is None:
        from kourai_common.llm import chat as default_chat
        chat_fn = default_chat
    else:
        chat_fn = llm.chat

    messages = [
        {
            "role": "system",
            "content": (
                "You are Aletheia's Claim Extractor. Given a passage that "
                "needs a citation, return ONE short sentence stating the "
                "specific assertion the citation must support. No markup, "
                "no quotation, just the assertion."
            ),
        },
        {"role": "user", "content": text},
    ]
    return (await chat_fn("aletheia", messages, temperature=0.1, max_tokens=120)).strip()


async def aletheia_search_papers(
    query: str,
    *,
    year_hint: int | None = None,
    limit: int = 5,
) -> list[PaperMetadata]:
    """Thin wrapper around academic_search.search_semantic_scholar."""
    return await search_semantic_scholar(query, limit=limit, year_hint=year_hint)
```

- [ ] **Step 3: Run to verify**

Run: `uv run pytest tests/integration/test_aletheia_verify_cite.py -v -k "extract_claim or search_papers"`

Expected: tests pass (extract_claim uses FakeLLM; search_papers uses cassette from PR 3).

- [ ] **Step 4: Commit**

```bash
git add agents/aletheia/agent.py tests/integration/test_aletheia_verify_cite.py
git commit -m "feat(aletheia-v2): extract_claim + search_papers tools"
```

---

### Task 4.3: fetch_paper_text + match_evidence + triangulate tools

**Files:**
- Modify: `agents/aletheia/agent.py`
- Modify: `tests/integration/test_aletheia_verify_cite.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_aletheia_verify_cite.py`:

```python
import re

from kourai_common.triangulate import triangulate
from agents.aletheia.agent import (
    aletheia_fetch_paper_text,
    aletheia_match_evidence,
)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_fetch_paper_text_arxiv_html_path():
    text = await aletheia_fetch_paper_text(arxiv_id="1902.06156")
    assert text is not None
    assert "byzantine" in text.lower()


def test_match_evidence_filters_to_verbatim_substrings():
    paper_text = (
        "We propose a novel attack: A Little Is Enough.\n"
        "It perturbs honest updates within statistical bounds."
    )
    candidate_excerpts = [
        ("We propose a novel attack: A Little Is Enough.", "Section 1"),
        ("This is not in the paper at all.", "Fabricated"),
        ("perturbs honest updates within statistical bounds", "Section 2"),
    ]
    verified = aletheia_match_evidence(
        candidate_excerpts=candidate_excerpts,
        paper_text=paper_text,
    )
    # The fabricated quote is dropped; the real ones pass
    assert len(verified) == 2
    assert all("fabricated" not in q.lower() for q, _ in verified)


def test_match_evidence_whitespace_tolerant():
    paper_text = "Federated\n  learning\nis hard."
    candidate_excerpts = [
        ("Federated learning is hard.", "Abstract"),
    ]
    verified = aletheia_match_evidence(
        candidate_excerpts=candidate_excerpts,
        paper_text=paper_text,
    )
    # Whitespace-normalized match should accept the candidate despite
    # the line breaks in the source.
    assert len(verified) == 1
```

- [ ] **Step 2: Implement the tools**

Append to `agents/aletheia/agent.py`:

```python
import re
from collections.abc import Sequence

from kourai_common.academic_search import (
    fetch_arxiv_html,
    fetch_paper_pdf_text,
)


async def aletheia_fetch_paper_text(
    *,
    arxiv_id: str | None = None,
    pdf_url: str | None = None,
) -> str | None:
    """Fetch full paper text. arXiv HTML5 preferred; PDF fallback via Docling."""
    if arxiv_id:
        text = await fetch_arxiv_html(arxiv_id)
        if text:
            return text
    if pdf_url:
        return await fetch_paper_pdf_text(pdf_url)
    return None


_WS_RE = re.compile(r"\s+")


def _norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def aletheia_match_evidence(
    *,
    candidate_excerpts: Sequence[tuple[str, str]],
    paper_text: str,
) -> list[tuple[str, str]]:
    """Filter candidate excerpts to verbatim substrings (whitespace-tolerant).

    `candidate_excerpts` come from an LLM extraction step elsewhere; this
    function is purely mechanical (no LLM call) — substring check on the
    whitespace-normalized form.
    """
    normalized_paper = _norm_ws(paper_text)
    return [
        (quote, ref)
        for quote, ref in candidate_excerpts
        if _norm_ws(quote) in normalized_paper
    ]
```

- [ ] **Step 3: Run to verify**

Run: `uv run pytest tests/integration/test_aletheia_verify_cite.py -v -k "fetch_paper or match_evidence"`

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add agents/aletheia/agent.py tests/integration/test_aletheia_verify_cite.py
git commit -m "feat(aletheia-v2): fetch_paper_text + match_evidence (whitespace-tolerant verbatim check)"
```

---

### Task 4.4: verify_and_cite() top-level orchestrator + end-to-end tests

**Files:**
- Modify: `agents/aletheia/agent.py`
- Modify: `tests/integration/test_aletheia_verify_cite.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_aletheia_verify_cite.py`:

```python
from pathlib import Path

from kourai_common.citation_artifacts import ConflictReport, PaperMetadata
from agents.aletheia.agent import verify_and_cite


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_verify_and_cite_happy_path(tmp_path: Path, fake_llm):
    # Script the LLM: extract claim, pick the first S2 candidate, return excerpts
    fake_llm.queue("ALIE perturbs within statistical envelope (Baruch 2019)")
    fake_llm.queue("0")  # "pick first candidate by index"
    fake_llm.queue(
        '[{"quote": "We propose a novel attack", "ref": "Abstract"}]'
    )

    cite, artifact_or_conflict = await verify_and_cite(
        claim="ALIE perturbs honest updates within statistical bounds",
        project_root=tmp_path,
        llm=fake_llm,
    )

    assert cite is not None
    assert isinstance(artifact_or_conflict, Path)
    assert artifact_or_conflict.exists()
    assert "baruch" in artifact_or_conflict.name.lower()


@pytest.mark.asyncio
async def test_verify_and_cite_triangulation_reject_returns_conflict(
    tmp_path: Path,
    fake_llm,
    monkeypatch,
):
    """Force a first-author mismatch and verify the citation is refused."""
    fake_llm.queue("ALIE perturbation")
    fake_llm.queue("0")
    fake_llm.queue('[{"quote": "We propose ALIE", "ref": "Abstract"}]')

    async def fake_s2(*args, **kwargs):
        return [PaperMetadata(
            title="A Little Is Enough",
            authors=["Wrong Author"],  # deliberate mismatch
            year=2019,
            urls={"abs": "https://arxiv.org/abs/1902.06156"},
            arxiv_id="1902.06156",
        )]

    async def fake_openalex(doi):
        return PaperMetadata(
            title="A Little Is Enough",
            authors=["Gilad Baruch"],
            year=2019,
            urls={"abs": "https://arxiv.org/abs/1902.06156"},
            arxiv_id="1902.06156",
            doi=doi,
        )

    async def fake_arxiv_meta(arxiv_id):
        return PaperMetadata(
            title="A Little Is Enough",
            authors=["Gilad Baruch"],  # OpenAlex/arxiv agree on Baruch
            year=2019,
            urls={"abs": f"https://arxiv.org/abs/{arxiv_id}"},
            arxiv_id=arxiv_id,
        )

    async def fake_html(arxiv_id):
        return "We propose ALIE: A Little Is Enough"

    monkeypatch.setattr("agents.aletheia.agent.aletheia_search_papers", fake_s2)
    monkeypatch.setattr("agents.aletheia.agent.lookup_openalex_by_doi", fake_openalex)
    monkeypatch.setattr("agents.aletheia.agent.lookup_arxiv_metadata", fake_arxiv_meta)
    monkeypatch.setattr("agents.aletheia.agent.aletheia_fetch_paper_text", lambda **kw: fake_html(kw.get("arxiv_id", "")))

    cite, conflict = await verify_and_cite(
        claim="ALIE perturbs honest updates",
        project_root=tmp_path,
        llm=fake_llm,
    )
    assert cite is None
    assert isinstance(conflict, ConflictReport)
    assert conflict.kind == "triangulation_mismatch"
    assert any(f[0] == "first_author_surname" for f in conflict.field_disagreements)
```

- [ ] **Step 2: Implement verify_and_cite()**

Append to `agents/aletheia/agent.py`:

```python
import json
from pathlib import Path

from kourai_common.academic_search import (
    lookup_arxiv_metadata,
    lookup_openalex_by_doi,
)
from kourai_common.citation_artifacts import (
    ConflictReport,
    PaperMetadata,
    TriangulationResult,
    write_citation_artifact,
)
from kourai_common.triangulate import triangulate


async def _pick_candidate_via_llm(
    candidates: list[PaperMetadata],
    claim: str,
    *,
    llm,
) -> int | None:
    """Ask the LLM to pick the index of the best-matching candidate."""
    if not candidates:
        return None
    summary = "\n".join(
        f"{i}: {c.title} ({c.authors[0]}, {c.year})"
        for i, c in enumerate(candidates)
    )
    chat_fn = llm.chat if llm else __import__("kourai_common.llm", fromlist=["chat"]).chat
    response = await chat_fn(
        "aletheia",
        [
            {"role": "system", "content": "Pick the candidate index (0-based) that best supports the claim. Reply with just the integer, or 'none' if no match."},
            {"role": "user", "content": f"Claim: {claim}\n\nCandidates:\n{summary}"},
        ],
        temperature=0.0,
        max_tokens=10,
    )
    response = response.strip().lower()
    if response == "none":
        return None
    try:
        idx = int(response)
        if 0 <= idx < len(candidates):
            return idx
    except ValueError:
        pass
    return None


async def _extract_excerpts_via_llm(
    claim: str,
    paper_text: str,
    *,
    llm,
) -> list[tuple[str, str]]:
    """Ask the LLM for candidate verbatim excerpts. They'll be substring-verified."""
    # Cap paper text at ~30K chars to fit in context
    truncated = paper_text[:30000]
    chat_fn = llm.chat if llm else __import__("kourai_common.llm", fromlist=["chat"]).chat
    response = await chat_fn(
        "aletheia",
        [
            {
                "role": "system",
                "content": (
                    "Find verbatim excerpts in the paper that support the claim. "
                    "Reply with a JSON list of objects with keys 'quote' (exact substring) and 'ref' (e.g. 'Abstract', 'Section 3.1'). "
                    "Each quote MUST be copy-pasted verbatim from the paper text. Return empty list if no excerpts match."
                ),
            },
            {"role": "user", "content": f"Claim: {claim}\n\nPaper text:\n{truncated}"},
        ],
        temperature=0.1,
        max_tokens=500,
    )
    try:
        items = json.loads(response)
        return [(item["quote"], item["ref"]) for item in items if "quote" in item and "ref" in item]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


async def verify_and_cite(
    *,
    claim: str,
    project_root: Path,
    hint: str | None = None,
    llm=None,
    override: bool = False,
    override_reason: str | None = None,
) -> tuple[str | None, Path | ConflictReport]:
    """Specialized academic-claim verifier — the new Aletheia v2 entrypoint.

    Returns (citation_string, artifact_path) on success.
    Returns (None, ConflictReport) on any verification failure.
    """
    # 1. Distill the claim
    refined_claim = await aletheia_extract_claim(claim, llm=llm)
    query = hint or refined_claim

    # 2. Retrieve candidates
    candidates = await aletheia_search_papers(query, limit=5)
    if not candidates:
        return None, ConflictReport(
            kind="no_candidates",
            detail=f"Semantic Scholar returned no results for query: {query!r}",
        )

    # 3. LLM picks best candidate
    pick = await _pick_candidate_via_llm(candidates, refined_claim, llm=llm)
    if pick is None:
        return None, ConflictReport(
            kind="no_candidates",
            detail="LLM judged no candidate as a match for the claim.",
        )
    primary = candidates[pick]

    # 4. Fetch full paper text
    paper_text = await aletheia_fetch_paper_text(
        arxiv_id=primary.arxiv_id,
        pdf_url=primary.urls.get("pdf"),
    )
    if not paper_text:
        return None, ConflictReport(
            kind="text_unavailable",
            detail=f"Could not fetch paper text for {primary.arxiv_id or primary.doi}.",
        )

    # 5. Extract + verify verbatim excerpts
    candidate_excerpts = await _extract_excerpts_via_llm(refined_claim, paper_text, llm=llm)
    verified_excerpts = aletheia_match_evidence(
        candidate_excerpts=candidate_excerpts,
        paper_text=paper_text,
    )
    if not verified_excerpts and not override:
        return None, ConflictReport(
            kind="no_supporting_excerpts",
            primary_meta_summary=f"{primary.authors[0]}, {primary.year}",
            detail="No LLM-proposed excerpt verified as a verbatim substring of the paper text.",
        )

    # 6. Triangulation gate
    secondary: PaperMetadata | None = None
    secondary_source: str | None = None
    if primary.doi:
        secondary = await lookup_openalex_by_doi(primary.doi)
        secondary_source = "openalex" if secondary else None
    if secondary is None and primary.arxiv_id:
        secondary = await lookup_arxiv_metadata(primary.arxiv_id)
        secondary_source = "arxiv" if secondary else None

    triang_result, triang_conflict = triangulate(
        primary, secondary,
        primary_source="semantic_scholar",
        secondary_source=secondary_source,
    )
    if triang_conflict is not None and not override:
        return None, triang_conflict

    if triang_result is None:
        # Should not happen unless triangulate has a bug; defensive.
        triang_result = TriangulationResult(
            verified=True,
            primary_source="semantic_scholar",
            secondary_source=None,
            decisive_fields_checked=[],
            decisive_fields_agreed=True,
            single_source_verified=True,
            notes=["triangulate_returned_neither_branch"],
        )

    # 7. Write artifact
    abstract_text = paper_text[:1500]  # crude abstract fallback if no separate one
    artifact_path = write_citation_artifact(
        meta=primary,
        claim=refined_claim,
        excerpts=verified_excerpts,
        triangulation=triang_result,
        abstract=abstract_text,
        project_root=project_root,
        human_overridden=override,
        override_reason=override_reason if override else None,
    )

    citation = (
        f"{primary.authors[0]} et al., *{primary.title}* "
        f"({'arXiv:' + primary.arxiv_id if primary.arxiv_id else 'DOI ' + (primary.doi or '?')}, "
        f"{primary.year})"
    )
    return citation, artifact_path
```

- [ ] **Step 3: Run end-to-end tests**

Run: `uv run pytest tests/integration/test_aletheia_verify_cite.py -v`

Expected: all pass (happy path + triangulation reject + fakeLLM-driven extraction).

- [ ] **Step 4: Commit**

```bash
git add agents/aletheia/agent.py tests/integration/test_aletheia_verify_cite.py
git commit -m "feat(aletheia-v2): verify_and_cite() orchestrator + end-to-end agent tests"
```

---

### Task 4.5: audit_existing_citations() — drift detection

**Files:**
- Modify: `agents/aletheia/agent.py`
- Modify: `tests/integration/test_aletheia_verify_cite.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_aletheia_verify_cite.py`:

```python
from agents.aletheia.agent import audit_existing_citations


@pytest.mark.asyncio
async def test_audit_existing_citations_detects_changed_first_author(
    tmp_path: Path,
    monkeypatch,
):
    """Artifact says first author = X; OpenAlex now says first author = Y."""
    # Write an artifact claiming Zhang as first author
    from kourai_common.citation_artifacts import write_citation_artifact

    meta = PaperMetadata(
        title="SoK: Benchmarking",
        authors=["Heyi Zhang"],
        year=2025,
        urls={"abs": "https://arxiv.org/abs/2502.03801"},
        arxiv_id="2502.03801",
        doi="10.1234/x.5",
    )
    triangulation = TriangulationResult(
        verified=True,
        primary_source="semantic_scholar",
        secondary_source="openalex",
        decisive_fields_checked=["title", "first_author_surname", "year"],
        decisive_fields_agreed=True,
    )
    write_citation_artifact(
        meta=meta,
        claim="test",
        excerpts=[],
        triangulation=triangulation,
        abstract="test abstract",
        project_root=tmp_path,
    )

    # Stub OpenAlex to now return a DIFFERENT first author for the same DOI
    async def fake_openalex(doi):
        return PaperMetadata(
            title="SoK: Benchmarking",
            authors=["Different Author"],
            year=2025,
            urls={"abs": "https://arxiv.org/abs/2502.03801"},
            arxiv_id="2502.03801",
            doi=doi,
        )

    monkeypatch.setattr("agents.aletheia.agent.lookup_openalex_by_doi", fake_openalex)

    drift = await audit_existing_citations(project_root=tmp_path)
    assert len(drift) == 1
    assert "first_author" in drift[0].detail.lower()
```

- [ ] **Step 2: Implement audit_existing_citations()**

Append to `agents/aletheia/agent.py`:

```python
from kourai_common.citation_artifacts import read_citation_artifact


async def audit_existing_citations(
    *,
    project_root: Path,
) -> list[ConflictReport]:
    """Re-run triangulation on every artifact in docs/citations/.

    Returns a list of ConflictReports for any artifact whose current
    upstream metadata disagrees with what was recorded at write-time.
    Empty list = no drift.
    """
    citations_dir = project_root / "docs" / "citations"
    if not citations_dir.exists():
        return []

    drift: list[ConflictReport] = []
    for path in sorted(citations_dir.glob("*.md")):
        try:
            stored_meta, _ = read_citation_artifact(path)
        except (ValueError, KeyError):
            drift.append(ConflictReport(
                kind="text_unavailable",
                detail=f"{path.name}: artifact file malformed",
            ))
            continue

        # Fetch current upstream metadata
        current: PaperMetadata | None = None
        if stored_meta.doi:
            current = await lookup_openalex_by_doi(stored_meta.doi)
        if current is None and stored_meta.arxiv_id:
            current = await lookup_arxiv_metadata(stored_meta.arxiv_id)
        if current is None:
            drift.append(ConflictReport(
                kind="text_unavailable",
                detail=f"{path.name}: no upstream source resolves the stored identifier",
            ))
            continue

        # Re-run the triangulation gate
        _, conflict = triangulate(
            stored_meta, current,
            primary_source="artifact",
            secondary_source="upstream",
        )
        if conflict is not None:
            conflict.detail = f"{path.name}: {conflict.detail or ''}".strip()
            drift.append(conflict)

    return drift
```

- [ ] **Step 3: Run test**

Run: `uv run pytest tests/integration/test_aletheia_verify_cite.py::test_audit_existing_citations_detects_changed_first_author -v`

Expected: PASS.

- [ ] **Step 4: Commit + PR**

```bash
git add agents/aletheia/agent.py tests/integration/test_aletheia_verify_cite.py
git commit -m "feat(aletheia-v2): audit_existing_citations() scheduled-drift detection"
git push -u origin feat/aletheia-v2-pr4-agent-integration
gh pr create --title "feat(aletheia-v2): verify_and_cite() + audit_existing_citations() (PR 4/6)" --body "PR 4 of 6 — Aletheia gains the verify_and_cite ReAct loop + the scheduled audit pass."
gh pr checks --watch
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

### Task 4.6: Nightly API-contract tests

**Files:**
- Create: `tests/nightly/test_api_contracts.py`

- [ ] **Step 1: Branch (small follow-up)**

```bash
git checkout -b feat/aletheia-v2-pr4b-nightly-contracts
```

- [ ] **Step 2: Write the tests**

Create `tests/nightly/test_api_contracts.py`:

```python
"""Nightly: one real API call per source to detect upstream schema drift.

Run with: pytest tests/nightly --run-nightly
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.nightly

from kourai_common.academic_search import (
    lookup_arxiv_metadata,
    lookup_openalex_by_doi,
    search_semantic_scholar,
)


@pytest.mark.asyncio
async def test_s2_api_contract():
    """S2 still returns title/authors/year for a known paper."""
    candidates = await search_semantic_scholar("FedAvg federated learning", limit=1)
    assert len(candidates) >= 1
    assert candidates[0].title
    assert candidates[0].authors
    assert 2010 <= candidates[0].year <= 2030


@pytest.mark.asyncio
async def test_openalex_api_contract():
    """OpenAlex DOI lookup still works."""
    meta = await lookup_openalex_by_doi("10.1109/TSP.2022.3153135")
    assert meta is not None
    assert meta.year == 2022
    assert "pillutla" in meta.authors[0].lower()


@pytest.mark.asyncio
async def test_arxiv_api_contract():
    """arXiv API still returns metadata for a known paper."""
    meta = await lookup_arxiv_metadata("1902.06156")
    assert meta is not None
    assert meta.year == 2019
    assert "baruch" in meta.authors[0].lower()
```

- [ ] **Step 3: Wire into existing nightly workflow**

Check if `.github/workflows/nightly.yml` exists in kourai-khryseai:

Run: `cat .github/workflows/nightly.yml 2>/dev/null | head -30`

If exists, add a step that runs `tests/nightly/test_api_contracts.py`. If not, that's a separate workflow-creation task — defer to PR 5 wiring.

- [ ] **Step 4: Commit + PR**

```bash
git add tests/nightly/test_api_contracts.py
git commit -m "feat(aletheia-v2): nightly API-contract drift tests"
git push -u origin feat/aletheia-v2-pr4b-nightly-contracts
gh pr create --title "feat(aletheia-v2): nightly API-contract tests" --body "Tiny follow-up to PR 4: 3 real API calls per night to detect upstream schema drift."
gh pr checks --watch
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

## PR 5 — Mechanical CI check (check_citations.py)

**Scope:** No-LLM filesystem-walker that verifies every `# research:` / `[^cite]` link in the codebase resolves to an artifact file. Pre-commit + CI integration.

### Task 5.1: Branch + check_citations.py + tests

**Files:**
- Create: `scripts/check_citations.py`
- Create: `tests/unit/test_check_citations.py`

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/aletheia-v2-pr5-citation-check
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_check_citations.py`:

```python
"""Tests for scripts/check_citations.py — mechanical CI gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_citations import (
    find_citation_links,
    check_project,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_find_citation_links_in_python(tmp_path: Path):
    src = _write(tmp_path / "foo.py", """
# research(2026-05): Baruch et al. ALIE perturbation
# see docs/citations/1902.06156-baruch-alie.md
def alie():
    pass
""".strip())
    links = list(find_citation_links([src]))
    assert ("docs/citations/1902.06156-baruch-alie.md", src) in [(p, s) for p, s in links]


def test_find_citation_links_in_markdown(tmp_path: Path):
    src = _write(tmp_path / "README.md", """
ALIE [Baruch et al. 2019][^alie] perturbs honest updates.

[^alie]: See [docs/citations/1902.06156-baruch-alie.md] for the verified source.
""".strip())
    links = list(find_citation_links([src]))
    assert ("docs/citations/1902.06156-baruch-alie.md", src) in [(p, s) for p, s in links]


def test_check_project_passes_when_artifact_exists(tmp_path: Path):
    _write(tmp_path / "src/foo.py", "# see docs/citations/1902.06156-baruch-alie.md\n")
    _write(tmp_path / "docs/citations/1902.06156-baruch-alie.md", "---\ntitle: ALIE\n---\n")
    rc, errors = check_project(tmp_path)
    assert rc == 0
    assert errors == []


def test_check_project_fails_when_artifact_missing(tmp_path: Path):
    _write(tmp_path / "src/foo.py", "# see docs/citations/missing-paper.md\n")
    rc, errors = check_project(tmp_path)
    assert rc == 1
    assert len(errors) == 1
    assert "missing-paper.md" in errors[0]


def test_check_project_validates_artifact_frontmatter_yaml(tmp_path: Path):
    _write(tmp_path / "src/foo.py", "# see docs/citations/bad.md\n")
    _write(tmp_path / "docs/citations/bad.md", "not yaml at all")
    rc, errors = check_project(tmp_path)
    assert rc == 1
    assert any("frontmatter" in e.lower() or "yaml" in e.lower() for e in errors)


def test_check_project_flags_stale_verified_at(tmp_path: Path):
    """Artifact with verified_at older than 365 days should be flagged."""
    _write(tmp_path / "src/foo.py", "# see docs/citations/stale.md\n")
    _write(tmp_path / "docs/citations/stale.md", """---
title: Stale Paper
authors: [Stale Author]
year: 2020
urls:
  abs: https://example.com
arxiv_id: "0000.0001"
doi: null
sources_consulted: [semantic_scholar]
triangulation:
  primary_source: semantic_scholar
  secondary_source: openalex
  decisive_fields_agreed: true
  decisive_fields_checked: []
  notes: []
single_source_verified: false
verified_by: aletheia
verified_at: "2020-01-01T00:00:00+00:00"
verification_version: "1.0"
human_overridden: false
override_reason: null
claim_supported: stale
---
""")
    rc, errors = check_project(tmp_path)
    assert rc == 1
    assert any("stale" in e.lower() for e in errors)
```

- [ ] **Step 3: Implement check_citations.py**

Create `scripts/check_citations.py`:

```python
"""Mechanical CI check: every citation link resolves to an artifact file.

Runs in <1s with no LLM call. Pre-commit hook + CI gate.

Usage:
    uv run python scripts/check_citations.py [project_root]
    # Exit 0 = all citations resolved + artifacts well-formed
    # Exit 1 = at least one link missing or artifact malformed
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import yaml

# Citation-link patterns we recognize
_PY_CITE_RE = re.compile(r"docs/citations/([a-zA-Z0-9._-]+\.md)")
_MD_FOOTNOTE_RE = re.compile(r"\[docs/citations/([a-zA-Z0-9._-]+\.md)\]")

_REQUIRED_FRONTMATTER_KEYS = {
    "title", "authors", "year", "urls", "verified_at", "verified_by", "claim_supported",
}

_STALE_DAYS = 365


def _iter_source_files(root: Path) -> Iterator[Path]:
    """Yield .py, .md, .yml, .yaml files under root (excluding .venv, node_modules, build)."""
    exclude_dirs = {".venv", "node_modules", "build", "dist", ".git", "__pycache__", "site"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if path.suffix in {".py", ".md", ".yml", ".yaml"}:
            yield path


def find_citation_links(files: Iterable[Path]) -> Iterator[tuple[str, Path]]:
    """Yield (artifact_filename, source_file) for each citation link found."""
    for src in files:
        try:
            text = src.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for m in _PY_CITE_RE.finditer(text):
            yield m.group(1), src
        for m in _MD_FOOTNOTE_RE.finditer(text):
            yield m.group(1), src


def _validate_frontmatter(artifact_path: Path) -> list[str]:
    """Return a list of error strings for the artifact, or empty if OK."""
    errors: list[str] = []
    try:
        text = artifact_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError) as e:
        return [f"{artifact_path}: read error: {e}"]

    if not text.startswith("---\n"):
        return [f"{artifact_path}: missing YAML frontmatter delimiter"]
    end = text.find("\n---\n", 4)
    if end == -1:
        return [f"{artifact_path}: unterminated YAML frontmatter"]
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError as e:
        return [f"{artifact_path}: malformed YAML frontmatter: {e}"]
    if not isinstance(fm, dict):
        return [f"{artifact_path}: frontmatter is not a mapping"]

    missing = _REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
    if missing:
        errors.append(f"{artifact_path}: missing required keys: {sorted(missing)}")

    # Stale verified_at check
    verified_at = fm.get("verified_at")
    if verified_at:
        try:
            ts = dt.datetime.fromisoformat(verified_at)
            age = dt.datetime.now(dt.UTC) - ts
            if age.days > _STALE_DAYS:
                errors.append(
                    f"{artifact_path}: verified_at is stale ({age.days} days > {_STALE_DAYS}); re-run aletheia.verify_and_cite"
                )
        except (TypeError, ValueError) as e:
            errors.append(f"{artifact_path}: verified_at not ISO-8601: {e}")

    return errors


def check_project(project_root: Path) -> tuple[int, list[str]]:
    """Walk project_root, verify all citation links resolve and artifacts are well-formed."""
    errors: list[str] = []
    seen_artifacts: set[Path] = set()

    for artifact_name, source in find_citation_links(_iter_source_files(project_root)):
        artifact_path = project_root / "docs" / "citations" / artifact_name
        if not artifact_path.exists():
            errors.append(
                f"{source}: cites missing artifact docs/citations/{artifact_name}"
            )
            continue
        if artifact_path not in seen_artifacts:
            errors.extend(_validate_frontmatter(artifact_path))
            seen_artifacts.add(artifact_path)

    return (1 if errors else 0, errors)


def main(argv: list[str]) -> int:
    project_root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    rc, errors = check_project(project_root)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if rc == 0:
        print(f"OK: all citation links in {project_root} resolve to well-formed artifacts.")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_check_citations.py -v`

Expected: 6 passed.

- [ ] **Step 5: Smoke run on kourai itself**

Run: `uv run python scripts/check_citations.py .`

Expected: `OK: all citation links in . resolve to well-formed artifacts.` (kourai has no citation links yet, so trivially OK).

- [ ] **Step 6: Commit**

```bash
git add scripts/check_citations.py tests/unit/test_check_citations.py
git commit -m "feat(aletheia-v2): scripts/check_citations.py mechanical CI gate"
```

---

### Task 5.2: Wire into pre-commit + CI workflow

**Files:**
- Modify (or create): `.pre-commit-config.yaml`
- Modify (or create): `.github/workflows/check-citations.yml`

- [ ] **Step 1: Inspect current pre-commit + CI setup**

Run: `cat .pre-commit-config.yaml 2>/dev/null | head -30 && ls .github/workflows/`

- [ ] **Step 2: Add pre-commit hook**

If `.pre-commit-config.yaml` exists, add to its `repos:` list:

```yaml
- repo: local
  hooks:
    - id: check-citations
      name: check-citations
      entry: uv run python scripts/check_citations.py
      language: system
      pass_filenames: false
      always_run: true
      stages: [pre-commit]
```

If it doesn't exist, create it:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-citations
        name: check-citations
        entry: uv run python scripts/check_citations.py
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

- [ ] **Step 3: Add CI workflow**

Create `.github/workflows/check-citations.yml`:

```yaml
name: check-citations

on:
  pull_request:
    paths:
      - "**/*.py"
      - "**/*.md"
      - "docs/citations/**"
      - "scripts/check_citations.py"
      - ".github/workflows/check-citations.yml"
  push:
    branches: [main]

jobs:
  check-citations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6.0.2
      - uses: astral-sh/setup-uv@v8.1.0
        with:
          enable-cache: true
      - name: Install minimal deps (pyyaml)
        run: uv sync --no-install-project
      - name: Run check_citations.py
        run: uv run python scripts/check_citations.py .
```

- [ ] **Step 4: Test the pre-commit hook locally**

Run: `pre-commit run check-citations --all-files` (if pre-commit is installed)

Or manually: `uv run python scripts/check_citations.py .`

Expected: `OK: all citation links in . resolve to well-formed artifacts.`

- [ ] **Step 5: Commit + PR**

```bash
git add .pre-commit-config.yaml .github/workflows/check-citations.yml
git commit -m "feat(aletheia-v2): wire check_citations.py into pre-commit + CI"
git push -u origin feat/aletheia-v2-pr5-citation-check
gh pr create --title "feat(aletheia-v2): mechanical citation check + CI wiring (PR 5/6)" --body "PR 5 of 6 — scripts/check_citations.py + pre-commit hook + GitHub Actions workflow. No LLM, <1s runtime."
gh pr checks --watch
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

## PR 6 — Documentation

**Scope:** User-facing documentation for the new capability. Architecture overview + agent-page entry + nav wiring.

### Task 6.1: Write docs/agents/aletheia.md

**Files:**
- Create or extend: `docs/agents/aletheia.md`
- Modify: `docs/agents/specialists.md` (add link to new aletheia.md)

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/aletheia-v2-pr6-docs
```

- [ ] **Step 2: Write the documentation**

Create `docs/agents/aletheia.md`:

```markdown
# Aletheia — research validator + citation enforcer

Aletheia is the spirit of truth in the Kourai pantheon. She validates that
technical claims are grounded in real research and that citations point at
real papers with accurate metadata.

## Two surfaces

### Generic claim validation (v1, existing)

`aletheia.validate_research(text)` runs a regex pre-screen for algorithmic
claims (Big-O, "proven", "optimal", "industry standard") and uses Brave
Search to surface evidence. Returns a per-claim verdict block.

Use this for: industry-standard references, RFCs, generic web claims.

### Academic citation verification (v2, this page's focus)

`aletheia.verify_and_cite(claim, project_root=...)` runs a 5-tool agentic
loop over Semantic Scholar + arXiv + OpenAlex, picks a candidate paper,
verifies the claim is supported by verbatim excerpts in the paper text,
cross-checks the metadata against a second source, and writes an artifact
file at `docs/citations/{slug}.md` that the developer can manually audit.

Returns `(citation_string, artifact_path)` on success, or
`(None, ConflictReport)` if any verification step fails.

Use this for: academic paper citations in code comments, READMEs, PR bodies,
LinkedIn captions — anywhere a hallucinated citation would damage trust.

## Why this exists

LLMs hallucinate academic citations at empirically observed rates of
14-95% (CiteVerifier benchmark, May 2026). NeurIPS 2025 had ~100 fabricated
citations across 53 published papers. The 5 errors caught in vFL PR #36's
manual audit are the same failure mode at smaller scale.

The full design rationale lives in
[2026-05-23-aletheia-v2-citation-verification-design.md](../architecture/2026-05-23-aletheia-v2-citation-verification-design.md).

## How to use

### From Python

```python
from agents.aletheia.agent import verify_and_cite

citation, artifact_or_conflict = await verify_and_cite(
    claim="ALIE attack perturbs honest updates within a statistical envelope",
    project_root=Path("/path/to/my/project"),
)

if citation is None:
    # artifact_or_conflict is a ConflictReport — inspect it
    print(f"Refused: {artifact_or_conflict.kind}: {artifact_or_conflict.detail}")
else:
    # artifact_or_conflict is the Path to the written artifact file
    print(f"Citation: {citation}")
    print(f"Artifact: {artifact_or_conflict}")
```

### From code comments

After running `verify_and_cite`, link the artifact in your code:

```python
# research(2026-05): Baruch et al. ALIE perturbation
# see docs/citations/1902.06156-baruch-alie.md
def alie_attack(...):
    ...
```

### From Markdown

```markdown
ALIE [Baruch et al. 2019][^alie] perturbs honestly-trained updates.

[^alie]: See [docs/citations/1902.06156-baruch-alie.md] for the verified source.
```

The `scripts/check_citations.py` CI gate verifies every link resolves to a
well-formed artifact (pre-commit + CI on every PR).

## Anti-hallucination guarantees

Mechanical (deterministic, code-verifiable):

1. **Identity provenance** — `title`, `authors`, `year`, `doi`, `arxiv_id` in
   the artifact YAML come VERBATIM from API JSON. The LLM is not in the call
   path for these fields.
2. **Triangulation gate** — `verify_and_cite()` returns `(None, ConflictReport)`
   if the secondary source (OpenAlex or arXiv) disagrees on any decisive
   field (DOI, arxiv_id, title fuzzy-match, first-author surname, year).
3. **Verbatim-excerpt check** — every quote in the artifact body is verified
   as a whitespace-normalized substring of the parsed paper text.
4. **Artifact-file existence** — `scripts/check_citations.py` verifies every
   cite link resolves to an artifact file (pre-commit + CI).
5. **Re-verifiability** — `audit_existing_citations(project_root)` re-runs
   the triangulation step on every artifact and reports drift.

Probabilistic (LLM judgment, reviewer-audited):

1. **Candidate selection** — LLM ranks retrieval results; wrong-but-plausible
   picks caught by triangulation.
2. **Excerpt selection** — LLM picks quotes; substring check verifies they're real.
3. **`claim_supported` field** — LLM's stated link, reviewer-auditable in
   the artifact body.

## Configuration

Environment variables:

| Var | Purpose | Required? |
| --- | --- | --- |
| `OPENALEX_API_KEY` | OpenAlex polite-pool API key — [register here](https://openalex.org/signup) (30s) | Yes (since 2026-02-13) |

## Operational notes

- **Latency**: 5-15s per `verify_and_cite()` call (2-5 API calls + LLM judgment).
  Do NOT put this in a pre-commit hook — see the [10-second pre-commit rule](https://www.deployhq.com/git/ai-git-hooks).
- **Drift audit cadence**: `audit_existing_citations()` re-runs the
  triangulation step on every artifact. Schedule weekly, or invoke before
  any major submission (paper, poster, LinkedIn post).
- **Human override**: if a triangulation conflict is a known false positive
  (e.g., S2 has stale data), invoke with `override=True, override_reason="..."`.
  Records `human_overridden: true` in the artifact frontmatter.
```

- [ ] **Step 3: Link from specialists.md**

Edit `docs/agents/specialists.md` — find the Aletheia section and append:

```markdown
For the new academic-citation verification capability, see
[aletheia.md](aletheia.md).
```

- [ ] **Step 4: Wire into nav (zensical.toml)**

Find the `[nav]` or equivalent in `zensical.toml`. Add `docs/agents/aletheia.md`
under the Agents section if not already nested-listed.

Run: `grep -n "aletheia\|Agents" zensical.toml | head -10`

- [ ] **Step 5: Build the docs site to verify**

Run: `uv run zensical build --clean 2>&1 | tail -10`

Expected: clean build, no broken-link warnings on the new page.

- [ ] **Step 6: Commit + PR**

```bash
git add docs/agents/aletheia.md docs/agents/specialists.md zensical.toml
git commit -m "docs(aletheia-v2): user-facing documentation for verify_and_cite"
git push -u origin feat/aletheia-v2-pr6-docs
gh pr create --title "docs(aletheia-v2): user-facing documentation (PR 6/6)" --body "Final PR — user-facing docs for the new verify_and_cite capability."
gh pr checks --watch
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

## Cross-PR verification checkpoints

After each PR merges, before starting the next:

1. **Sync local main**: `git checkout main && git pull`.
2. **Smoke local install**: `uv sync --extra aletheia-v2` succeeds.
3. **Smoke import**: `uv run python -c "from kourai_common import citation_artifacts"` (PR 1 onward), then add `triangulate` (PR 2), `academic_search` (PR 3), `from agents.aletheia.agent import verify_and_cite` (PR 4).
4. **Cassette tests**: `uv run pytest tests/integration/test_academic_search.py -v` (PR 3 onward) — verifies cassettes replay cleanly with no network.
5. **End-to-end smoke** (PR 4 onward, optional): `uv run python -c "import asyncio; from agents.aletheia.agent import verify_and_cite; from pathlib import Path; r = asyncio.run(verify_and_cite(claim='ALIE attack perturbs honest updates', project_root=Path('/tmp/smoke'))); print(r)"` against real APIs.

If any checkpoint fails, halt and diagnose before the next PR.

---

## After all 6 PRs merge

- Update `docs/architecture/2026-05-23-aletheia-v2-citation-verification-design.md` Section 12 to mark each phase shipped with the merge commit SHA.
- Add a one-liner to kourai's ROADMAP.md `## Completed` section.
- Use the new capability on the next vFL / phalanx-fl PR that touches citations. Document the experience (latency, false-positive rate, override frequency) in a follow-up note.
- Decide on Phase 2: proactive inline guard (Techne / Kallos call Aletheia inline when emitting citations). The decision depends on how often Aletheia is invoked manually in practice — gather data first.
