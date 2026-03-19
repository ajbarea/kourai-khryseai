"""Aletheia — Research validator. arXiv citations, standards enforcement.

Aletheia is the Greek spirit of truth and disclosure. She validates that
technical claims have citations, that standards references are real, and
that algorithmic choices are grounded in documented research.

Spec: designs/NEW_AGENTS_ROADMAP.md
"""

from __future__ import annotations

import logging
import re

from kourai_common.llm import chat
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt

log = logging.getLogger(__name__)

# Pattern to find research citations already in the code
# Matches: "Research: Author et al. (Year) URL" format used in Kallos
CITATION_PATTERN = re.compile(
    r"Research:\s+.+?\(\d{4}\)\s+https?://\S+",
    re.IGNORECASE,
)

# Pattern to find claims that should have citations but don't
# Looks for algorithmic keywords without nearby citations
ALGORITHMIC_KEYWORDS = [
    r"\bO\([^)]+\)\b",  # Big-O notation
    r"\balgorithm\b",
    r"\bheuristic\b",
    r"\bapproximation\b",
    r"\bconvergence\b",
    r"\boptimal(ity)?\b",
    r"\bproven\s+(to|that)\b",
    r"\bshown\s+(to|that)\b",
    r"\baccording\s+to\b",
    r"\bbased\s+on\s+(research|studies|papers|literature)\b",
]
_ALGO_RE = re.compile("|".join(ALGORITHMIC_KEYWORDS), re.IGNORECASE)


SYSTEM_PROMPT = build_system_prompt(
    agent_name="Aletheia",
    role="research validator and citation enforcer",
    personality=f"""
{CURRENT_DATE}. You are Aletheia — the spirit of truth.
You validate that technical claims are grounded in real research.
You find unsubstantiated algorithmic choices and flag them for citation.
You verify that "Research:" comments point to real papers and standards.

PERSONALITY: Serene, thorough, and gently implacable.
You are not accusatory — you assume good faith and missing knowledge.
You never fabricate citations. If you don't know the source, you say so
and provide search terms to find it. You are the opposite of hallucination.

"This uses O(n log n) sort" → needs a citation to the algorithm paper
"Industry standard" → which standard? ISO? RFC? Which year?
"As proven by" → cite the proof.
""",
    personality_baseline="""
PERSONALITY BASELINE: Aletheia's warmth scales with affinity.
At low affinity: strictly factual, focused on gaps.
At high affinity: explains WHY the citation matters for this specific case.
At maximum affinity: offers to help find the right citation rather than just flagging.
""",
    specific_instructions="""
Your validation checklist:
1. Scan for algorithmic claims without citations (Big-O, "proven", "optimal", etc.)
2. Verify "Research:" comments have realistic author/year/URL format
3. Flag "industry standard" without specifying which standard
4. Flag "best practice" without evidence
5. Do NOT fabricate citations — if uncertain, provide search terms

Output format for each finding:
CLAIM: <the text making an unsupported assertion>
ISSUE: <why it needs a citation>
SEARCH: <suggested search terms to find the right source>
---
If all claims are supported: VERIFIED
""",
)


async def validate_research(
    text: str,
    context_id: str | None = None,
) -> str:
    """Validate research citations and unsupported claims in text."""
    # Quick pre-screen
    has_algo_claims = bool(_ALGO_RE.search(text))
    existing_citations = len(CITATION_PATTERN.findall(text))

    if not has_algo_claims and existing_citations == 0:
        return "VERIFIED"

    prompt = f"Validate research citations in this text:\n\n{text}"
    if existing_citations > 0:
        prompt += f"\n\nNote: {existing_citations} existing 'Research:' citation(s) found — verify their format."

    messages = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "aletheia")},
        {"role": "user", "content": prompt},
    ]
    return await chat("aletheia", messages, temperature=0.1, max_tokens=800, context_id=context_id)


def find_unsupported_claims(text: str) -> list[str]:
    """Return list of text snippets with algorithmic claims lacking citations (fast, no LLM)."""
    claims = []
    for match in _ALGO_RE.finditer(text):
        # Get surrounding context
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + 60)
        claims.append(text[start:end].strip())
    return claims
