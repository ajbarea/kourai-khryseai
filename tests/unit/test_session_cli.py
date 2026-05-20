"""Tests for the /session CLI slash command.

The data-layer helpers (``list_known_contexts``, ``clone_context``) are
hit by the dispatcher via runtime imports from ``kourai_common.memory``.
Tests monkey-patch at the source module so we never touch SQLite.
"""

from __future__ import annotations

import pytest

from hosts.cli.commands import _handle_session_command, _resolve_context_prefix


@pytest.fixture
def echoed(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(
        "hosts.cli.commands._echo",
        lambda text="", nl=True: captured.append(text),
    )
    return captured


@pytest.fixture
def fake_memory(monkeypatch):
    """Stub the kourai_common.memory functions the dispatcher imports."""
    state = {
        "contexts": [
            ("ctx-active-001", 12, 3),
            ("ctx-older-002", 5, 1),
            ("ctx-empty-003", 1, 1),
        ],
        "agents": ["hephaestus", "metis"],
        "history": {
            "hephaestus": [{"role": "user", "content": "hi"}] * 4,
            "metis": [{"role": "user", "content": "go"}] * 2,
        },
        "clone_count": 6,
        "clone_should_raise": False,
    }

    def fake_list(limit: int = 20):
        return state["contexts"][:limit]

    def fake_agents(_ctx):
        return state["agents"]

    def fake_history(_ctx, agent):
        return state["history"].get(agent, [])

    def fake_clone(src, dst):
        if state["clone_should_raise"]:
            raise ValueError(f"destination context {dst!r} already has messages")
        return state["clone_count"]

    monkeypatch.setattr("kourai_common.memory.list_known_contexts", fake_list)
    monkeypatch.setattr("kourai_common.memory.list_agents_with_history", fake_agents)
    monkeypatch.setattr("kourai_common.memory.get_history", fake_history)
    monkeypatch.setattr("kourai_common.memory.clone_context", fake_clone)
    return state


@pytest.fixture
def fake_usage(monkeypatch):
    """Stub get_session_usage so /session show has totals to print."""

    class _Usage:
        input_tokens = 1234
        output_tokens = 567

    class _Session:
        agents = {("hephaestus", "anthropic"): _Usage()}

    monkeypatch.setattr("kourai_common.usage.get_session_usage", lambda: _Session())


class TestShow:
    """`/session` (no arg) and `/session show` print the summary card."""

    def test_bare_session_shows_summary(self, echoed, fake_memory, fake_usage):
        new_ctx = _handle_session_command("/session", "ctx-active-001")
        assert new_ctx == "ctx-active-001"  # context unchanged
        joined = "\n".join(echoed)
        assert "Context:" in joined
        assert "ctx-active-001" in joined
        assert "hephaestus" in joined
        assert "1,234 in" in joined or "1234 in" in joined.replace(",", "")

    def test_explicit_show(self, echoed, fake_memory, fake_usage):
        _handle_session_command("/session show", "ctx-active-001")
        joined = "\n".join(echoed)
        assert "Messages:" in joined
        assert "6" in joined  # 4 hephaestus + 2 metis


class TestList:
    """`/session list` enumerates known contexts, marking the active one."""

    def test_marks_active_context(self, echoed, fake_memory):
        _handle_session_command("/session list", "ctx-active-001")
        joined = "\n".join(echoed)
        assert "Known contexts" in joined
        # The active context_id (truncated to 8 chars) should appear with the *
        active_line = next(line for line in echoed if "ctx-acti" in line)
        assert "*" in active_line

    def test_empty_store_message(self, echoed, fake_memory):
        fake_memory["contexts"] = []
        _handle_session_command("/session list", "ctx-active-001")
        joined = "\n".join(echoed)
        assert "No stored contexts" in joined


class TestFork:
    """`/session fork` clones to a new uuid and returns the new context_id."""

    def test_fork_returns_new_context_and_echoes_count(self, echoed, fake_memory):
        new_ctx = _handle_session_command("/session fork", "ctx-active-001")
        assert new_ctx != "ctx-active-001"
        assert len(new_ctx) == 32  # uuid4().hex
        joined = "\n".join(echoed)
        assert "Forked" in joined
        assert "6 messages cloned" in joined

    def test_fork_collision_keeps_old_context(self, echoed, fake_memory):
        fake_memory["clone_should_raise"] = True
        new_ctx = _handle_session_command("/session fork", "ctx-active-001")
        assert new_ctx == "ctx-active-001"
        joined = "\n".join(echoed)
        assert "already has messages" in joined


class TestResume:
    """`/session resume <id>` switches to a prior context; prefix-resolved."""

    def test_resume_full_id(self, echoed, fake_memory):
        new_ctx = _handle_session_command("/session resume ctx-older-002", "ctx-active-001")
        assert new_ctx == "ctx-older-002"
        joined = "\n".join(echoed)
        assert "Resumed" in joined

    def test_resume_prefix_uniquely_resolves(self, echoed, fake_memory):
        new_ctx = _handle_session_command("/session resume ctx-older", "ctx-active-001")
        assert new_ctx == "ctx-older-002"

    def test_resume_no_arg_complains(self, echoed, fake_memory):
        new_ctx = _handle_session_command("/session resume", "ctx-active-001")
        assert new_ctx == "ctx-active-001"
        joined = "\n".join(echoed)
        assert "needs a context id" in joined

    def test_resume_unknown_prefix_leaves_state(self, echoed, fake_memory):
        new_ctx = _handle_session_command("/session resume nosuch", "ctx-active-001")
        assert new_ctx == "ctx-active-001"
        joined = "\n".join(echoed)
        assert "no context id matches" in joined

    def test_resume_same_context_is_noop_message(self, echoed, fake_memory):
        new_ctx = _handle_session_command("/session resume ctx-active-001", "ctx-active-001")
        assert new_ctx == "ctx-active-001"
        joined = "\n".join(echoed)
        assert "Already on" in joined


class TestResolvePrefix:
    """`_resolve_context_prefix` returns the canonical id or None."""

    def test_single_match(self):
        candidates = [("abc-111", 0, 0), ("def-222", 0, 0)]
        assert _resolve_context_prefix("abc", lambda limit: candidates) == "abc-111"

    def test_ambiguous_prefix_returns_none(self):
        candidates = [("abc-111", 0, 0), ("abc-222", 0, 0)]
        assert _resolve_context_prefix("abc", lambda limit: candidates) is None

    def test_no_match_returns_none(self):
        candidates = [("abc-111", 0, 0)]
        assert _resolve_context_prefix("xyz", lambda limit: candidates) is None


class TestUnknownSubcommand:
    def test_unknown_subcommand_complains(self, echoed, fake_memory):
        _handle_session_command("/session bogus", "ctx-active-001")
        joined = "\n".join(echoed)
        assert "unknown subcommand" in joined
