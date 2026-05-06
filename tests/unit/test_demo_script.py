"""Unit tests for the shared CSV-export demo script.

The Hephaestus → Metis canned scene previously lived in three places:
  * hosts/cli/demo.py (ANSI _echo lines, interactive)
  * hosts/gui/demo_client.py (recv_q event tuples, non-interactive)
  * hosts/vn/.../script_poster_demo.rpy (Ren'Py labels)

This module canonicalizes the dialogue beats, choice keys, and answer
responses; CLI and GUI iterate the same DemoTurn list and render in
their own primitives. VN's .rpy still hand-codes its own form (Ren'Py
can't cleanly import Python at script-time) but a header comment
cross-references the canonical source.
"""

from __future__ import annotations

import dataclasses

from kourai_common.demo_script import (
    CSV_DEMO_CHOICES,
    CSV_DEMO_TRIGGER,
    CSV_DEMO_TURNS,
    DemoChoice,
    DemoTurn,
    matches_csv_trigger,
)


def test_trigger_text_is_canonical_phrase():
    assert "csv" in CSV_DEMO_TRIGGER.lower()
    assert "events" in CSV_DEMO_TRIGGER.lower()


def test_turns_are_immutable_dataclass_instances():
    for turn in CSV_DEMO_TURNS:
        assert isinstance(turn, DemoTurn)
        # Frozen — both hosts iterate the same list, mutation in one
        # surface would silently change the other.
        try:
            turn.text = "mutated"  # type: ignore[misc]
        except dataclasses.FrozenInstanceError:
            continue
        raise AssertionError("DemoTurn should be frozen")


def test_turns_open_with_hephaestus_handoff():
    first = CSV_DEMO_TURNS[0]
    assert first.speaker == "hephaestus"
    assert first.kind == "speech"
    # The handoff line is the canonical "Metis! Draw up the plans..." beat.
    assert "metis" in first.text.lower()
    assert "plans" in first.text.lower()


def test_turns_include_metis_status_analysis():
    statuses = [t for t in CSV_DEMO_TURNS if t.speaker == "metis" and t.kind == "action"]
    assert statuses, "demo script should include at least one Metis action"
    assert any("events module" in t.text.lower() for t in statuses), (
        "Metis should explicitly call out events module analysis"
    )


def test_turns_include_input_required_question():
    # The pause beat is the screenshot moment — must exist exactly once,
    # spoken by Metis, mentioning the streaming-vs-memory trade-off.
    iq = [t for t in CSV_DEMO_TURNS if t.kind == "input_required"]
    assert len(iq) == 1
    assert iq[0].speaker == "metis"
    assert "stream" in iq[0].text.lower() or "chunk" in iq[0].text.lower()


def test_only_rationale_follows_input_required():
    # After the question, only rationale continuation lines may appear —
    # nothing should re-prompt with another question. Keeps the script
    # focused on a single decision moment.
    saw_iq = False
    for turn in CSV_DEMO_TURNS:
        if turn.kind == "input_required":
            saw_iq = True
            continue
        if saw_iq:
            assert turn.kind == "rationale", f"unexpected {turn.kind!r} after input_required"


def test_choices_cover_yes_no_explain():
    keys = {c.key for c in CSV_DEMO_CHOICES}
    assert {"y", "n", "?"}.issubset(keys)


def test_choices_have_response_turns():
    for choice in CSV_DEMO_CHOICES:
        assert isinstance(choice, DemoChoice)
        assert choice.label
        assert choice.response_turns, f"choice {choice.key} has no response_turns"


def test_choices_aliases_are_loose_match():
    yes = next(c for c in CSV_DEMO_CHOICES if c.key == "y")
    assert "yes" in yes.aliases
    assert "stream" in yes.aliases
    no = next(c for c in CSV_DEMO_CHOICES if c.key == "n")
    assert "no" in no.aliases


def test_matches_csv_trigger_is_loose():
    # CLI + GUI both call this — must accept rephrased prompts.
    assert matches_csv_trigger("implement csv export") is True
    assert matches_csv_trigger("Implement CSV export with tests") is True
    assert matches_csv_trigger("CSV streaming for events") is True
    assert matches_csv_trigger("write a sorting algorithm") is False


def test_pacing_ms_non_negative():
    for turn in CSV_DEMO_TURNS:
        assert turn.pacing_ms >= 0
