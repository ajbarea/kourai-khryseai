"""Schema models and gameplay-rule split logic for the Forge Memoir."""

from __future__ import annotations

import pytest

from kourai_common.federation.memoir_schema import (
    EntrySource,
    MemoirEntry,
    PlayerResponse,
    SplitDecision,
    TrainingLabel,
    decide_split,
)


class TestSplitDecision:
    """SplitDecision is a frozen pydantic model with two booleans and an
    invariant that they cannot both be true."""

    def test_shared_eligible_only(self):
        d = SplitDecision(shared_eligible=True, private_only=False)
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_private_only_only(self):
        d = SplitDecision(shared_eligible=False, private_only=True)
        assert d.shared_eligible is False
        assert d.private_only is True

    def test_neither_set_is_valid(self):
        # Used for entries that are still being constructed.
        d = SplitDecision(shared_eligible=False, private_only=False)
        assert d.shared_eligible is False
        assert d.private_only is False

    def test_both_true_is_rejected(self):
        with pytest.raises(ValueError, match="cannot both be true"):
            SplitDecision(shared_eligible=True, private_only=True)


class TestDecideSplit:
    """Pure function applying the gameplay rules from the design spec."""

    def test_specialist_proposed_output_is_shared(self):
        d = decide_split(EntrySource.SPECIALIST_PROPOSED, agent="kallos")
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_player_revision_is_private(self):
        d = decide_split(EntrySource.PLAYER_REVISION, agent="kallos")
        assert d.shared_eligible is False
        assert d.private_only is True

    def test_federating_agent_interrupt_is_shared(self):
        d = decide_split(EntrySource.AGENT_INTERRUPT, agent="aidos")
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_cupid_interrupt_is_private(self):
        d = decide_split(EntrySource.AGENT_INTERRUPT, agent="cupid")
        assert d.private_only is True
        assert d.shared_eligible is False

    def test_puck_interrupt_is_private(self):
        d = decide_split(EntrySource.AGENT_INTERRUPT, agent="puck")
        assert d.private_only is True
        assert d.shared_eligible is False

    def test_disagreement_resolution_is_shared(self):
        d = decide_split(EntrySource.DISAGREEMENT_RESOLUTION, agent="hephaestus")
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_cupid_scene_is_private(self):
        d = decide_split(EntrySource.CUPID_SCENE, agent="cupid")
        assert d.private_only is True

    def test_puck_engagement_is_private(self):
        d = decide_split(EntrySource.PUCK_ENGAGEMENT, agent="puck")
        assert d.private_only is True

    def test_affinity_change_is_private(self):
        d = decide_split(EntrySource.AFFINITY_CHANGE, agent="cupid")
        assert d.private_only is True

    def test_player_profile_is_private(self):
        d = decide_split(EntrySource.PLAYER_PROFILE, agent=None)
        assert d.private_only is True

    def test_raw_transcript_is_private(self):
        d = decide_split(EntrySource.RAW_TRANSCRIPT, agent=None)
        assert d.private_only is True

    def test_task_description_is_private(self):
        d = decide_split(EntrySource.TASK_DESCRIPTION, agent=None)
        assert d.private_only is True

    def test_unknown_agent_for_interrupt_raises(self):
        with pytest.raises(ValueError, match="unknown agent"):
            decide_split(EntrySource.AGENT_INTERRUPT, agent="nobody")


class TestMemoirEntry:
    """The on-disk schema. Each entry carries narrative + training payloads
    and auto-populates its SplitDecision from EntrySource + agent."""

    def test_minimal_specialist_proposal_is_shared(self):
        entry = MemoirEntry(
            scene_id="session-1.turn-1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="some style edit",
        )
        assert entry.split.shared_eligible is True
        assert entry.split.private_only is False

    def test_cupid_scene_is_private(self):
        entry = MemoirEntry(
            scene_id="session-1.scene-cupid-7",
            agent="cupid",
            source=EntrySource.CUPID_SCENE,
            narrative_beat="cupid_late_night_check_in",
        )
        assert entry.split.private_only is True

    def test_pipeline_turn_with_player_response(self):
        entry = MemoirEntry(
            scene_id="session-1.turn-2",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="lint fix",
            player_response=PlayerResponse(kind="modified", delta="player edits", felt="right"),
            training_label=TrainingLabel(
                preference_pair=[
                    {"text": "lint fix", "score": 0},
                    {"text": "lint fix with player edits", "score": 1},
                ],
                weight=1.0,
            ),
        )
        assert entry.player_response.kind == "modified"
        assert entry.training_label.weight == 1.0

    def test_unknown_agent_rejected(self):
        with pytest.raises(ValueError, match="unknown agent"):
            MemoirEntry(
                scene_id="session-1.turn-3",
                agent="nobody",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed="x",
            )

    def test_round_trip_json(self):
        original = MemoirEntry(
            scene_id="session-1.turn-1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="hello",
        )
        as_json = original.model_dump_json()
        restored = MemoirEntry.model_validate_json(as_json)
        assert restored == original

    def test_optional_context_block_round_trips(self):
        # Spec shows a `context` block with task_type, transcript_hash,
        # preceding_agents. We accept any dict for forward compatibility;
        # plan-02 will lock in the host-emitted shape.
        original = MemoirEntry(
            scene_id="session-1.turn-1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="hello",
            context={
                "task_type": "style_review",
                "transcript_hash": "sha256:abc",
                "preceding_agents": ["techne"],
            },
        )
        restored = MemoirEntry.model_validate_json(original.model_dump_json())
        assert restored.context["task_type"] == "style_review"
        assert restored.context["preceding_agents"] == ["techne"]
