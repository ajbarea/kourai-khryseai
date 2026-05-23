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
