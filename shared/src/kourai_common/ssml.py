"""Defensive SSML strip helper.

Kept as infrastructure even though no producer in the current codebase
emits SSML — defends against any future LLM-emitted markup (the LLM
might decide on its own to wrap text in `<speak>` or other XML-shaped
tags) leaking literal angle brackets into the comms window or into
Kokoro's phonemizer.

research(2026-05, walked back from earlier plan): The original M18 Phase 2
plan was producer-side SSML emission anticipating an M6 ElevenLabs swap.
Verifying against ElevenLabs docs at decision time would have shown:

- Eleven v3 (the M6 high-impact-line target per VOICE_CASTING_PLAN.md)
  does NOT support SSML break tags. Their idiom is `[bracket]` audio
  tags (`[whispers]`, `[sarcastic]`) plus ellipses + natural punctuation.
- Eleven Flash V2.5 (the M6 routine-dialogue target) technically supports
  break tags but ElevenLabs warns against them ("too many cause
  instability") and recommends ellipses/dashes anyway.
- Kokoro mainline still has zero native SSML (`hexgrad/kokoro#36` open).

So SSML envelopes were the wrong markup for both Kokoro AND the planned
M6 target. PRs #149/#150 (and proposed #151) were reverted in favor of
plain text with rich punctuation — periods, commas, ellipses, em-dashes
already create natural pauses in Kokoro and ElevenLabs alike.

The helper stays so any future producer that DOES emit SSML (or any
other XML-shaped markup that arrives via LLM output) doesn't bleed
literal `<tag>` characters to the player. `_comms_window`, the TTS
engine's `speak()` and `synthesize_to_wav()`, and the maiden-card +
greeting display sites all call this defensively. strip_ssml is
idempotent and has a fast plain-text path (`if "<" not in text:
return text`) so the cost on plain input is one substring check.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

# defusedxml hardens stdlib's ElementTree against billion-laughs / XXE on
# LLM-emitted SSML — recommended by Python docs through 2026 even though
# its module-level patch shim is deprecated. Only the parse path is
# untrusted; Element type hints use the stdlib class.
from defusedxml.ElementTree import ParseError, fromstring

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

logger = logging.getLogger(__name__)

# Tags that imply audible whitespace when stripped — `<break>` adds a pause,
# so the text on either side shouldn't run together. Keep the gap tiny so
# Kokoro's own sentence chunker doesn't read it as a punctuation marker.
_BREAK_LIKE_TAGS = frozenset({"break", "p", "s"})

_TAG_RE = re.compile(r"<[^>]+>")


def strip_ssml(text: str) -> str:
    """Return the text content of an SSML document, dropping all tags.

    Plain text passes through unchanged. Well-formed SSML is parsed via
    :mod:`xml.etree.ElementTree` so structural tags become spaces and the
    payload reads cleanly. Malformed input falls back to a regex strip —
    a producer bug shouldn't kill TTS, just skip the prosody hints.
    """
    if not text or "<" not in text:
        return text

    cleaned = _strip_via_etree(text)
    if cleaned is not None:
        return cleaned

    # Fallback: regex tag scrub. Less precise (no break-tag whitespace) but
    # always returns *something* synthesizable.
    logger.debug("SSML parse failed, falling back to regex strip")
    return _TAG_RE.sub(" ", text).strip()


def _strip_via_etree(text: str) -> str | None:
    """Parse with defusedxml's safe ET and concatenate text nodes. None on failure."""
    # ET expects a single root. `<speak>...</speak>` already provides one;
    # bare fragments need a synthetic wrapper.
    wrapped = text if text.lstrip().startswith("<speak") else f"<speak>{text}</speak>"
    try:
        root = fromstring(wrapped)
    except ParseError:
        return None
    parts: list[str] = []
    _walk(root, parts)
    return _collapse_whitespace("".join(parts))


def _walk(node: Element, parts: list[str]) -> None:
    """Depth-first text accumulator. Emits a space for break-like tags so
    `<break/>` between two sentences doesn't glue them.
    """
    tag_local = node.tag.rsplit("}", 1)[-1].lower()  # strip namespace
    if tag_local in _BREAK_LIKE_TAGS:
        parts.append(" ")
    if node.text:
        parts.append(node.text)
    for child in node:
        _walk(child, parts)
        if child.tail:
            parts.append(child.tail)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
