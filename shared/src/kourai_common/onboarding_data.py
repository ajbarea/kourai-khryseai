"""Shared onboarding option lists across CLI / GUI / VN hosts.

Replaces the divergent per-host lists. Pre-this-module, CLI had four
roles (``divine | mortal | master | casual``) with ``(id, description)``
tuples while GUI + VN had five (``divine | mortal | hero | devoted |
name_only``) with ``(id, label, description)`` triples — same player
switching hosts saw different choices, sometimes incompatible IDs.

The 5-role set wins because two of three hosts already use it. CLI
gains ``hero``; legacy CLI IDs ``master`` / ``casual`` should be
treated as aliases for ``devoted`` / ``name_only`` in any code that
branches on persisted profile values (``hosts/cli/onboarding.py``'s
Puck handoff line keeps both forms in its match set for backward
compatibility).

Each ``OnboardingChoice`` carries both ``label`` (short button-friendly
text the GUI uses) and ``description`` (longer prompt the CLI shows
under each numbered choice). Hosts that only need one read whichever
field fits their surface.
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
