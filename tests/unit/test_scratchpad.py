"""Unit tests for kourai_common.scratchpad.

Per-agent ring-buffered chain-of-thought / TODO buffer. Tests cover
the dataclass shape, ring-buffer cap behavior, per-agent isolation,
chronological cross-agent merging, and the process-scoped singleton.
"""

from __future__ import annotations

import dataclasses
import time

import pytest

from kourai_common.scratchpad import (
    DEFAULT_MAX_PER_AGENT,
    Scratchpad,
    ScratchpadEntry,
    get_scratchpad,
    reset_scratchpad,
)

# ===================================================================
# ScratchpadEntry — frozen dataclass surface
# ===================================================================


class TestScratchpadEntry:
    def test_holds_fields(self):
        e = ScratchpadEntry(agent="metis", text="Plan:\n- step", timestamp=1.5)
        assert e.agent == "metis"
        assert e.text == "Plan:\n- step"
        assert e.timestamp == 1.5

    def test_frozen(self):
        e = ScratchpadEntry(agent="metis", text="x", timestamp=0.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.agent = "techne"  # type: ignore[misc]

    def test_equality_by_value(self):
        a = ScratchpadEntry(agent="metis", text="x", timestamp=1.0)
        b = ScratchpadEntry(agent="metis", text="x", timestamp=1.0)
        assert a == b


# ===================================================================
# Scratchpad.add — append to per-agent buffer
# ===================================================================


class TestScratchpadAdd:
    def test_returns_entry_with_agent_and_text(self):
        s = Scratchpad()
        e = s.add("metis", "Plan:\n- decompose login")
        assert e.agent == "metis"
        assert e.text == "Plan:\n- decompose login"
        assert e.timestamp > 0

    def test_appends_to_buffer(self):
        s = Scratchpad()
        s.add("metis", "first")
        s.add("metis", "second")
        ents = s.entries("metis")
        assert [e.text for e in ents] == ["first", "second"]

    def test_per_agent_isolation(self):
        """A chatty agent doesn't push other agents' entries out."""
        s = Scratchpad(max_per_agent=2)
        s.add("metis", "metis-1")
        s.add("techne", "techne-1")
        for i in range(5):
            s.add("metis", f"flood-{i}")
        # techne's buffer is untouched by metis flooding hers.
        assert [e.text for e in s.entries("techne")] == ["techne-1"]
        # metis only has the last 2.
        assert [e.text for e in s.entries("metis")] == ["flood-3", "flood-4"]


# ===================================================================
# Scratchpad.entries — per-agent + cross-agent chronological
# ===================================================================


class TestScratchpadEntries:
    def test_no_arg_returns_all_oldest_first(self):
        """Cross-agent ordering recovered via wall-clock timestamp."""
        s = Scratchpad()
        s.add("metis", "first")
        time.sleep(0.001)
        s.add("techne", "second")
        time.sleep(0.001)
        s.add("metis", "third")
        merged = s.entries()
        assert [e.text for e in merged] == ["first", "second", "third"]

    def test_unknown_agent_returns_empty(self):
        s = Scratchpad()
        assert s.entries("never_added") == []

    def test_returns_copy_not_internal_buffer(self):
        """Mutating the returned list must not affect the buffer."""
        s = Scratchpad()
        s.add("metis", "x")
        out = s.entries("metis")
        out.clear()
        assert len(s.entries("metis")) == 1


# ===================================================================
# Scratchpad.agents — alphabetical, only buffered
# ===================================================================


class TestScratchpadAgents:
    def test_returns_alphabetical(self):
        s = Scratchpad()
        s.add("techne", "x")
        s.add("metis", "y")
        s.add("dokimasia", "z")
        assert s.agents() == ["dokimasia", "metis", "techne"]

    def test_excludes_cleared_agent(self):
        s = Scratchpad()
        s.add("metis", "x")
        s.clear("metis")
        assert s.agents() == []

    def test_empty_when_nothing_added(self):
        assert Scratchpad().agents() == []


# ===================================================================
# Scratchpad ring-buffer cap
# ===================================================================


class TestScratchpadCap:
    def test_default_cap_constant(self):
        assert DEFAULT_MAX_PER_AGENT == 20

    def test_custom_cap_evicts_oldest(self):
        s = Scratchpad(max_per_agent=3)
        for i in range(5):
            s.add("metis", f"entry-{i}")
        # Oldest 2 evicted; newest 3 remain.
        assert [e.text for e in s.entries("metis")] == [
            "entry-2",
            "entry-3",
            "entry-4",
        ]

    def test_default_cap_holds_under_threshold(self):
        s = Scratchpad()
        for i in range(DEFAULT_MAX_PER_AGENT):
            s.add("metis", f"e-{i}")
        assert len(s.entries("metis")) == DEFAULT_MAX_PER_AGENT


# ===================================================================
# Scratchpad.clear
# ===================================================================


class TestScratchpadClear:
    def test_clear_one_agent_leaves_others_alone(self):
        s = Scratchpad()
        s.add("metis", "x")
        s.add("techne", "y")
        s.clear("metis")
        assert s.entries("metis") == []
        assert len(s.entries("techne")) == 1

    def test_clear_all(self):
        s = Scratchpad()
        s.add("metis", "x")
        s.add("techne", "y")
        s.clear()
        assert len(s) == 0
        assert s.agents() == []

    def test_clear_unknown_agent_silent(self):
        """Clearing an agent that never had entries is a no-op, not an error."""
        s = Scratchpad()
        s.clear("never_added")  # must not raise
        assert s.agents() == []


# ===================================================================
# __len__ — total entry count across all agents
# ===================================================================


class TestScratchpadLen:
    def test_len_zero_initially(self):
        assert len(Scratchpad()) == 0

    def test_len_sums_across_agents(self):
        s = Scratchpad()
        s.add("metis", "a")
        s.add("metis", "b")
        s.add("techne", "c")
        assert len(s) == 3

    def test_len_respects_cap(self):
        s = Scratchpad(max_per_agent=2)
        for i in range(5):
            s.add("metis", f"e-{i}")
        assert len(s) == 2


# ===================================================================
# Process-scoped singleton
# ===================================================================


class TestSharedSingleton:
    def test_get_scratchpad_idempotent_within_process(self):
        reset_scratchpad()
        a = get_scratchpad()
        b = get_scratchpad()
        assert a is b

    def test_singleton_persists_state_across_calls(self):
        reset_scratchpad()
        get_scratchpad().add("metis", "first")
        # Different access path; same instance, same state.
        assert [e.text for e in get_scratchpad().entries("metis")] == ["first"]

    def test_reset_replaces_instance(self):
        a = get_scratchpad()
        a.add("metis", "x")
        reset_scratchpad()
        b = get_scratchpad()
        assert a is not b
        assert b.entries("metis") == []
