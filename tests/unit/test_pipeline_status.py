"""Tests for kourai_common.pipeline_status."""

from __future__ import annotations

import dataclasses

import pytest

from kourai_common.pipeline_status import PipelineState, PipelineTracker


class TestPipelineState:
    def test_state_is_frozen(self):
        state = PipelineState(current_agent="hephaestus")
        with pytest.raises(dataclasses.FrozenInstanceError):
            state.current_agent = "metis"  # type: ignore[misc]

    def test_state_uses_slots(self):
        state = PipelineState(current_agent="hephaestus")
        # slots=True means no __dict__ on instances.
        assert not hasattr(state, "__dict__")


class TestPipelineTracker:
    def test_initial_state(self):
        tracker = PipelineTracker(initial_agent="hephaestus")
        assert tracker.current_agent == "hephaestus"
        assert tracker.state.current_agent == "hephaestus"

    def test_rejects_empty_initial(self):
        with pytest.raises(ValueError):
            PipelineTracker(initial_agent="")

    def test_handoff_advances_state(self):
        tracker = PipelineTracker(initial_agent="hephaestus")
        tracker.handoff("metis")
        assert tracker.current_agent == "metis"

    def test_handoff_replaces_state_object(self):
        # New frozen instance after handoff; old reference still valid.
        tracker = PipelineTracker(initial_agent="hephaestus")
        first = tracker.state
        tracker.handoff("metis")
        second = tracker.state
        assert first is not second
        assert first.current_agent == "hephaestus"
        assert second.current_agent == "metis"

    def test_handoff_to_same_agent_is_noop(self):
        tracker = PipelineTracker(initial_agent="hephaestus")
        first = tracker.state
        tracker.handoff("hephaestus")
        # No new state object allocated.
        assert tracker.state is first

    def test_handoff_rejects_empty(self):
        tracker = PipelineTracker(initial_agent="hephaestus")
        with pytest.raises(ValueError):
            tracker.handoff("")

    def test_chained_handoffs(self):
        tracker = PipelineTracker(initial_agent="hephaestus")
        tracker.handoff("metis")
        tracker.handoff("kallos")
        tracker.handoff("dokimasia")
        assert tracker.current_agent == "dokimasia"
