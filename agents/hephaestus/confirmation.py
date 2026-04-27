"""Forge Order Confirmation — tier classification and protocol parsing.

The CONFIRM_ORDER routing token is Hephaestus's pre-pipeline gate
(M13 — McDonald's-pattern read-back). Token shape::

    CONFIRM_ORDER: <tier> "<read-back>"

Where ``<tier>`` is one of ``clear`` / ``smart`` / ``clarify`` and the
``<read-back>`` is the quoted Hephaestus voice line shown to the
player as a speech card. The read-back is double-quoted so we can
carry multi-word natural language through a single token boundary
(no JSON escaping in the prompt — keeps the LLM's job simple).

Three tiers scale verbosity to ambiguity:

- **clear**    — order is unambiguous; ≤15 words; ends with a confirm cue.
- **smart**    — order is reasonable but Metis would suggest implicit
                 upgrades (edge cases, parity); read-back surfaces them.
- **clarify**  — order is genuinely ambiguous; ask ONE specific question.

The runtime classifier is LLM-driven (the routing call); this module
only decodes the response. Voice-quality regression lives in
``tests/integration/test_confirmation_voice.py`` (banned-phrase list).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

Tier = Literal["clear", "smart", "clarify"]
_VALID_TIERS: tuple[Tier, ...] = ("clear", "smart", "clarify")

# DOTALL so multi-line read-backs (rare but legal) are captured. The
# read-back is the LAST quoted span on the line — anchored with $ so
# trailing whitespace from the LLM doesn't trip the match.
_PATTERN = re.compile(
    r'^CONFIRM_ORDER:\s*(\w+)\s+"(.+)"\s*$',
    re.DOTALL,
)


@dataclass(frozen=True)
class ConfirmationResponse:
    """Decoded ``CONFIRM_ORDER`` token, ready for executor / CLI handoff."""

    tier: Tier
    read_back: str  # quoted Hephaestus voice line, sans surrounding quotes


def parse_confirmation_response(raw: str) -> ConfirmationResponse:
    """Decode a ``CONFIRM_ORDER: <tier> "<read-back>"`` line.

    Raises:
        ValueError: if the line isn't shaped like a CONFIRM_ORDER token,
            or the tier word isn't one of the three known values.
    """
    match = _PATTERN.match(raw.strip())
    if not match:
        raise ValueError(f"malformed CONFIRM_ORDER response: {raw!r}")
    tier_str, read_back = match.group(1), match.group(2)
    if tier_str not in _VALID_TIERS:
        raise ValueError(f"unknown tier {tier_str!r}; expected one of {_VALID_TIERS}")
    # mypy/ty: the membership check above narrows tier_str to Tier, but
    # neither tool propagates set-membership narrowing to Literal types
    # without `assert tier_str in (...)`. Cast keeps both happy.
    return ConfirmationResponse(tier=cast("Tier", tier_str), read_back=read_back)
