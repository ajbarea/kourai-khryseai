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
