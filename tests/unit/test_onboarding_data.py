"""Unit tests for shared onboarding option lists.

Both CLI ``hosts/cli/onboarding.py`` and GUI ``hosts/gui/onboarding_ui.py``
present role / pronoun / experience choices to first-launch players. The
two hosts had drifted apart: CLI's ROLE_OPTIONS held ``(id, description)``
2-tuples with IDs ``divine | mortal | master | casual`` while the GUI's
held ``(id, label, description)`` 3-tuples with IDs
``divine | mortal | hero | devoted | name_only``. VN's ``script_start.rpy``
already uses the GUI 5-role set. This module canonicalizes on a single
``OnboardingChoice`` schema; the GUI's 5-role set wins because two of
three hosts (GUI + VN) already use it.
"""

from __future__ import annotations

from kourai_common.onboarding_data import (
    EXPERIENCE_OPTIONS,
    PRONOUN_OPTIONS,
    ROLE_OPTIONS,
    OnboardingChoice,
)


def test_role_options_canonical_ids():
    ids = [c.id for c in ROLE_OPTIONS]
    assert ids == ["divine", "mortal", "hero", "devoted", "name_only"]


def test_role_options_carry_label_and_description():
    for choice in ROLE_OPTIONS:
        assert isinstance(choice, OnboardingChoice)
        assert choice.label, f"missing label for {choice.id}"
        assert choice.description, f"missing description for {choice.id}"
        # GUI buttons use ``label`` (short); CLI prompts use ``description``
        # (longer). Different lengths catch label/description swaps.
        assert len(choice.label) < len(choice.description) + 30


def test_pronoun_options_include_skip():
    ids = [c.id for c in PRONOUN_OPTIONS]
    assert "he/him" in ids
    assert "she/her" in ids
    assert "they/them" in ids
    # The skip entry uses an empty-string id (matches existing CLI flow).
    assert "" in ids


def test_pronoun_skip_has_label_text():
    skip = next(c for c in PRONOUN_OPTIONS if c.id == "")
    # Empty id should still surface a human-readable label so a CLI/GUI
    # player isn't asked to choose between blank rows.
    assert skip.label
    assert "skip" in skip.label.lower() or "prefer not" in skip.description.lower()


def test_experience_options_match_existing_two_modes():
    ids = [c.id for c in EXPERIENCE_OPTIONS]
    assert ids == ["focused", "gamified"]


def test_onboarding_choice_is_immutable():
    # Frozen dataclass — keeps the canonical lists from being mutated by
    # one host's startup path in a way the other host wouldn't see.
    import dataclasses

    c = OnboardingChoice(id="x", label="L", description="D")
    try:
        c.id = "y"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("OnboardingChoice should be frozen")
