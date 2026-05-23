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

    def test_filesystem_safe_under_slash_in_author(self):
        meta = PaperMetadata(
            title="Sample Paper",
            authors=["Author/Slash"],
            year=2025,
            urls={"abs": "https://example.com"},
            arxiv_id="2502.03801",
        )
        slug = slug_for_paper(meta)
        assert "/" not in slug, f"slug contains path separator: {slug!r}"

    def test_filesystem_safe_under_weird_chars_in_title(self):
        meta = PaperMetadata(
            title="@#$% Weird Title",
            authors=["Normal Author"],
            year=2025,
            urls={"abs": "https://example.com"},
            arxiv_id="2502.03801",
        )
        slug = slug_for_paper(meta)
        # No filesystem-hostile chars
        assert all(c.isalnum() or c in "_-." for c in slug), f"slug contains unsafe char: {slug!r}"


import datetime as dt
from pathlib import Path

from hypothesis import given, settings, strategies as st
from hypothesis import HealthCheck

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
    arxiv_id = draw(st.sampled_from(["2502.03801", "1902.06156", None]))
    doi = draw(st.sampled_from(["10.1109/TSP.2022.3153135", None]))
    # Reject the None+None case (validator would raise)
    if arxiv_id is None and doi is None:
        arxiv_id = "2502.03801"  # force at least one identifier
    return PaperMetadata(
        title=draw(st.text(min_size=3, max_size=80, alphabet=st.characters(min_codepoint=32, max_codepoint=126))),
        authors=draw(st.lists(st.text(min_size=2, max_size=40, alphabet=st.characters(min_codepoint=32, max_codepoint=126)), min_size=1, max_size=10)),
        year=draw(st.integers(min_value=1900, max_value=2100)),
        urls={"abs": "https://example.com/paper"},
        arxiv_id=arxiv_id,
        doi=doi,
    )


@given(meta=paper_metadata_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
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
