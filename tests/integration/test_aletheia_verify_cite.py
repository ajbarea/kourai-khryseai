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


from pathlib import Path

from agents.aletheia.agent import verify_and_cite
from kourai_common.citation_artifacts import ConflictReport


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_verify_and_cite_happy_path(tmp_path: Path, fake_llm):
    # Script the LLM: extract claim, pick the first S2 candidate, return excerpts
    fake_llm.queue("ALIE perturbs within statistical envelope (Baruch 2019)")
    fake_llm.queue("0")  # "pick first candidate by index"
    fake_llm.queue('[{"quote": "We propose a novel attack", "ref": "Abstract"}]')

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
    from kourai_common.citation_artifacts import PaperMetadata

    fake_llm.queue("ALIE perturbation")
    fake_llm.queue("0")
    fake_llm.queue('[{"quote": "We propose ALIE", "ref": "Abstract"}]')

    async def fake_s2(*args, **kwargs):
        return [
            PaperMetadata(
                title="A Little Is Enough",
                authors=["Wrong Author"],  # deliberate mismatch
                year=2019,
                urls={"abs": "https://arxiv.org/abs/1902.06156"},
                arxiv_id="1902.06156",
            )
        ]

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
    monkeypatch.setattr(
        "agents.aletheia.agent.aletheia_fetch_paper_text",
        lambda **kw: fake_html(kw.get("arxiv_id", "")),
    )

    cite, conflict = await verify_and_cite(
        claim="ALIE perturbs honest updates",
        project_root=tmp_path,
        llm=fake_llm,
    )
    assert cite is None
    assert isinstance(conflict, ConflictReport)
    assert conflict.kind == "triangulation_mismatch"
    assert any(f[0] == "first_author_surname" for f in conflict.field_disagreements)


from agents.aletheia.agent import audit_existing_citations
from kourai_common.citation_artifacts import PaperMetadata, TriangulationResult


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
