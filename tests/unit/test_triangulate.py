"""Tests for the triangulation gate."""

from __future__ import annotations

from kourai_common.triangulate import (
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
        assert (
            compare_dois("https://doi.org/10.1109/TSP.2022.3153135", "10.1109/tsp.2022.3153135")
            is True
        )

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
        assert (
            compare_titles(
                "SoK: Benchmarking Poisoning Attacks and Defenses in Federated Learning",
                "Benchmarking Poisoning Attacks and Defenses in Federated Learning",
            )
            is True
        )

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
        assert (
            venues_equivalent(
                "Advances in Neural Information Processing Systems 32",
                "NeurIPS 2019",
            )
            is True
        )

    def test_non_alias_different(self):
        assert venues_equivalent("ICML 2019", "NeurIPS 2019") is False

    def test_none_returns_true(self):
        # Missing venue is non-decisive — never rejects
        assert venues_equivalent(None, "NeurIPS 2019") is True
        assert venues_equivalent("NeurIPS 2019", None) is True


from kourai_common.citation_artifacts import PaperMetadata
from kourai_common.triangulate import triangulate


def _meta(
    *,
    title="Sample Title",
    authors=("First Author",),
    year=2025,
    arxiv_id="2025.0001",
    doi=None,
    venue=None,
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
        result, conflict = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is not None
        assert conflict is None
        assert result.verified is True
        assert result.decisive_fields_agreed is True

    def test_first_author_mismatch_rejects(self):
        primary = _meta(authors=("Heyi Zhang",))
        secondary = _meta(authors=("Yifei Liu",))
        result, conflict = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is None
        assert conflict is not None
        assert conflict.kind == "triangulation_mismatch"
        assert any(f[0] == "first_author_surname" for f in conflict.field_disagreements)

    def test_year_mismatch_rejects(self):
        primary = _meta(year=2025)
        secondary = _meta(year=2024)
        result, conflict = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is None
        assert conflict is not None
        assert any(f[0] == "year" for f in conflict.field_disagreements)

    def test_arxiv_id_mismatch_rejects(self):
        primary = _meta(arxiv_id="2502.03801")
        secondary = _meta(arxiv_id="1902.06156")
        result, conflict = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is None
        assert conflict is not None
        assert any(f[0] == "arxiv_id" for f in conflict.field_disagreements)

    def test_title_well_above_threshold_accepts(self):
        primary = _meta(title="SoK: Benchmarking Poisoning Attacks")
        # Trivial punctuation difference
        secondary = _meta(title="SoK Benchmarking Poisoning Attacks")
        result, _ = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is not None
        assert result.verified is True

    def test_title_well_below_threshold_rejects(self):
        primary = _meta(title="SoK: Benchmarking Poisoning Attacks")
        secondary = _meta(title="A Different Paper Entirely")
        result, conflict = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is None
        assert conflict is not None
        assert any(f[0] == "title" for f in conflict.field_disagreements)

    def test_venue_alias_does_not_reject(self):
        primary = _meta(venue="NeurIPS 2019")
        secondary = _meta(venue="NIPS 2019")
        result, _ = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is not None
        assert result.verified is True
        # No notes about venue since they're aliased
        assert not any("venue" in n for n in result.notes)

    def test_venue_non_alias_recorded_as_note(self):
        primary = _meta(venue="NeurIPS 2019")
        secondary = _meta(venue="ICML 2019")
        result, _ = triangulate(
            primary, secondary, primary_source="s2", secondary_source="openalex"
        )
        assert result is not None
        # Venue is non-decisive — still verified
        assert result.verified is True
        # But recorded as a note
        assert any("venue" in n.lower() for n in result.notes)

    def test_single_source_no_secondary(self):
        primary = _meta()
        result, _ = triangulate(primary, None, primary_source="s2", secondary_source=None)
        assert result is not None
        assert result.verified is True
        assert result.single_source_verified is True
        assert "no_secondary_source_available" in result.notes
