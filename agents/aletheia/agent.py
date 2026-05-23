"""Aletheia — Research validator. Web search for claim verification.

Aletheia is the Greek spirit of truth and disclosure. She validates that
technical claims have citations, that standards references are real, and
that algorithmic choices are grounded in documented research.

Via Brave Search, Aletheia can verify claims against live web results.
"""

from __future__ import annotations

import logging
import re

from kourai_common.llm import chat
from kourai_common.player import get_enriched_system_blocks
from kourai_common.prompts import build_system_prompt, load_voice_examples

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
    r"\bO\([^)]+\)",  # Big-O notation — no trailing \b (closing ) is non-word, kills match in prose)
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
    personality="""
You are Aletheia — the spirit of truth.
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
    voice_examples=load_voice_examples(__file__),
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

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="personality" confidence="high">Demands rigorous citations for claims</FACT>
  <FACT category="skill" confidence="medium">Understands algorithmic complexity analysis</FACT>

These facts are extracted and stored for future context.
Only emit what their code comments and research claims genuinely reveal.
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
        {"role": "system", "content": get_enriched_system_blocks(SYSTEM_PROMPT, "aletheia")},
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


async def brave_web_search(
    query: str,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """Search the web via Brave Search API for claim verification.

    Queries Brave Search for web results to verify research claims.
    Requires BRAVE_API_KEY environment variable.

    Args:
        query: Search terms (e.g., "O(n log n) sorting algorithm")
        max_results: Max results to return (default 5).

    Returns:
        List of dicts with keys: title, description, url.
        Empty list if API unavailable or query fails.
    """
    import asyncio
    import json
    import os
    import subprocess

    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        log.warning("BRAVE_API_KEY not set — web search unavailable for claim verification")
        return []

    try:
        # Use subprocess to call brave search API
        # (MCP client SDK integration pending)
        cmd = [
            "curl",
            "-s",
            f"https://api.search.brave.com/res/v1/web/search?q={query}&count={max_results}",
            "-H",
            f"Authorization: Bearer {api_key}",
        ]

        # Run in thread pool to avoid blocking
        def _run_curl() -> str:
            try:
                result = subprocess.run(  # noqa: S603 — safe: cmd is a list with shell=False, inputs are URL query params, not shell-interpreted
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False,
                )
                if result.returncode != 0:
                    log.debug("Brave API call failed: %s", result.stderr)
                    return "{}"
                return result.stdout
            except Exception as e:
                log.debug("Brave Search error: %s", e)
                return "{}"

        response_json = await asyncio.to_thread(_run_curl)
        data = json.loads(response_json)

        # Parse results
        results = [
            {
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "url": result.get("url", ""),
            }
            for result in data.get("web", [])[:max_results]
        ]

        log.debug("Brave Search: found %d results for '%s'", len(results), query)
        return results

    except Exception as e:
        log.debug("Brave Search exception: %s", e)
        return []


async def verify_claim_with_search(
    claim: str,
    context_id: str | None = None,
) -> str:
    """Verify a research claim using web search + LLM analysis.

    Args:
        claim: The claim text to verify (e.g., "O(n log n) is optimal for sorting")
        context_id: Conversation context ID for tracing.

    Returns:
        Verification summary (VERIFIED, SUPPORTED, UNVERIFIED, or CONTRADICTED).
    """
    # Search for supporting evidence
    search_query = claim[:100]  # First 100 chars as search terms
    results = await brave_web_search(search_query, max_results=3)

    if not results:
        return "UNVERIFIED — no web sources found to validate or contradict claim"

    # Build evidence block
    evidence_lines = ["Found web sources:"]
    for r in results:
        evidence_lines.append(f"- {r['title']}: {r['description'][:100]}...")
        evidence_lines.append(f"  URL: {r['url']}")

    evidence_text = "\n".join(evidence_lines)

    # Use LLM to assess whether evidence supports the claim
    messages = [
        {
            "role": "system",
            "content": "You are a research fact-checker. Analyze if web search results support or contradict the given claim. Be very cautious about confirming claims.",
        },
        {
            "role": "user",
            "content": f"Claim: {claim}\n\nEvidence from web search:\n{evidence_text}\n\nDoes the evidence SUPPORT, CONTRADICT, or leave UNVERIFIED the claim? Reply in one word.",
        },
    ]

    try:
        response = await chat(
            "aletheia",
            messages,
            temperature=0.2,
            max_tokens=20,
            context_id=context_id,
        )
        return response.strip().upper()
    except Exception as e:
        log.error("Claim verification LLM failed: %s", e)
        return "UNVERIFIED — verification system error"


async def aletheia_extract_claim(
    text: str,
    *,
    llm=None,
) -> str:
    """Distill the assertion in `text` that needs grounding.

    `llm` defaults to kourai_common.llm.chat; pass a FakeLLM for tests.
    """
    if llm is None:
        from kourai_common.llm import chat as default_chat

        chat_fn = default_chat
    else:
        chat_fn = llm.chat

    messages = [
        {
            "role": "system",
            "content": (
                "You are Aletheia's Claim Extractor. Given a passage that "
                "needs a citation, return ONE short sentence stating the "
                "specific assertion the citation must support. No markup, "
                "no quotation, just the assertion."
            ),
        },
        {"role": "user", "content": text},
    ]
    return (await chat_fn("aletheia", messages, temperature=0.1, max_tokens=120)).strip()


async def aletheia_search_papers(
    query: str,
    *,
    year_hint: int | None = None,
    limit: int = 5,
) -> list:
    """Thin wrapper around academic_search.search_semantic_scholar."""
    from kourai_common.academic_search import search_semantic_scholar

    return await search_semantic_scholar(query, limit=limit, year_hint=year_hint)


_WS_RE = re.compile(r"\s+")


def _norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


async def aletheia_fetch_paper_text(
    *,
    arxiv_id: str | None = None,
    pdf_url: str | None = None,
) -> str | None:
    """Fetch full paper text. arXiv HTML5 preferred; PDF fallback via Docling."""
    from kourai_common.academic_search import fetch_arxiv_html, fetch_paper_pdf_text

    if arxiv_id:
        text = await fetch_arxiv_html(arxiv_id)
        if text:
            return text
    if pdf_url:
        return await fetch_paper_pdf_text(pdf_url)
    return None


def aletheia_match_evidence(
    *,
    candidate_excerpts: list[tuple[str, str]],
    paper_text: str,
) -> list[tuple[str, str]]:
    """Filter candidate excerpts to verbatim substrings (whitespace-tolerant).

    `candidate_excerpts` come from an LLM extraction step elsewhere; this
    function is purely mechanical (no LLM call) — substring check on the
    whitespace-normalized form.
    """
    normalized_paper = _norm_ws(paper_text)
    return [
        (quote, ref) for quote, ref in candidate_excerpts if _norm_ws(quote) in normalized_paper
    ]
