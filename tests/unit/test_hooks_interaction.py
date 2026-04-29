"""Tests for the interaction hooks layer (HOTL fact synthesis + memory extraction)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from kourai_common.hooks_interaction import (
    VALID_PREFERENCE_KINDS,
    synthesise_fact_from_pause,
)

# ── synthesise_fact_from_pause ────────────────────────────────────


class TestSynthesiseFactFromPause:
    def test_stores_fact_with_canonical_body_format(self):
        captured: list[dict] = []

        def capture(**kwargs: object) -> None:
            captured.append(kwargs)

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            ok = synthesise_fact_from_pause(
                player_id="p1",
                project_id="proj-A",
                preference_kind="coverage_target",
                player_response="80%",
                source_agent="metis",
            )

        assert ok is True
        assert len(captured) == 1
        assert captured[0]["project_id"] == "proj-A"
        assert captured[0]["agent_name"] == "metis"
        assert captured[0]["category"] == "fact"
        assert "coverage_target: 80%" in captured[0]["content"]

    def test_high_confidence_translates_to_full_weight(self):
        """High-confidence facts persist at importance == 1.0 (CONFIDENCE_WEIGHT['high'])."""
        captured: list[dict] = []

        def capture(**kwargs: object) -> None:
            captured.append(kwargs)

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            synthesise_fact_from_pause(
                player_id="p1",
                project_id="proj-A",
                preference_kind="python_version",
                player_response="3.12",
                source_agent="metis",
            )

        assert captured[0]["importance"] == 1.0

    def test_strips_whitespace_from_player_response(self):
        captured: list[dict] = []

        def capture(**kwargs: object) -> None:
            captured.append(kwargs)

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            synthesise_fact_from_pause(
                player_id="p1",
                project_id=None,
                preference_kind="commit_style",
                player_response="   conventional   ",
                source_agent="metis",
            )

        assert "commit_style: conventional" in captured[0]["content"]

    def test_global_scope_when_project_id_is_none(self):
        captured: list[dict] = []

        def capture(**kwargs: object) -> None:
            captured.append(kwargs)

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            synthesise_fact_from_pause(
                player_id="p1",
                project_id=None,
                preference_kind="style_rules",
                player_response="ruff at 88 cols",
                source_agent="metis",
            )

        assert captured[0]["project_id"] is None

    def test_unknown_preference_kind_skips_synthesis(self, caplog):
        """An unknown kind logs a warning and stores nothing rather than poisoning the graph."""
        with (
            patch("kourai_common.player.add_player_memory") as mock_add,
            caplog.at_level("WARNING"),
        ):
            ok = synthesise_fact_from_pause(
                player_id="p1",
                project_id="proj-A",
                preference_kind="not_a_real_kind",
                player_response="anything",
                source_agent="metis",
            )

        assert ok is False
        assert mock_add.call_count == 0
        assert "not_a_real_kind" in caplog.text

    def test_empty_response_skips_synthesis(self):
        with patch("kourai_common.player.add_player_memory") as mock_add:
            ok = synthesise_fact_from_pause(
                player_id="p1",
                project_id="proj-A",
                preference_kind="coverage_target",
                player_response="   ",
                source_agent="metis",
            )

        assert ok is False
        assert mock_add.call_count == 0

    def test_empty_player_id_skips_synthesis(self):
        with patch("kourai_common.player.add_player_memory") as mock_add:
            ok = synthesise_fact_from_pause(
                player_id="",
                project_id="proj-A",
                preference_kind="coverage_target",
                player_response="80%",
                source_agent="metis",
            )

        assert ok is False
        assert mock_add.call_count == 0

    @pytest.mark.parametrize(
        "kind",
        [
            "coverage_target",
            "python_version",
            "style_rules",
            "commit_style",
            "test_framework",
        ],
    )
    def test_phase1_vocabulary_all_accepted(self, kind):
        """Each Phase 1 closed-set kind is accepted."""
        assert kind in VALID_PREFERENCE_KINDS

        with patch("kourai_common.player.add_player_memory"):
            ok = synthesise_fact_from_pause(
                player_id="p1",
                project_id="proj-A",
                preference_kind=kind,
                player_response="some answer",
                source_agent="metis",
            )

        assert ok is True
