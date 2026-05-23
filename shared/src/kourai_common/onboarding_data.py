"""Shared onboarding option lists across CLI / GUI / VN hosts.

The canonical 5-role set is ``divine | mortal | hero | devoted | name_only``.
Legacy CLI IDs ``master`` / ``devoted`` and ``casual`` / ``name_only``
must be treated as aliases by any code that branches on persisted profile
values (``hosts/cli/onboarding.py``'s Puck handoff keeps both forms in
its match set for backward compatibility).

Each ``OnboardingChoice`` carries both ``label`` (short button-friendly
text the GUI uses) and ``description`` (longer prompt the CLI shows
under each numbered choice). Hosts read whichever field fits their surface.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnboardingChoice:
    """One pickable option in the onboarding flow."""

    id: str
    label: str
    description: str


ROLE_OPTIONS: list[OnboardingChoice] = [
    OnboardingChoice(
        id="divine",
        label="As a God among mortals",
        description="A God among mortals — divine honorifics, reverent tone",
    ),
    OnboardingChoice(
        id="mortal",
        label="As a fellow artisan",
        description="A fellow artisan — casual, warm, collaborative tone",
    ),
    OnboardingChoice(
        id="hero",
        label="As a proven champion",
        description="A proven champion — comradely respect, earned trust",
    ),
    OnboardingChoice(
        id="devoted",
        label="As their beloved master",
        description="Their beloved master — devoted, formal, adoring",
    ),
    OnboardingChoice(
        id="name_only",
        label="Just by name",
        description="Just by name — natural, no special treatment",
    ),
]

PRONOUN_OPTIONS: list[OnboardingChoice] = [
    OnboardingChoice(id="he/him", label="he/him", description="he/him"),
    OnboardingChoice(id="she/her", label="she/her", description="she/her"),
    OnboardingChoice(id="they/them", label="they/them", description="they/them"),
    OnboardingChoice(id="", label="skip", description="skip / prefer not to say"),
]

EXPERIENCE_OPTIONS: list[OnboardingChoice] = [
    OnboardingChoice(
        id="focused",
        label="Focused",
        description="Focused — minimal game mechanics, terminal-first coding flow",
    ),
    OnboardingChoice(
        id="gamified",
        label="Gamified",
        description="Gamified — full forge systems, relationship progression, and lore",
    ),
]


__all__ = [
    "EXPERIENCE_OPTIONS",
    "PRONOUN_OPTIONS",
    "ROLE_OPTIONS",
    "OnboardingChoice",
]
