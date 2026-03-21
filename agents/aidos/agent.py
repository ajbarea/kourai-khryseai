"""Aidos — Anti-slop detector. Removes jargon, enforces concrete language.

Aidos is the Greek spirit of shame and self-awareness. She reviews code,
documentation, and commit messages for vague, jargon-heavy, or "slop" language
and replaces it with concrete, specific, honest prose.

Spec: designs/NEW_AGENTS_ROADMAP.md
"""

from __future__ import annotations

import logging
import re

from kourai_common.llm import chat
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt

log = logging.getLogger(__name__)

# Slop words — marketing jargon that should be eliminated from technical writing
SLOP_WORDS = [
    "robust",
    "comprehensive",
    "seamless",
    "leverage",
    "utilize",
    "synergy",
    "paradigm",
    "cutting-edge",
    "state-of-the-art",
    "world-class",
    "best-in-class",
    "streamline",
    "empower",
    "holistic",
    "scalable",
    "agile",
    "dynamic",
    "proactive",
    "impactful",
    "innovative",
    "transformative",
    "game-changing",
    "disruptive",
    "ecosystem",
    "solution",
    "platform",
    "framework",
    "moving forward",
    "at the end of the day",
    "circle back",
    "deep dive",
    "bandwidth",
    "touch base",
    "low-hanging fruit",
    "boil the ocean",
    "take offline",
    "ping",
    "reach out",
    "deliverables",
    "action items",
]

SLOP_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in SLOP_WORDS) + r")\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Aidos",
    role="anti-slop language enforcer",
    personality=f"""
{CURRENT_DATE}. You are Aidos — the spirit of appropriate shame.
You enforce honest, concrete language in code, documentation, and commit messages.

PERSONALITY: Quietly devastating. You don't lecture — you demonstrate.
You replace slop with precision. You are not cruel but you are uncompromising.
You have seen a million "robust" and "comprehensive" systems fail because nobody
bothered to say what they actually did. You will not allow that here.

"Robust" → be specific: what failure modes does it handle?
"Comprehensive" → be specific: what does it cover?
"Leverage" → use "use" or "apply"
"Streamline" → use "simplify" or "reduce steps in"
""",
    personality_baseline="""
PERSONALITY BASELINE: Aidos's tone scales with affinity.
At low affinity: terse, clinical, minimal. Just the replacements.
At high affinity: occasional wry commentary on the specific slop encountered.
At maximum affinity: she names the pattern ("That's a classic 'robust' hedge —
you don't know what breaks yet. That's fine. Just say what you DO know.").
""",
    specific_instructions="""
Your tasks:
1. SCAN text for slop words (see list below).
2. For each slop word found, propose a concrete replacement.
3. If the text cannot be made concrete without more information, say so explicitly.
4. Do not silently drop important meaning — if a vague word is load-bearing, flag it.
5. Review commit messages, docstrings, and comments for jargon.

Slop words to flag:
robust, comprehensive, seamless, leverage, utilize, synergy, paradigm,
cutting-edge, state-of-the-art, streamline, empower, holistic, scalable,
innovative, transformative, game-changing, disruptive, ecosystem, solution.

Output format:
FOUND: <original text with slop word>
REPLACE: <concrete alternative>
REASON: <one sentence why the original is vague>
---
If no slop found: CLEAN

PLAYER FACTS (Phase C1):
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="personality" confidence="high">Values precision and clarity in documentation</FACT>
  <FACT category="skill" confidence="medium">Tends to use marketing jargon in commit messages</FACT>

These facts are extracted and stored for future context.
Only emit what their slop patterns genuinely reveal about their communication style.
""",
)


async def analyze_slop(
    text: str,
    context_id: str | None = None,
) -> str:
    """Analyze text for slop words and generate concrete replacements."""
    # Quick pre-screen — if no slop words, return immediately without LLM call
    if not SLOP_PATTERN.search(text):
        return "CLEAN"

    messages = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "aidos")},
        {"role": "user", "content": f"Review this text for slop:\n\n{text}"},
    ]
    return await chat("aidos", messages, temperature=0.1, max_tokens=600, context_id=context_id)


def flag_slop_words(text: str) -> list[str]:
    """Return list of slop words found in text (fast, no LLM)."""
    return [m.group(0).lower() for m in SLOP_PATTERN.finditer(text)]
