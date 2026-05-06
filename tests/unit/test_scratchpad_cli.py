"""Tests for the /scratchpad CLI slash command + streaming integration.

The data layer is tested in ``test_scratchpad.py``. These tests cover
the CLI handler ``_handle_scratchpad_command`` and the relative-time
formatter ``_format_scratchpad_age``.
"""

from __future__ import annotations

import time

import pytest

from hosts.cli.commands import _format_scratchpad_age, _handle_scratchpad_command
from kourai_common.scratchpad import get_scratchpad, reset_scratchpad


@pytest.fixture(autouse=True)
def _reset_pad():
    reset_scratchpad()
    yield
    reset_scratchpad()


@pytest.fixture
def echoed(monkeypatch):
    """Patch ``hosts.cli.commands._echo`` so we can capture writes.

    `_echo` writes to ``hosts.cli.rendering._raw_out``, captured
    pre-patch_stdout, so capsys / sys.stdout patches can't see it.
    Mirrors the established test pattern in test_cli.py.
    """
    captured: list[str] = []
    monkeypatch.setattr(
        "hosts.cli.commands._echo",
        lambda text="", nl=True: captured.append(text),
    )
    return captured


def _run(prompt: str, echoed: list[str]) -> str:
    """Run the handler and return concatenated echoed lines."""
    _handle_scratchpad_command(prompt)
    return "\n".join(echoed)


# ===================================================================
# _format_scratchpad_age — relative time labels
# ===================================================================


class TestFormatAge:
    def test_just_now_under_60s(self):
        assert _format_scratchpad_age(0) == "just now"
        assert _format_scratchpad_age(59) == "just now"

    def test_minutes(self):
        assert _format_scratchpad_age(60) == "1m ago"
        assert _format_scratchpad_age(125) == "2m ago"
        assert _format_scratchpad_age(3599) == "59m ago"

    def test_hours(self):
        assert _format_scratchpad_age(3600) == "1h ago"
        assert _format_scratchpad_age(7200) == "2h ago"
        assert _format_scratchpad_age(86399) == "23h ago"

    def test_days(self):
        assert _format_scratchpad_age(86400) == "1d ago"
        assert _format_scratchpad_age(86400 * 3) == "3d ago"


# ===================================================================
# /scratchpad — empty state
# ===================================================================


class TestScratchpadEmpty:
    def test_empty_buffer_message(self, echoed):
        out = _run("/scratchpad", echoed)
        assert "Scratchpad is empty" in out

    def test_empty_with_arg_says_no_buffered(self, echoed):
        out = _run("/scratchpad metis", echoed)
        assert "metis" in out
        assert "No buffered reasoning" in out


# ===================================================================
# /scratchpad — list summary
# ===================================================================


class TestScratchpadList:
    def test_lists_agents_with_entries(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "Plan:\n- step 1\n- step 2")
        pad.add("techne", "TODO:\n- fix x\n- ship y")
        out = _run("/scratchpad", echoed)
        assert "metis" in out
        assert "techne" in out
        # Hint to drill down is shown.
        assert "/scratchpad <agent>" in out

    def test_list_shows_entry_count(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "first")
        pad.add("metis", "second")
        pad.add("metis", "third")
        out = _run("/scratchpad", echoed)
        assert "3 entries" in out

    def test_list_singular_for_one_entry(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "x")
        out = _run("/scratchpad", echoed)
        assert "1 entry" in out


# ===================================================================
# /scratchpad <agent>
# ===================================================================


class TestScratchpadByAgent:
    def test_shows_buffered_text(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "Plan:\n- decompose login\n- pick OAuth provider")
        out = _run("/scratchpad metis", echoed)
        assert "decompose login" in out
        assert "pick OAuth provider" in out

    def test_oldest_first_chronological(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "ALPHA")
        time.sleep(0.001)
        pad.add("metis", "BETA")
        out = _run("/scratchpad metis", echoed)
        assert out.index("ALPHA") < out.index("BETA")

    def test_agent_name_lowercased(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "case-insensitive lookup")
        out = _run("/scratchpad METIS", echoed)
        assert "case-insensitive lookup" in out


# ===================================================================
# /scratchpad clear
# ===================================================================


class TestScratchpadClear:
    def test_clear_all(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "x")
        pad.add("techne", "y")
        out = _run("/scratchpad clear", echoed)
        assert "Cleared scratchpad for all agents" in out
        assert pad.agents() == []

    def test_clear_one_agent_leaves_others(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "x")
        pad.add("techne", "y")
        out = _run("/scratchpad clear metis", echoed)
        assert "metis" in out
        assert pad.entries("metis") == []
        assert len(pad.entries("techne")) == 1

    def test_clear_lowercases_agent(self, echoed):
        pad = get_scratchpad()
        pad.add("metis", "x")
        _run("/scratchpad clear METIS", echoed)
        assert pad.entries("metis") == []
