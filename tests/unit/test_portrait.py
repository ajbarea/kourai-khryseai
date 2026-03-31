"""Unit tests for kourai_common.companion portrait inference.

Covers infer_portrait_state() and the PORTRAIT_STATES constant.
"""

from __future__ import annotations

import pytest

from kourai_common.companion import PORTRAIT_STATES, infer_portrait_state

# ── Neutral fallback ──────────────────────────────────────────────────────────


def test_neutral_for_empty_text() -> None:
    assert infer_portrait_state("techne", "") == "neutral"


def test_neutral_for_unknown_agent() -> None:
    assert infer_portrait_state("unknown_agent", "Hello there.") == "neutral"


def test_neutral_for_unmatched_text() -> None:
    assert infer_portrait_state("kallos", "The sky is blue.") == "neutral"


# ── Vulnerable priority ───────────────────────────────────────────────────────


def test_vulnerable_on_i_care() -> None:
    assert infer_portrait_state("techne", "I care about your progress.") == "vulnerable"


def test_vulnerable_on_i_appreciate() -> None:
    assert infer_portrait_state("kallos", "I appreciate your effort here.") == "vulnerable"


def test_vulnerable_on_means_a_lot() -> None:
    assert infer_portrait_state("metis", "That means a lot, honestly.") == "vulnerable"


def test_vulnerable_on_proud_of_you() -> None:
    assert infer_portrait_state("hephaestus", "I'm proud of you for this.") == "vulnerable"


def test_vulnerable_beats_tertiary() -> None:
    # "well done" is in BOTH vulnerable signals and hephaestus tertiary signals —
    # vulnerable must win.
    assert infer_portrait_state("hephaestus", "Well done, that's as expected.") == "vulnerable"


def test_vulnerable_case_insensitive() -> None:
    assert infer_portrait_state("mneme", "You Did Well on that last task.") == "vulnerable"


# ── Per-agent tertiary states ─────────────────────────────────────────────────


def test_hephaestus_fierce_on_approved() -> None:
    assert infer_portrait_state("hephaestus", "Approved — submit it.") == "fierce"


def test_hephaestus_fierce_on_masterwork() -> None:
    assert infer_portrait_state("hephaestus", "A true masterwork of the forge.") == "fierce"


def test_techne_fired_up_on_compiling() -> None:
    assert infer_portrait_state("techne", "Compiling your changes now.") == "fired_up"


def test_techne_fired_up_on_running() -> None:
    assert infer_portrait_state("techne", "Running the test suite...") == "fired_up"


def test_kallos_passionate_on_beautiful() -> None:
    assert infer_portrait_state("kallos", "Beautiful — the spacing is perfect.") == "passionate"


def test_kallos_passionate_on_style_violation() -> None:
    assert infer_portrait_state("kallos", "Style violation on line 12.") == "passionate"


def test_metis_calculating_on_planning() -> None:
    assert infer_portrait_state("metis", "Planning the migration in three phases.") == "calculating"


def test_metis_calculating_on_architecture() -> None:
    assert infer_portrait_state("metis", "The architecture here needs rethinking.") == "calculating"


def test_dokimasia_fierce_on_failure() -> None:
    assert infer_portrait_state("dokimasia", "Test failure on assertion line 42.") == "fierce"


def test_dokimasia_fierce_on_coverage() -> None:
    assert infer_portrait_state("dokimasia", "Coverage is at 61%, below threshold.") == "fierce"


def test_mneme_remembering_on_recall() -> None:
    assert infer_portrait_state("mneme", "I recall you prefer async patterns.") == "remembering"


def test_mneme_remembering_on_history() -> None:
    assert infer_portrait_state("mneme", "Looking at the history of this module.") == "remembering"


def test_puck_scheming_on_plan() -> None:
    assert infer_portrait_state("puck", "I have a plan for this, trust me.") == "scheming"


def test_puck_scheming_on_listen_up() -> None:
    assert infer_portrait_state("puck", "Listen up, boss — here's what we do.") == "scheming"


def test_cupid_determined_on_be_brave() -> None:
    assert infer_portrait_state("cupid", "You must be brave enough to say it.") == "determined"


def test_cupid_determined_on_love_requires() -> None:
    assert infer_portrait_state("cupid", "Love requires vulnerability, dear.") == "determined"


def test_aidos_cutting_on_vague() -> None:
    assert infer_portrait_state("aidos", "That response is vague and unhelpful.") == "cutting"


def test_aidos_cutting_on_hollow() -> None:
    assert infer_portrait_state("aidos", "Hollow phrasing with no substance.") == "cutting"


def test_aletheia_inspired_on_confirmed() -> None:
    assert infer_portrait_state("aletheia", "Confirmed — the docs back this claim.") == "inspired"


def test_aletheia_inspired_on_i_found() -> None:
    assert infer_portrait_state("aletheia", "I found a relevant paper on this.") == "inspired"


# ── PORTRAIT_STATES constant ──────────────────────────────────────────────────


def test_all_agents_present() -> None:
    expected = {
        "hephaestus",
        "techne",
        "kallos",
        "metis",
        "dokimasia",
        "mneme",
        "puck",
        "cupid",
        "aidos",
        "aletheia",
    }
    assert set(PORTRAIT_STATES.keys()) == expected


@pytest.mark.parametrize("agent", list(PORTRAIT_STATES.keys()))
def test_every_agent_has_neutral(agent: str) -> None:
    assert "neutral" in PORTRAIT_STATES[agent]


@pytest.mark.parametrize("agent", list(PORTRAIT_STATES.keys()))
def test_every_agent_has_vulnerable(agent: str) -> None:
    assert "vulnerable" in PORTRAIT_STATES[agent]


@pytest.mark.parametrize("agent", list(PORTRAIT_STATES.keys()))
def test_every_agent_has_exactly_three_states(agent: str) -> None:
    assert len(PORTRAIT_STATES[agent]) == 3


def test_aidos_has_cutting() -> None:
    assert "cutting" in PORTRAIT_STATES["aidos"]


def test_aletheia_has_inspired() -> None:
    assert "inspired" in PORTRAIT_STATES["aletheia"]


def test_puck_has_scheming_not_mischievous() -> None:
    assert "scheming" in PORTRAIT_STATES["puck"]
    assert "mischievous" not in PORTRAIT_STATES["puck"]


def test_cupid_has_determined_not_knowing() -> None:
    assert "determined" in PORTRAIT_STATES["cupid"]
    assert "knowing" not in PORTRAIT_STATES["cupid"]


def test_tertiary_states_are_canonical() -> None:
    """Verify all tertiary (non-neutral/vulnerable) state names match the guide."""
    canonical = {
        "hephaestus": "fierce",
        "techne": "fired_up",
        "kallos": "passionate",
        "metis": "calculating",
        "dokimasia": "fierce",
        "mneme": "remembering",
        "puck": "scheming",
        "cupid": "determined",
        "aidos": "cutting",
        "aletheia": "inspired",
    }
    for agent, expected_tertiary in canonical.items():
        states = PORTRAIT_STATES[agent]
        tertiary = states - {"neutral", "vulnerable"}
        assert tertiary == {expected_tertiary}, (
            f"{agent}: expected tertiary '{expected_tertiary}', got {tertiary}"
        )
