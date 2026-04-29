"""Cross-turn stash for HOTL pause classification (M17 Phase 1)."""

from __future__ import annotations

import pytest

from kourai_common.pause_state import (
    PendingPause,
    clear,
    peek_preference_kind,
    pop_preference_kind,
    stash_preference_kind,
)


@pytest.fixture(autouse=True)
def _isolated_stash():
    """Each test gets a fresh in-process stash."""
    clear()
    yield
    clear()


class TestStash:
    def test_stash_then_pop_returns_kind_and_agent(self):
        stash_preference_kind("ctx-1", "coverage_target", source_agent="metis")
        popped = pop_preference_kind("ctx-1")
        assert popped == PendingPause(preference_kind="coverage_target", source_agent="metis")

    def test_default_source_agent_is_metis(self):
        stash_preference_kind("ctx-1", "python_version")
        popped = pop_preference_kind("ctx-1")
        assert popped is not None
        assert popped.source_agent == "metis"

    def test_pop_returns_none_for_unknown_context(self):
        assert pop_preference_kind("never-stashed") is None

    def test_pop_consumes_entry(self):
        stash_preference_kind("ctx-1", "python_version")
        pop_preference_kind("ctx-1")
        assert pop_preference_kind("ctx-1") is None

    def test_stash_overwrites_prior_entry_on_same_context(self):
        stash_preference_kind("ctx-1", "coverage_target")
        stash_preference_kind("ctx-1", "python_version", source_agent="techne")
        popped = pop_preference_kind("ctx-1")
        assert popped == PendingPause(preference_kind="python_version", source_agent="techne")

    def test_stash_isolates_distinct_contexts(self):
        stash_preference_kind("ctx-A", "coverage_target", source_agent="metis")
        stash_preference_kind("ctx-B", "python_version", source_agent="kallos")
        a = pop_preference_kind("ctx-A")
        b = pop_preference_kind("ctx-B")
        assert (
            a is not None and a.preference_kind == "coverage_target" and a.source_agent == "metis"
        )
        assert (
            b is not None and b.preference_kind == "python_version" and b.source_agent == "kallos"
        )

    def test_peek_does_not_consume(self):
        stash_preference_kind("ctx-1", "style_rules")
        first = peek_preference_kind("ctx-1")
        second = peek_preference_kind("ctx-1")
        assert first == second
        popped = pop_preference_kind("ctx-1")
        assert popped == first

    def test_peek_returns_none_for_unknown_context(self):
        assert peek_preference_kind("nope") is None

    def test_clear_drops_all_entries(self):
        stash_preference_kind("ctx-A", "coverage_target")
        stash_preference_kind("ctx-B", "python_version")
        clear()
        assert pop_preference_kind("ctx-A") is None
        assert pop_preference_kind("ctx-B") is None
