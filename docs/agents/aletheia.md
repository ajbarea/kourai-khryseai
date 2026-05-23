# Aletheia — research validator + citation enforcer

Aletheia is the spirit of truth in the Kourai pantheon. She validates that
technical claims are grounded in real research and that citations point at
real papers with accurate metadata.

## Two surfaces

### Generic claim validation (v1, existing)

`aletheia.validate_research(text)` runs a regex pre-screen for algorithmic
claims (Big-O, "proven", "optimal", "industry standard") and uses Brave
Search to surface evidence. Returns a per-claim verdict block.

Use this for: industry-standard references, RFCs, generic web claims.

### Academic citation verification (v2, this page's focus)

`aletheia.verify_and_cite(claim, project_root=...)` runs a 5-tool agentic
loop over Semantic Scholar + arXiv + OpenAlex, picks a candidate paper,
verifies the claim is supported by verbatim excerpts in the paper text,
cross-checks the metadata against a second source, and writes an artifact
file at `docs/citations/{slug}.md` that the developer can manually audit.

Returns `(citation_string, artifact_path)` on success, or
`(None, ConflictReport)` if any verification step fails.

Use this for: academic paper citations in code comments, READMEs, PR bodies,
LinkedIn captions — anywhere a hallucinated citation would damage trust.

## Why this exists

LLMs hallucinate academic citations at empirically observed rates of
14-95% (CiteVerifier benchmark, May 2026). NeurIPS 2025 had ~100 fabricated
citations across 53 published papers. The 5 errors caught in vFL PR #36's
manual audit are the same failure mode at smaller scale.

The full design rationale lives in
[2026-05-23-aletheia-v2-citation-verification-design.md](../architecture/2026-05-23-aletheia-v2-citation-verification-design.md).

## How to use

### From Python

```python
from agents.aletheia.agent import verify_and_cite

citation, artifact_or_conflict = await verify_and_cite(
    claim="ALIE attack perturbs honest updates within a statistical envelope",
    project_root=Path("/path/to/my/project"),
)

if citation is None:
    # artifact_or_conflict is a ConflictReport — inspect it
    print(f"Refused: {artifact_or_conflict.kind}: {artifact_or_conflict.detail}")
else:
    # artifact_or_conflict is the Path to the written artifact file
    print(f"Citation: {citation}")
    print(f"Artifact: {artifact_or_conflict}")
```

### From code comments

After running `verify_and_cite`, link the artifact in your code:

```python
# research(2026-05): Baruch et al. ALIE perturbation
# see docs/citations/1902.06156-baruch-alie.md
def alie_attack(...):
    ...
```

### From Markdown

```markdown
ALIE [Baruch et al. 2019][^alie] perturbs honestly-trained updates.

[^alie]: See [docs/citations/1902.06156-baruch-alie.md] for the verified source.
```

The `scripts/check_citations.py` CI gate verifies every link resolves to a
well-formed artifact (pre-commit + CI on every PR).

## Anti-hallucination guarantees

Mechanical (deterministic, code-verifiable):

1. **Identity provenance** — `title`, `authors`, `year`, `doi`, `arxiv_id` in
   the artifact YAML come VERBATIM from API JSON. The LLM is not in the call
   path for these fields.
2. **Triangulation gate** — `verify_and_cite()` returns `(None, ConflictReport)`
   if the secondary source (OpenAlex or arXiv) disagrees on any decisive
   field (DOI, arxiv_id, title fuzzy-match, first-author surname, year).
3. **Verbatim-excerpt check** — every quote in the artifact body is verified
   as a whitespace-normalized substring of the parsed paper text.
4. **Artifact-file existence** — `scripts/check_citations.py` verifies every
   cite link resolves to an artifact file (pre-commit + CI).
5. **Re-verifiability** — `audit_existing_citations(project_root)` re-runs
   the triangulation step on every artifact and reports drift.

Probabilistic (LLM judgment, reviewer-audited):

1. **Candidate selection** — LLM ranks retrieval results; wrong-but-plausible
   picks caught by triangulation.
2. **Excerpt selection** — LLM picks quotes; substring check verifies they're real.
3. **`claim_supported` field** — LLM's stated link, reviewer-auditable in
   the artifact body.

## Configuration

Environment variables:

| Var | Purpose | Required? |
| --- | --- | --- |
| `OPENALEX_API_KEY` | OpenAlex polite-pool API key — [register here](https://openalex.org/signup) (30s) | Yes (since 2026-02-13) |

## Operational notes

- **Latency**: 5-15s per `verify_and_cite()` call (2-5 API calls + LLM judgment).
  Do NOT put this in a pre-commit hook — see the [10-second pre-commit rule](https://www.deployhq.com/git/ai-git-hooks).
- **Drift audit cadence**: `audit_existing_citations()` re-runs the
  triangulation step on every artifact. Schedule weekly, or invoke before
  any major submission (paper, poster, LinkedIn post).
- **Human override**: if a triangulation conflict is a known false positive
  (e.g., S2 has stale data), invoke with `override=True, override_reason="..."`.
  Records `human_overridden: true` in the artifact frontmatter.
