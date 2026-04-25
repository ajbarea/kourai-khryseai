"""Pure helpers used by hosts to construct MemoirEntries for the FL pipeline."""

from __future__ import annotations

import pytest

from kourai_common.federation.host_helpers import (
    build_pipeline_turn_entry,
    derive_scene_id,
)
from kourai_common.federation.memoir_schema import EntrySource


class TestDeriveSceneId:
    """`session-<short-id>.turn-<n>` is the canonical format."""

    def test_uses_first_eight_chars_of_session_id(self):
        sid = derive_scene_id("abcdef0123456789", turn_number=1)
        assert sid == "session-abcdef01.turn-1"

    def test_zero_turn_is_valid(self):
        # Some hosts may want to write a session-open marker entry.
        sid = derive_scene_id("abcdef01", turn_number=0)
        assert sid == "session-abcdef01.turn-0"

    def test_negative_turn_rejected(self):
        with pytest.raises(ValueError, match="turn_number must be"):
            derive_scene_id("abcdef01", turn_number=-1)

    def test_empty_session_id_rejected(self):
        with pytest.raises(ValueError, match="session_id must be"):
            derive_scene_id("", turn_number=1)


class TestBuildPipelineTurnEntry:
    """Constructs a SPECIALIST_PROPOSED MemoirEntry from CLI-side data."""

    def test_minimal_inputs_produces_shared_eligible_entry(self):
        entry = build_pipeline_turn_entry(
            scene_id="session-abc.turn-1",
            agent="kallos",
            agent_proposed="lint suggestion text",
        )
        assert entry.scene_id == "session-abc.turn-1"
        assert entry.agent == "kallos"
        assert entry.source is EntrySource.SPECIALIST_PROPOSED
        assert entry.agent_proposed == "lint suggestion text"
        assert entry.split.shared_eligible is True

    def test_unknown_agent_rejected(self):
        with pytest.raises(ValueError, match="unknown agent"):
            build_pipeline_turn_entry(
                scene_id="session-abc.turn-1",
                agent="nobody",
                agent_proposed="x",
            )

    def test_empty_agent_proposed_rejected(self):
        with pytest.raises(ValueError, match="agent_proposed must be"):
            build_pipeline_turn_entry(
                scene_id="session-abc.turn-1",
                agent="kallos",
                agent_proposed="",
            )
