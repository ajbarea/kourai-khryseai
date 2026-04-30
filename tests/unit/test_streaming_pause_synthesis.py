"""Streaming-layer integration of M17 Phase 1 fact synthesis.

When a Metis pause is resolved on the next turn, ``send_and_stream``
calls into the streaming helper to:

- Pop the stashed ``preference_kind`` for the active context_id.
- Treat the player's reply as the bare answer (M7 Phase 5 dropped the
  text-tag prefix; the metadata rides on ``Message.metadata`` instead).
- Derive the M17 ``project_id`` from the forge metadata.
- Hand off to ``synthesise_fact_from_pause``.

Unit-tests the helpers directly so we don't pull a full A2A client
through the seam.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hosts.cli.streaming import _project_id_from_metadata, _try_synthesise_pause_fact
from kourai_common.pause_state import (
    clear,
    peek_preference_kind,
    stash_preference_kind,
)


@pytest.fixture(autouse=True)
def _isolated_stash():
    clear()
    yield
    clear()


class TestProjectIdFromMetadata:
    def test_returns_none_for_empty_metadata(self):
        assert _project_id_from_metadata(None) is None
        assert _project_id_from_metadata({}) is None

    def test_prefers_explicit_project_id_key(self):
        meta = {"project_id": "abc123", "project_root": "/some/path"}
        assert _project_id_from_metadata(meta) == "abc123"

    def test_strips_whitespace(self):
        assert _project_id_from_metadata({"project_id": "  abc  "}) == "abc"

    def test_falls_back_to_deriving_from_project_root(self):
        meta = {"project_root": "/var/proj"}
        with patch(
            "hosts.cli.streaming.derive_project_id", return_value="derived-id"
        ) as mock_derive:
            assert _project_id_from_metadata(meta) == "derived-id"
        mock_derive.assert_called_once_with("/var/proj")


class TestTrySynthesisePauseFact:
    def test_no_pending_kind_is_a_noop(self):
        with patch("hosts.cli.streaming.synthesise_fact_from_pause") as mock_synth:
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="80%",
                forge_metadata={"project_id": "proj"},
            )
        mock_synth.assert_not_called()

    def test_pending_kind_with_metadata_calls_synthesiser(self):
        stash_preference_kind("ctx-1", "coverage_target", source_agent="metis")

        from kourai_common.player import PlayerProfile

        fake_profile = PlayerProfile(player_id="player-1", display_name="AJ")

        with (
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=fake_profile,
            ),
            patch("hosts.cli.streaming.synthesise_fact_from_pause") as mock_synth,
        ):
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="80%",
                forge_metadata={"project_id": "proj-abc"},
            )

        mock_synth.assert_called_once_with(
            player_id="player-1",
            project_id="proj-abc",
            preference_kind="coverage_target",
            player_response="80%",
            source_agent="metis",
        )
        # Stash was popped.
        assert peek_preference_kind("ctx-1") is None

    def test_empty_user_text_does_not_synthesise(self):
        stash_preference_kind("ctx-1", "coverage_target", source_agent="metis")
        with patch("hosts.cli.streaming.synthesise_fact_from_pause") as mock_synth:
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="   ",
                forge_metadata={"project_id": "proj"},
            )
        mock_synth.assert_not_called()
