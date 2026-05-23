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
