"""Integration tests for the academic_search HTTP layer.

Uses pytest-recording / vcrpy: first run hits real APIs and records to
tests/cassettes/*.yaml; subsequent runs replay from disk. CI replays.

Refresh: uv run pytest --record-mode=rewrite tests/integration/test_academic_search.py
"""

from __future__ import annotations

import pytest

# academic_search depends on httpx + tenacity + (for the docling test) docling,
# all in the aletheia-v2 optional extra. CI's default `uv sync --all-packages
# --dev --frozen` does not install the extra; skip the whole module to keep
# CI green. Follow-up: add `--extra aletheia-v2` to the relevant CI job.
pytest.importorskip("httpx")
pytest.importorskip("tenacity")

pytestmark = pytest.mark.integration

from kourai_common.academic_search import (
    fetch_arxiv_html,
    fetch_paper_pdf_text,
    lookup_arxiv_metadata,
    lookup_openalex_by_doi,
    search_semantic_scholar,
)


@pytest.mark.vcr
@pytest.mark.asyncio
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
@pytest.mark.asyncio
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


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_lookup_arxiv_metadata_baruch_alie():
    meta = await lookup_arxiv_metadata("1902.06156")
    assert meta is not None
    assert meta.year == 2019
    assert "baruch" in meta.authors[0].lower()
    assert meta.arxiv_id == "1902.06156"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_fetch_arxiv_html_returns_paper_text():
    # 1902.06156 (ALIE, 2019) predates arXiv HTML5 and returns 404.
    # Use a 2026 Byzantine-FL paper that arXiv has rendered to HTML5.
    text = await fetch_arxiv_html("2605.15887")
    assert text is not None
    # Paper title: "Practical Validity Conditions for Byzantine-Tolerant FL"
    assert "byzantine" in text.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_lookup_openalex_pillutla_rfa():
    meta = await lookup_openalex_by_doi("10.1109/TSP.2022.3153135")
    assert meta is not None
    assert meta.year == 2022
    assert "pillutla" in meta.authors[0].lower()
    # DOIs are case-insensitive; OpenAlex lowercases them internally.
    assert meta.doi is not None
    assert meta.doi.lower() == "10.1109/tsp.2022.3153135"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_lookup_openalex_missing_returns_none():
    meta = await lookup_openalex_by_doi("10.0000/nonexistent")
    assert meta is None


@pytest.mark.nightly
@pytest.mark.asyncio
async def test_fetch_paper_pdf_via_docling():
    """Fetch the FLPoison PDF and extract its text via docling.

    Marked nightly: the cassette would be ~62MB (full PDF download +
    rendered Markdown), which is too large for git.

    No CI job currently runs this. Reaching it needs both the
    `aletheia-v2` extra (or the module importorskips away) and a selector
    that admits `nightly`. The integration jobs sync without the extra;
    `aletheia-v2-tests` has the extra but selects `-m "not nightly"`.
    """
    text = await fetch_paper_pdf_text("https://arxiv.org/pdf/2502.03801")
    assert text is not None
    assert "federated" in text.lower()
