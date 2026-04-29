"""Streaming-layer integration of M17 Phase 1 fact synthesis.

When a Metis pause is resolved on the next turn, ``send_and_stream``
calls into the streaming helper to:

- Pop the stashed ``preference_kind`` for the active context_id.
- Strip ``forge_tags`` from the player's reply so the bare answer
  becomes the fact body.
- Derive the M17 ``project_id`` from the ``[project_root: ...]`` tag.
- Hand off to ``synthesise_fact_from_pause``.

Unit-tests the helpers directly so we don't pull a full A2A client
through the seam.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hosts.cli.streaming import (
    _project_id_from_forge_tags,
    _strip_forge_tag_prefix,
    _try_synthesise_pause_fact,
)
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


class TestStripForgeTagPrefix:
    def test_no_tags_returns_input_unchanged(self):
        assert _strip_forge_tag_prefix("80%", None) == "80%"
        assert _strip_forge_tag_prefix("80%", []) == "80%"

    def test_strips_single_prefix_tag(self):
        forge = ["[project_root: /var/forge/proj]"]
        text = "[project_root: /var/forge/proj]\n80%"
        assert _strip_forge_tag_prefix(text, forge) == "80%"

    def test_strips_multiple_prefix_tags_in_order(self):
        forge = ["[project_root: /var/forge/proj]", "[yolo: on]"]
        text = "[project_root: /var/forge/proj]\n[yolo: on]\nactual reply"
        assert _strip_forge_tag_prefix(text, forge) == "actual reply"

    def test_leaves_text_unchanged_when_prefix_does_not_match(self):
        # Defensive: if the prefix shape drifts, return as-is rather than
        # mangling the player's response.
        forge = ["[project_root: /var/forge/proj]"]
        assert _strip_forge_tag_prefix("plain reply", forge) == "plain reply"


class TestProjectIdFromForgeTags:
    def test_none_when_no_tags(self):
        assert _project_id_from_forge_tags(None) is None
        assert _project_id_from_forge_tags([]) is None

    def test_none_when_no_project_root_tag(self):
        assert _project_id_from_forge_tags(["[yolo: on]"]) is None

    def test_derives_from_project_root_tag(self):
        from kourai_common.projects import derive_project_id

        forge = ["[project_root: /var/forge/example]"]
        result = _project_id_from_forge_tags(forge)
        assert result == derive_project_id("/var/forge/example")

    def test_distinct_paths_yield_distinct_ids(self):
        a = _project_id_from_forge_tags(["[project_root: /var/forge/proj-a]"])
        b = _project_id_from_forge_tags(["[project_root: /var/forge/proj-b]"])
        assert a is not None and b is not None and a != b

    def test_explicit_project_id_tag_wins_over_project_root(self):
        # M17 stability: [project_id: <stable>] is the canonical fact axis.
        # When forge worktrees are wrapped per-turn, project_root carries the
        # per-session workdir — deriving from it yields a different id every
        # turn, breaking cross-session recall. The explicit tag carries the
        # stable id derived from the project's persistent path.
        forge = [
            "[project_id: stable-abc123def4567890]",
            "[project_root: /var/forge/proj/.forge/session-uuid-xyz]",
        ]
        assert _project_id_from_forge_tags(forge) == "stable-abc123def4567890"

    def test_project_id_tag_alone_is_honoured(self):
        forge = ["[project_id: stable-abc123def4567890]"]
        assert _project_id_from_forge_tags(forge) == "stable-abc123def4567890"

    def test_project_root_still_derives_when_no_explicit_id(self):
        # Backward compatibility: turns that emit only project_root continue
        # to derive a project_id. The instability is the caller's problem;
        # the parser is not the place to fix it.
        from kourai_common.projects import derive_project_id

        forge = ["[project_root: /var/forge/example]"]
        assert _project_id_from_forge_tags(forge) == derive_project_id("/var/forge/example")


class TestTrySynthesisePauseFact:
    """The streaming-layer write hook — fires once the pause is answered."""

    def test_no_stash_is_a_noop(self):
        with patch("hosts.cli.streaming.synthesise_fact_from_pause") as synth:
            _try_synthesise_pause_fact(context_id="ctx-1", user_text="80%", forge_tags=None)
            synth.assert_not_called()

    def test_calls_synthesise_with_bare_answer_and_project_id(self):
        from kourai_common.projects import derive_project_id

        stash_preference_kind("ctx-1", "coverage_target", source_agent="metis")
        forge = ["[project_root: /var/forge/proj]"]

        fake_profile = type("P", (), {"player_id": "player-uuid"})()
        with (
            patch("hosts.cli.streaming.synthesise_fact_from_pause") as synth,
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=fake_profile,
            ),
        ):
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="[project_root: /var/forge/proj]\n80%",
                forge_tags=forge,
            )

        synth.assert_called_once_with(
            player_id="player-uuid",
            project_id=derive_project_id("/var/forge/proj"),
            preference_kind="coverage_target",
            player_response="80%",
            source_agent="metis",
        )
        # Stash consumed — second call is a no-op.
        assert peek_preference_kind("ctx-1") is None

    def test_no_player_profile_skips_synthesis(self):
        stash_preference_kind("ctx-1", "python_version")
        with (
            patch("hosts.cli.streaming.synthesise_fact_from_pause") as synth,
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=None,
            ),
        ):
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="3.13",
                forge_tags=None,
            )
        synth.assert_not_called()
        # Stash was consumed even when the profile was missing — the pop is
        # by design unconditional (a stale entry would otherwise persist
        # indefinitely if the player wipes their profile mid-pause).
        assert peek_preference_kind("ctx-1") is None

    def test_blank_answer_skips_synthesis(self):
        stash_preference_kind("ctx-1", "python_version")
        forge = ["[project_root: /var/forge/proj]"]
        with (
            patch("hosts.cli.streaming.synthesise_fact_from_pause") as synth,
            patch("kourai_common.player_profile.PlayerProfile.load") as load,
        ):
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="[project_root: /var/forge/proj]\n   ",
                forge_tags=forge,
            )
        synth.assert_not_called()
        load.assert_not_called()

    def test_global_fact_when_no_project_root_in_forge_tags(self):
        stash_preference_kind("ctx-1", "python_version", source_agent="metis")
        fake_profile = type("P", (), {"player_id": "player-uuid"})()
        with (
            patch("hosts.cli.streaming.synthesise_fact_from_pause") as synth,
            patch(
                "kourai_common.player_profile.PlayerProfile.load",
                return_value=fake_profile,
            ),
        ):
            _try_synthesise_pause_fact(
                context_id="ctx-1",
                user_text="3.12",
                forge_tags=["[yolo: on]"],
            )
        synth.assert_called_once()
        kwargs = synth.call_args.kwargs
        assert kwargs["project_id"] is None
        assert kwargs["player_response"] == "3.12"
