# Aletheia v2 — Citation Verification Agent (Design Spec)

**Status**: design approved 2026-05-23 (AJ) — implementation plan to follow.

**Author**: Claude (Opus 4.7) in collaboration with AJ.

**Path**: `docs/architecture/2026-05-23-aletheia-v2-citation-verification-design.md`

---

## 1. Problem

LLMs hallucinate academic citations at empirically observed rates of 14-95%
(CiteVerifier benchmark, May 2026). NeurIPS 2025 surfaced ~100 fabricated
citations across 53 published papers; ICLR 2026 reported 20% of sampled papers
contain at least one AI-generated hallucination. arXiv began a 1-year policy of
removing submissions with LLM errors. The "ACM venue rejected 100 camera-ready
papers" incident AJ flagged is one observable consequence.

A direct manifestation in this project: today's vFL PR #36 added an attribution
of arXiv:2502.03801 to "Yifei Liu et al." The actual first author is
**Heyi Zhang**. Five separate citation errors made it into the PR before a manual
audit; four would have been caught mechanically by the design specified here.

The kourai agent ecosystem already has **Aletheia** (`agents/aletheia/agent.py`)
in the role of "research validator and citation enforcer". Today she runs
[Brave Search](https://api.search.brave.com) for generic claim verification.
This spec specializes her to academic-source verification with a mechanical
artifact-first workflow that closes the categories of hallucination Brave can't
catch.

---

## 2. Goals + non-goals

**Goals:**

- Given a research claim, produce a citation backed by a verifiable on-disk
  artifact whose metadata fields are populated verbatim from official APIs.
- Mechanical (deterministic, code-verifiable) guarantees on the load-bearing
  parts: identity provenance, triangulation gate, verbatim-excerpt check,
  artifact-file existence.
- Probabilistic (LLM-judgment) pieces clearly labeled and surfaced for
  reviewer audit, not hidden.
- Default-deny: every error path returns `(None, ...)` rather than emitting
  an unverified citation.
- Per-project artifacts committed alongside code, reviewable in PR diffs.
- A scheduled audit pass to detect drift (retractions, metadata corrections).

**Non-goals (out of scope):**

- IEEE Xplore API integration (requires institutional API key application;
  multi-week calendar time). Defer until first concrete need.
- Google Scholar integration via paid SERP API ($50-300/mo recurring). The
  free S2 + arXiv + OpenAlex stack covers the same papers with ToS-compliant
  access; add Scholar as opt-in only if a developer specifically needs it.
- Replacing Aletheia's existing `validate_research()` / `find_unsupported_claims()`
  / `verify_claim_with_search()` — those stay for non-academic claim
  validation (industry standards, RFCs, generic web claims).
- Pre-commit hook with full LLM call. The May 2026 "10-second pre-commit
  rule" (devs bypass hooks >5s) rules this out; pre-commit gets only the
  mechanical file-existence check.
- A novel citation-graph or paper-recommendation system. Aletheia verifies
  citations the developer or another agent is about to make; she does not
  proactively suggest papers.
- "Find every citation in a paper and verify it" batch tool. The artifact
  audit pass covers re-verification of existing artifacts, which is the
  closest equivalent and what this design ships.

---

## 3. Research foundation (May 2026 state of the art)

| Topic | Source | Verified |
| --- | --- | --- |
| Cite-hallucination rates 14-95% | CiteVerifier benchmark, [CiteAudit paper](https://arxiv.org/abs/2602.23452) | yes |
| NeurIPS 2025 ~100 fabricated cites | [Fortune, Jan 2026](https://fortune.com/2026/01/21/neurips-ai-conferences-research-papers-hallucinations/), [TechCrunch](https://techcrunch.com/2026/01/21/irony-alert-hallucinated-citations-found-in-papers-from-neurips-the-prestigious-ai-conference/) | yes |
| ICLR 2026 20% hallucination sample | same | yes |
| Multi-component verification pipeline | [CiteAudit (arXiv:2602.23452)](https://arxiv.org/abs/2602.23452) — Claim Extractor → Retriever → Evidence Matcher → Reasoner → Judge | yes |
| ReAct as native tool use | [Agentic AI Design Patterns 2026](https://www.innovatrixinfotech.com/blog/agentic-ai-design-patterns-react-reflection-tool-use) — "modern LLMs handle reasoning-action loop natively through built-in tool calling" | yes |
| Semantic Scholar API: 200M+ papers, no auth | [api docs](https://api.semanticscholar.org/api-docs/) | yes |
| OpenAlex API: 250M+ works, key required from 2026-02-13 | [docs](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication) — 30-second signup | yes |
| arXiv API: free, no auth, Atom XML | [user manual](https://info.arxiv.org/help/api/user-manual.html) — HTML5 versions at `arxiv.org/html/{id}` since late 2023 | yes |
| MCP servers reliability: 71% median pass rate | [100-MCP stress test](https://www.digitalapplied.com/blog/mcp-server-reliability-100-server-stress-test-study), Feb-Apr 2026 | yes; supports direct-API over MCP-based approach |
| PDF→Markdown: Docling 0.877 on opendataloader-bench, Apache 2.0 | [Granite-Docling-258M, Jan 2026](https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion) | yes |
| PyMuPDF4LLM is AGPL-3.0 (transitive-dep risk) | [PyPI](https://pypi.org/project/PyMuPDF/) | yes — rejected for that reason |
| Title fuzzy threshold 0.92 = high-precision; 0.85-0.90 = "everything-is-duplicate" | [pdfmux benchmark](https://similarity-api.com/blog/speed-benchmarks), [Vikranth3140/Citation-Hallucination-Detection](https://github.com/Vikranth3140/Citation-Hallucination-Detection) (0.92 exact, 0.70 fuzzy hybrid) | yes |
| vcrpy + httpx async works | [vcrpy 8.0 changelog](https://vcrpy.readthedocs.io/en/latest/changelog.html) — "BREAKING fix for httpx support" landed | yes |
| Hard gate > soft gate for high-stakes | [vLLM HaluGate](https://blog.vllm.ai/2025/12/14/halugate.html), [Tool Receipts arXiv:2603.10060](https://arxiv.org/pdf/2603.10060) | yes — triangulation is a hard gate |
| Pre-commit "10-second rule" | [DeployHQ AI hooks guide](https://www.deployhq.com/git/ai-git-hooks) | yes — LLM calls belong in CI |
| Anthropic deterministic-grader guidance | [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | yes |
| CFF (Citation File Format) YAML schema | [citation-file-format.github.io](https://citation-file-format.github.io/) | yes — field-name source for artifact frontmatter |

---

## 4. Architecture

### 4.1 Component decomposition (CiteAudit-aligned, five tools)

Aletheia exposes `verify_and_cite(claim: str, hint: str | None = None) -> tuple[Citation | None, ArtifactPath | ConflictReport]`,
implemented as five composable tools that Claude's native tool-use loop calls
in sequence. No explicit ReAct prompting — Claude's built-in tool calling is
the loop.

| Tool | Role | Backed by |
| --- | --- | --- |
| `extract_claim(text)` | Claim Extractor — distills the assertion that needs grounding | LLM call (Aletheia, low temp) |
| `search_papers(query, year_hint)` | Retriever — top-K candidates with metadata + abstract | Semantic Scholar `/graph/v1/paper/search` |
| `fetch_paper_text(paper_id)` | Retriever, deeper — full paper text for excerpt extraction | arXiv HTML5 (preferred) → Docling for PDF |
| `match_evidence(claim, paper_text)` | Evidence Matcher — verbatim excerpts supporting claim | LLM call returning quotes; substring-verified mechanically |
| `triangulate(paper_meta)` | Judge — cross-source metadata agreement check | OpenAlex DOI lookup (or arXiv if no DOI) |

### 4.2 Data flow

```
verify_and_cite(claim, hint=None)
  │
  ├─ extract_claim → search_query  (LLM)
  │
  ├─ search_papers(query) → [candidates]  (S2 API)
  │
  ├─ rank candidates by abstract-match  (LLM, max 3 ReAct iterations)
  │      │
  │      └─ if no good match: return (None, NoCandidates)
  │
  ├─ fetch_paper_text(best_candidate)  (arXiv HTML5 → Docling)
  │      │
  │      └─ if all fetches fail: abstract-only fallback (artifact written
  │         with text_excerpts_unavailable=true, flagged) OR return (None, ...)
  │
  ├─ match_evidence(claim, paper_text) → [verbatim_excerpts]  (LLM + substring-check)
  │      │
  │      └─ if zero excerpts pass: return (None, NoSupportingExcerpts)
  │
  ├─ triangulate(paper_meta)  (OpenAlex)
  │      │
  │      ├─ if no DOI + no arxiv_id: skip, mark single_source_verified=true
  │      ├─ if decisive_field mismatch: return (None, TriangulationConflict)
  │      └─ if agree: continue
  │
  ├─ write_citation_artifact(meta, claim, excerpts, project_root)
  │      │
  │      └─ writes docs/citations/{slug}.md with frontmatter populated
  │         verbatim from API responses
  │
  └─ return (citation_string, artifact_path)
```

### 4.3 Module layout

| Module | Status | Purpose |
| --- | --- | --- |
| `agents/aletheia/agent.py` | extend existing | Add `verify_and_cite()` + the five tool implementations. Keep existing `validate_research`, `find_unsupported_claims`, `verify_claim_with_search` for non-academic claim verification. |
| `shared/src/kourai_common/academic_search.py` | new | `search_semantic_scholar()`, `fetch_arxiv_html()`, `fetch_paper_pdf()`, `lookup_openalex_by_doi()`, `lookup_arxiv_metadata()` — all `httpx.AsyncClient` + `tenacity` retries + polite User-Agent header with kourai's email. |
| `shared/src/kourai_common/citation_artifacts.py` | new | `write_citation_artifact()`, `read_citation_artifact()`, `slug_for_paper()`, `normalize_doi()`, `normalize_title()`, `normalize_surname()`. |
| `shared/src/kourai_common/triangulate.py` | new | `triangulate()` + helpers for field-level comparison. |
| `scripts/check_citations.py` | new | Mechanical pre-commit + CI check: every `# research:` / `[^cite]` resolves to an existing artifact. No LLM, <1s runtime. |
| `tests/unit/test_*.py` | new — five files | Unit tests for normalizers, artifact round-trip, triangulation, slug generation. Hypothesis property tests. |
| `tests/integration/test_academic_search.py` | new | vcrpy-cassette tests for the three APIs. |
| `tests/integration/test_aletheia_verify_cite.py` | new | End-to-end agent tests with FakeLLM + replayed cassettes. |
| `tests/nightly/test_api_contracts.py` | new | One real query per source; detects upstream schema drift. |

### 4.4 New runtime dependencies

| Package | License | Purpose | Wheel size |
| --- | --- | --- | --- |
| `httpx` | BSD-3 | Async HTTP client | small |
| `tenacity` | Apache 2.0 | Retry decorator | small |
| `rapidfuzz` | MIT | Title fuzzy match | ~2 MB |
| `docling` | Apache 2.0 | PDF → Markdown | ~50 MB |
| `pyyaml` | MIT | YAML frontmatter | small |
| `pydantic` | MIT | Frontmatter schema validation (probably already present) | already in kourai |

**Excluded** (with rationale):
- `pymupdf4llm` — AGPL-3.0 transitive dep risk for a project that might want
  permissive licensing later. Docling is a clean Apache 2.0 swap with
  comparable academic-PDF quality and CPU-friendly performance.
- `scholarly` — ToS-grey scraping of Google Scholar, CAPTCHA-prone, not
  recommended for production.
- Any paid SERP API (SerpAPI / ScraperAPI) — $50-300/mo recurring; free
  alternatives cover the same papers.
- MCP servers (paper-search-mcp, scholar-mcp, arxiv-mcp-server) — May 2026
  100-MCP study shows median 71% pass rate; depending on three external
  MCPs has compound failure rate. Direct HTTP is more reliable.

---

## 5. The triangulation gate (load-bearing)

### 5.1 Cross-check source priority

1. **OpenAlex via DOI lookup** — when S2 returns a DOI (~95% of published papers)
2. **arXiv API via arxiv_id** — when no DOI but paper is on arXiv
3. **Skip with note** — preprint with neither DOI nor arxiv_id. In this case `triangulate()` returns `verified=true` with `notes=["no_secondary_source_available"]`, the artifact still gets written, and `single_source_verified: true` is recorded in the frontmatter so reviewers know to be more skeptical of this artifact.

### 5.2 Decisive fields (mismatch → REJECT)

| Field | Normalization | Match rule |
| --- | --- | --- |
| DOI | lowercase, strip `https://doi.org/` prefix | exact equality (DOI spec is case-insensitive) |
| arXiv ID | strip version suffix (`v1`, `v2`, ...) | exact equality |
| Title | Unicode NFKD, lowercase, strip punctuation, collapse whitespace | RapidFuzz `fuzz.ratio` ≥ 0.92 |
| First-author surname | NFKD, lowercase, strip accents/hyphens, drop suffixes ("Jr.") | exact equality |
| Year | none | exact equality |

### 5.3 Non-decisive fields (note in artifact, do not reject)

- Venue name (NeurIPS / NIPS / "Advances in Neural Information Processing
  Systems" are aliases; a small hand-maintained `VENUE_ALIASES` map covers
  ~15 common cases). Everything else gets recorded as a note: `venue_aliases:
  "S2 says X" vs "OpenAlex says Y"`.
- Author count beyond first (S2 sometimes truncates lists at 5-10).
- Author order beyond first author.

### 5.4 Rejection behavior

On any decisive-field mismatch, `verify_and_cite()` returns
`(None, TriangulationConflict)`. The `TriangulationConflict` lists
field-level disagreements with both sources' values. The caller can:

1. **Pick a different candidate** from the retrieval (Aletheia surfaces the
   top-K, not just top-1).
2. **Escalate to manual review** — print the conflict, ask AJ.
3. **Override** — invoke with `override=True`. Records
   `human_overridden: true` + a required `override_reason: "..."` in the
   artifact so the audit trail shows the decision.

### 5.5 Why this catches today's specific bug

The "Yifei Liu" misattribution would have been caught at the first-author
surname check. S2 returns first_author="Heyi Zhang"; OpenAlex returns
first_author="Heyi Zhang"; arXiv returns first_author="Heyi Zhang". An LLM-
generated "Liu" attribution does not match any of these, so the citation
is rejected before emission.

---

## 6. Artifact format

### 6.1 Path + slug

Per-project: `docs/citations/{slug}.md` in the consuming repo (vFL, phalanx-fl,
kourai-khryseai itself). Per-project rather than central kourai cache — artifacts
ship with the code, surface in PR diffs, get reviewed alongside the code that
cites them.

**Slug pattern**: `{paper_id}-{first_author_surname}-{title_keyword}.md`

| Example | Identifier | Slug |
| --- | --- | --- |
| arXiv preprint | arXiv:2502.03801 | `2502.03801-zhang-flpoison.md` |
| Published DOI | 10.1109/TSP.2022.3153135 | `10.1109_tsp.2022.3153135-pillutla-rfa.md` |
| Neither | first-author + title hash | `noid-blanchard-krum-c3d8.md` |

DOI slashes → underscores (filesystem safety). Title keyword: first significant
word from title (skip articles, prepositions, etc.), lowercase, alphanumeric only.

### 6.2 Frontmatter schema (YAML)

```yaml
---
# === Identity (verbatim from API; never LLM-generated) ===
title: "SoK: Benchmarking Poisoning Attacks and Defenses in Federated Learning"
authors:
  - Heyi Zhang
  - Yule Liu
  - Xinlei He
  - Jun Wu
  - Tianshuo Cong
  - Xinyi Huang
year: 2025
venue: "arXiv preprint"
venue_full: null  # optional alternative form

# === Identifiers (at least one of arxiv_id, doi required) ===
arxiv_id: "2502.03801"
doi: null

# === Resolvable URLs ===
urls:
  abs: https://arxiv.org/abs/2502.03801
  pdf: https://arxiv.org/pdf/2502.03801
  html: https://arxiv.org/html/2502.03801  # optional; preferred for parsing

# === Verification trail (Aletheia-populated) ===
sources_consulted: [semantic_scholar, openalex]
triangulation:
  primary_source: semantic_scholar
  secondary_source: openalex
  decisive_fields_agreed: true
  decisive_fields_checked: [title, first_author_surname, year, arxiv_id]
  notes: []
single_source_verified: false  # true iff triangulation was skipped
verified_by: aletheia
verified_at: "2026-05-23T17:42:00Z"
verification_version: "1.0"

# === Human override (optional) ===
human_overridden: false
override_reason: null

# === Claim linkage (LLM-generated; supported by verbatim excerpts below) ===
claim_supported: "FLPoison canonical headliner set includes ALIE, Fang, sign-flip"
---
```

Field names borrowed from CFF where applicable (`authors`, `title`, `year`,
`doi`). Aletheia-specific fields namespaced under their own keys so future CFF
tooling won't conflict.

### 6.3 Body sections (markdown)

```markdown
## Abstract

{verbatim from API — no LLM rewrite}

## Excerpts supporting the claim

> "We evaluate 15 representative poisoning attacks and 17 defense
> strategies in a unified benchmark..."
> (Abstract, paragraph 2)

> "Our headliner attack set includes ALIE [Baruch et al. 2019],
> Fang [Fang et al. 2020], and sign-flipping..."
> (Section 3.1, p. 4)

## Citation snippet

Heyi Zhang, Yule Liu, Xinlei He, Jun Wu, Tianshuo Cong, Xinyi Huang.
*SoK: Benchmarking Poisoning Attacks and Defenses in Federated Learning*.
arXiv:2502.03801 (2025).

## BibTeX

```bibtex
@article{zhang2025sok,
  title={SoK: Benchmarking Poisoning Attacks and Defenses in Federated Learning},
  author={Zhang, Heyi and Liu, Yule and He, Xinlei and Wu, Jun and Cong, Tianshuo and Huang, Xinyi},
  journal={arXiv preprint arXiv:2502.03801},
  year={2025}
}
```
```

### 6.4 Verbatim-excerpt rule (with whitespace tolerance)

Every excerpt in the "Excerpts supporting the claim" section must be a
verbatim substring of the paper's text (Docling-extracted Markdown).
Substring check applies *after* whitespace normalization on both sides
(collapse runs of whitespace, normalize line breaks to `\n`) to handle PDF
column breaks and hyphenation that would otherwise make a real quote fail
the check.

```python
def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def excerpt_verifies(claim_quote: str, paper_text: str) -> bool:
    return _normalize_whitespace(claim_quote) in _normalize_whitespace(paper_text)
```

If zero excerpts pass the check → triangulation soft-fails →
`(None, NoSupportingExcerpts)` is returned.

### 6.5 Code-side citation linking

```python
# research(2026-05): Baruch et al. ALIE perturbation
# see docs/citations/1902.06156-baruch-alie.md
def alie_attack(...):
    ...
```

For Markdown:

```markdown
ALIE [Baruch et al. 2019][^alie] perturbs honestly-trained updates by...

[^alie]: See [docs/citations/1902.06156-baruch-alie.md] for the verified source.
```

The mechanical pre-commit + CI check (`scripts/check_citations.py`) verifies
each `# research:` or `[^cite]` link resolves to an existing file in
`docs/citations/`.

---

## 7. Anti-hallucination guarantees

### 7.1 Mechanical (provable from code structure)

1. **Identity provenance** — `title`, `authors`, `year`, `doi`, `arxiv_id`,
   `urls` are written by `write_citation_artifact()` directly from parsed API
   JSON. The LLM is not in the call path for these fields. A code diff is
   the proof.

2. **Triangulation gate as hard reject** — `verify_and_cite()` returns
   `(None, ConflictReport)` if `triangulate()` returns `verified=False`. The
   function signature enforces this: caller cannot get a citation string
   without a successful triangulation. ([JPMorgan-style hard
   gate](https://blog.vllm.ai/2025/12/14/halugate.html).)

3. **Verbatim-excerpt check** — every excerpt is whitespace-normalized
   substring-matched against the parsed paper text. If LLM proposes a quote
   that isn't in the paper → excerpt rejected. Zero passing excerpts → no
   artifact.

4. **Artifact-file existence as code-side gate** — `scripts/check_citations.py`
   (no LLM, <1s) walks the codebase and confirms every cite link resolves to
   a file in `docs/citations/`. Runs in pre-commit + CI.

5. **Re-verifiability via audit pass** — `audit_existing_citations()`
   re-runs triangulation on every artifact's identifiers against current
   API data. Reports drift: DOI now resolves to a different paper, paper
   retracted, first-author surname corrected upstream.

### 7.2 Probabilistic (LLM judgment, audited by the artifact)

1. **Candidate selection** — LLM ranks retrieval results. Wrong-but-plausible
   pick caught by triangulation (e.g., wrong-year of same paper → year
   mismatch).

2. **Excerpt selection** — LLM picks which quotes to extract; substring check
   verifies they're real.

3. **`claim_supported` field** — LLM's stated link between paper and claim;
   reviewer-auditable in artifact body.

### 7.3 Coverage of today's failure modes

| Failure (from vFL PR #36 audit) | Caught by |
| --- | --- |
| Wrong first author ("Yifei Liu" → "Heyi Zhang") | Triangulation gate (mechanical) |
| Wrong attribution of `std=100` to FLPoison reference | Verbatim-excerpt check (mechanical — no excerpt matches) |
| Overstated "uses same formula" claim on IPM | Verbatim-excerpt check + reviewer audit of `claim_supported` |
| Unverifiable "eq. 3" precision pointer | Verbatim-excerpt check (no excerpt with that section ref) |
| Paper-of-origin overclaim (sign-flip predates Damaskinos) | LLM judgment piece — surfaced in `claim_supported` body for reviewer to audit |

Four of five caught mechanically. The fifth (semantic judgment) is surfaced
explicitly in the artifact rather than hidden.

---

## 8. Trigger model

Four tiers, aligned with the May 2026 "LLM calls belong in CI, not pre-commit"
consensus:

| Tier | When | What runs | Latency | LLM? |
| --- | --- | --- | --- | --- |
| **1. On-demand** *(primary)* | Developer or agent calls `aletheia.verify_and_cite(claim)` | Full agentic loop | 5-15s | yes |
| **2. Pre-commit mechanical** | `git commit` | `scripts/check_citations.py`: every cite link resolves to a file | <1s | no |
| **3. CI mechanical** | Every PR | Tier 2 + frontmatter schema validation (well-formed YAML, required fields, `verified_at` not stale beyond 365 days — academic metadata is reasonably stable but does drift on retractions/corrections) | <5s | no |
| **4. Scheduled audit** | Weekly cron / pre-publication | `audit_existing_citations(project_root)` — re-runs triangulation on every artifact | minutes | yes |

**Phase 2 (deferred)**: proactive inline guard — when Techne / Kallos is
generating output containing a research claim, they call Aletheia inline
before emitting. Uses Anthropic's [managed-agents
pattern](https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/).
Wire after Tier 1-3 prove stable; only if there's a real signal that proactive
catching is needed.

---

## 9. Error handling (default-deny)

Five failure modes with recovery. Every error path returns `(None, ...)`
rather than emitting an unverified citation.

| Failure | Recovery | Returns |
| --- | --- | --- |
| API timeout / 5xx | `tenacity` retry: 3 attempts, exponential backoff with jitter | After retries: `(None, RetriesExhausted)` |
| No candidates from S2 | Surface query terms to caller | `(None, NoCandidates(query=...))` |
| Triangulation reject | Surface field-level disagreement list | `(None, TriangulationConflict(fields=[...]))` |
| PDF parse failure | arXiv HTML5 → Docling → abstract-only fallback (artifact with `text_excerpts_unavailable: true`) | `(citation, artifact)` with flag, or `(None, ...)` if even abstract unreadable |
| Zero verbatim excerpts support claim | Soft triangulation reject; surface candidate for manual decision | `(None, NoSupportingExcerpts(candidate=...))` |

---

## 10. Testing strategy

Three test tiers, mirroring kourai's existing layout (`tests/unit/`,
`tests/integration/`, `tests/nightly/`):

### 10.1 Tier 1 — Unit tests (no network, no LLM)

- `test_doi_normalization.py` — idempotency, case-insensitivity, URL-prefix
- `test_title_match.py` — RapidFuzz pair fixtures (equivalent + different)
- `test_author_normalization.py` — Unicode NFKD, accents, hyphens, "Jr."
- `test_slug_generation.py` — determinism + filesystem safety
- `test_citation_artifacts.py` — write/read round-trip, schema validation
- `test_triangulate.py` — decisive vs non-decisive field handling

Hypothesis property tests:
- `normalize_doi(normalize_doi(x)) == normalize_doi(x)` (idempotency)
- For valid PaperMetadata `m`: `read_artifact(write_artifact(m)) == m` (round-trip)
- Same paper → same slug (determinism)
- Triangulation symmetric: swap primary↔secondary → same verdict

### 10.2 Tier 2 — API cassette tests (recorded HTTP, no LLM)

`tests/integration/test_academic_search.py` uses
[pytest-recording / vcrpy](https://til.simonwillison.net/pytest/pytest-recording-vcr).
First run hits real S2/OpenAlex/arXiv; subsequent runs replay from
`tests/cassettes/*.yaml`. Documented [14s → 1.4s
speedup](https://rogulski.it/blog/pytest-httpx-vcr-respx-remote-service-tests/).

Cassettes are YAML — grep-able, diff-able, AJ-auditable.

Fixture papers:
- `arxiv:1902.06156` (Baruch ALIE)
- `arxiv:2502.03801` (Zhang FLPoison)
- `doi:10.1109/TSP.2022.3153135` (Pillutla RFA)
- one preprint-with-no-DOI case
- one S2-finds-but-OpenAlex-doesn't case

Refresh: `uv run pytest --record-mode=rewrite tests/integration/test_academic_search.py`.

### 10.3 Tier 3 — Agent end-to-end (mocked LLM + replayed HTTP)

`tests/integration/test_aletheia_verify_cite.py` mocks Aletheia's LLM via a
`FakeLLM` fixture (per [Anthropic
guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents))
+ replays Tier 2 cassettes.

Coverage:
- Happy path: ALIE claim → Baruch citation + artifact
- Triangulation reject: hand-crafted wrong-first-author S2 response → `(None, TriangulationConflict)`
- No candidates: vague claim → `(None, NoCandidates)`
- API timeout: cassette 504 → retries → `(None, RetriesExhausted)`
- Abstract-only fallback: PDF parse fails → artifact with `text_excerpts_unavailable: true`
- Human override: triangulation conflict + `override=True` → artifact with `human_overridden: true`

### 10.4 Nightly — live-API contract check

`tests/nightly/test_api_contracts.py` runs one real query per source. Detects
upstream schema drift before it breaks cassettes. ~3 queries, no LLM, fast.
Failure means an API has changed shape and our cassettes need rebuild.

### 10.5 Shared-state hygiene

Per [Anthropic eval guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents),
"unnecessary shared state between runs can cause correlated failures."
Aletheia tests use per-test `tmp_path` for artifact writes; no
`docs/citations/` pollution. `pytest-mock` reset at function scope.

---

## 11. Open questions / Phase 2

- **IEEE Xplore integration** — deferred until first concrete need; institutional
  API key application is multi-week calendar time.
- **Google Scholar via paid SERP API** — opt-in, behind a `SCHOLAR_SERPAPI_KEY`
  env var. Defer until a developer specifically needs it.
- **Proactive inline guard (Tier 5)** — Techne / Kallos call Aletheia inline
  when generating output with research claims. Cost: 5-15s per generation that
  contains a citation. Defer; ship Tier 1-3 first and measure how often
  citations actually need verification.
- **CSL-JSON export from artifact** — convert frontmatter to
  [Citation Style Language JSON](https://citationstyles.org/) so Zotero /
  Pandoc can consume artifacts directly. Easy add later if needed.
- **DOI registration agents (Crossref, DataCite)** — if vFL or phalanx-fl
  ever issue their own DOIs for datasets / software, Aletheia could verify
  the registration trail too. Out of scope.

---

## 12. Implementation plan placeholder

Implementation plan will be drafted via the
[`superpowers:writing-plans`](https://github.com/obra/superpowers) skill after
AJ reviews this spec. Anticipated rough order:

1. `shared/src/kourai_common/citation_artifacts.py` + unit tests
2. `shared/src/kourai_common/triangulate.py` + unit tests
3. `shared/src/kourai_common/academic_search.py` + cassette tests (with
   one-time real-API recording)
4. Extend `agents/aletheia/agent.py` with `verify_and_cite()` and the five
   tool wrappers
5. End-to-end agent test with FakeLLM
6. `scripts/check_citations.py` + CI wiring
7. Documentation: `docs/agents/aletheia.md` describing the new capability

Each step lands as its own PR with green CI before the next begins.

---

## 13. Decision log (for posterity)

| Decision | Date | Rationale |
| --- | --- | --- |
| Extend existing Aletheia, don't build new agent | 2026-05-23 | Aletheia is already "research validator and citation enforcer" — natural specialization. |
| Direct HTTP, not MCP servers | 2026-05-23 | 100-MCP stress test: 71% median pass rate; coordinating 3 MCPs compounds tail risk. |
| Triangulation as a hard gate, not parallel-vote | 2026-05-23 | CiteGuard (single-source ReAct) is published SOTA; triangulation as a Judge-step gate adds AJ's instinct without the parallel-vote complexity. |
| Docling over PyMuPDF4LLM | 2026-05-23 | PyMuPDF4LLM is AGPL transitive-dep risk; Docling is Apache 2.0 with comparable quality and CPU-friendly. |
| Per-project `docs/citations/` not central kourai cache | 2026-05-23 | Artifacts ship with code, show up in PR diffs, get reviewed alongside the code that cites them. |
| Title fuzzy threshold 0.92 | 2026-05-23 | Matches Vikranth3140 hybrid pipeline's "exact" tier; May 2026 benchmark shows 0.85-0.90 is "everything is duplicate" — 0.92 for high precision. |
| Skip pre-commit LLM call | 2026-05-23 | May 2026 "10-second pre-commit rule" — devs bypass slow hooks. Mechanical existence check only in pre-commit. |
| Defer Google Scholar | 2026-05-23 | No official API; scraping ToS-grey; paid SERP $50-300/mo. Free S2 + OpenAlex + arXiv covers the same papers. |
| `verify_and_cite()` returns `tuple[CitationString \| None, ArtifactPathOrError]` | 2026-05-23 | Default-deny: typed boundary forces caller to handle None; no silent emit-with-warning path. |
