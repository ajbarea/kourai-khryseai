"""``PAUSE: <preference_kind> "<question>"`` runtime control token (M17 Phase 1).

Mirror of M13's ``CONFIRM_ORDER: <tier> "<read-back>"`` token, used by
specialists (today: Metis) to mark a clarifying question as a one-time-
per-project preference. The closed Phase 1 vocabulary lives in
``kourai_common.hooks_interaction.VALID_PREFERENCE_KINDS``.

Token shape::

    PAUSE: <preference_kind> "<question>"

The token is emitted on its own line at the END of the agent's response.
Anything before the line is the agent's normal artifact prose; the
parser strips the line and returns the clean text plus the parsed kind
and question, ready for the executor's pause path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kourai_common.hooks_interaction import VALID_PREFERENCE_KINDS

# The PAUSE line is matched at the end of the response. ``re.MULTILINE``
# lets ``^`` anchor on the line start; ``re.DOTALL`` is NOT used because
# the question is single-line (multi-line questions are out of Phase 1
# scope — the LLM is told one short question).
_PATTERN = re.compile(
    r'^PAUSE:\s*(\w+)\s+"([^"\n]+)"\s*$',
    re.MULTILINE,
)


@dataclass(frozen=True)
class PauseTag:
    """Decoded ``PAUSE`` token, ready for executor handoff."""

    preference_kind: str
    question: str
    clean_text: str  # original text with the PAUSE line stripped


def extract_pause_tag(text: str) -> PauseTag | None:
    """Parse a trailing ``PAUSE: <kind> "<question>"`` line, if present.

    Returns ``None`` when the text contains no PAUSE token, when the
    token is malformed, or when ``preference_kind`` is not in the
    Phase 1 closed vocabulary. Unknown kinds fail closed — a malformed
    classification poisons the fact graph, so we'd rather drop the
    pause than synthesise garbage.
    """
    match = _PATTERN.search(text)
    if not match:
        return None

    kind = match.group(1).strip()
    if kind not in VALID_PREFERENCE_KINDS:
        return None

    question = match.group(2).strip()
    if not question:
        return None

    clean = (text[: match.start()] + text[match.end() :]).rstrip()
    return PauseTag(preference_kind=kind, question=question, clean_text=clean)
