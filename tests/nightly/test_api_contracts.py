"""Nightly: one real API call per source (S2 / OpenAlex / arXiv) to surface
upstream schema drift before it breaks the cassette-replay path in
`tests/integration/`. Push/PR lane skips via `pytest.mark.nightly`; only
`nightly.yml`'s `aletheia-v2-contracts` job runs these."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("httpx")

from kourai_common.academic_search import (
    lookup_arxiv_metadata,
    lookup_openalex_by_doi,
    search_semantic_scholar,
)

pytestmark = pytest.mark.nightly


@pytest.mark.asyncio
async def test_s2_api_contract():
    """S2 still returns title/authors/year. Needs `S2_API_KEY` — unauthenticated
    S2 rate-limits too hard for a 3-test run."""
    if not os.environ.get("S2_API_KEY"):
        pytest.skip("S2_API_KEY not set; unauthenticated S2 rate-limits hard")
    candidates = await search_semantic_scholar("FedAvg federated learning", limit=1)
    assert len(candidates) >= 1
    first = candidates[0]
    assert first.title
    assert first.authors
    assert 2010 <= first.year <= 2030


@pytest.mark.asyncio
async def test_openalex_api_contract():
    """OpenAlex DOI lookup still works on a stable paper."""
    meta = await lookup_openalex_by_doi("10.1109/TSP.2022.3153135")
    assert meta is not None
    assert meta.year == 2022
    assert "pillutla" in meta.authors[0].lower()


@pytest.mark.asyncio
async def test_arxiv_api_contract():
    """arXiv API still returns metadata for the ALIE paper (Baruch et al., 2019)."""
    meta = await lookup_arxiv_metadata("1902.06156")
    assert meta is not None
    assert meta.year == 2019
    assert "baruch" in meta.authors[0].lower()
