"""End-to-end tests for Aletheia's verify_and_cite agent loop."""

from __future__ import annotations

import pytest

# academic_search / triangulate depend on httpx + tenacity + rapidfuzz,
# all in the aletheia-v2 optional extra. CI's default `uv sync --all-packages
# --dev --frozen` does not install the extra; skip the whole module to keep
# CI green. The aletheia-v2 CI job installs the extra and runs these.
pytest.importorskip("httpx")
pytest.importorskip("tenacity")
pytest.importorskip("rapidfuzz")

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
