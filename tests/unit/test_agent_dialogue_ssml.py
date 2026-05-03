"""M18 Phase 2 rollout: shared dialogue dicts must be SSML-wrapped.

`HANDOFF_LINES`, `HANDOFF_FALLBACKS`, and `VICTORY_LINES` (in
`shared/src/kourai_common/agents.py`) flow through both the CLI display
chokepoint (`_comms_window` strips) and the TTS engine path
(`RealtimeTTSEngine.speak` strips). Producers emit SSML; both consumer
boundaries strip cleanly. These tests defend the contract:

- every dialogue line is well-formed `<speak>...</speak>`
- stripped form is non-empty (catches accidentally empty bodies)
- stripped form has no leftover `<` / `>` (catches mismatched wrappers)
"""

from __future__ import annotations

import pytest

from kourai_common.agents import (
    AGENT_METADATA,
    AGENT_QUOTES,
    HANDOFF_FALLBACKS,
    HANDOFF_LINES,
    VICTORY_LINES,
)
from kourai_common.ssml import strip_ssml


def _all_lines():
    """Yield (source_name, key, line) for every dialogue string."""
    for key, lines in HANDOFF_LINES.items():
        for line in lines:
            yield ("HANDOFF_LINES", key, line)
    for agent, lines in HANDOFF_FALLBACKS.items():
        for line in lines:
            yield ("HANDOFF_FALLBACKS", agent, line)
    for agent, lines in VICTORY_LINES.items():
        for line in lines:
            yield ("VICTORY_LINES", agent, line)
    for agent, lines in AGENT_QUOTES.items():
        for line in lines:
            yield ("AGENT_QUOTES", agent, line)
    for agent, meta in AGENT_METADATA.items():
        for line in meta.get("user_quotes", []):
            yield ("user_quotes", agent, line)


_ALL = list(_all_lines())


@pytest.mark.parametrize("source,key,line", _ALL)
def test_line_is_speak_wrapped(source, key, line):
    assert line.startswith("<speak>"), f"{source}[{key}] not wrapped: {line!r}"
    assert line.endswith("</speak>"), f"{source}[{key}] not closed: {line!r}"


@pytest.mark.parametrize("source,key,line", _ALL)
def test_line_strips_to_nonempty(source, key, line):
    stripped = strip_ssml(line)
    assert stripped, f"{source}[{key}] strips to empty: {line!r}"


@pytest.mark.parametrize("source,key,line", _ALL)
def test_stripped_line_has_no_xml_chars(source, key, line):
    stripped = strip_ssml(line)
    # The strip layer must remove every tag — leftover < or > would
    # render literally in the comms window or hit Kokoro as garbage.
    assert "<" not in stripped, f"{source}[{key}] strip leaks <: {stripped!r}"
    assert ">" not in stripped, f"{source}[{key}] strip leaks >: {stripped!r}"
