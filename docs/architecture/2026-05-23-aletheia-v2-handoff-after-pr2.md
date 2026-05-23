# Aletheia v2 — Implementation Handoff (after PR 1 + PR 2 merged)

**Pause point**: end of subagent-driven development for PRs 1 + 2. Context
budget for the original session was nearly exhausted; a fresh session
should pick up from here.

**Companion docs**:
- Spec: [`2026-05-23-aletheia-v2-citation-verification-design.md`](./2026-05-23-aletheia-v2-citation-verification-design.md)
- Plan: [`2026-05-23-aletheia-v2-implementation-plan.md`](./2026-05-23-aletheia-v2-implementation-plan.md)

---

## Status as of this handoff

| PR | Status | Merge commit | Notes |
| --- | --- | --- | --- |
| 1 — citation_artifacts | ✅ merged | `dbe2962` | 34 unit tests, hypothesis caught a filesystem-safety bug in `slug_for_paper` |
| 2 — triangulate | ✅ merged | `23e1274` | 32 unit tests, `[tool.ty.analysis] allowed-unresolved-imports` extended for the aletheia-v2 extras (rapidfuzz, httpx, tenacity, docling, vcr) |
| 3 — academic_search | 🟡 branch pushed, not opened as PR | branch `feat/aletheia-v2-pr3-academic-search` (4 commits, rebased onto main as of `21b850a..ddc3a4e`) | Needs: open PR, monitor CI, fix anything CI catches, merge. **62MB PDF cassette already removed**, `test_fetch_paper_pdf_via_docling` marked `@pytest.mark.nightly` |
| 4 — Aletheia agent integration | ⏳ not started | — | Largest task in the plan — 5 sub-tasks (FakeLLM fixture, extract_claim + search_papers, fetch_paper_text + match_evidence, verify_and_cite, audit_existing_citations + nightly contract tests) |
| 5 — check_citations.py CI gate | ⏳ not started | — | Independent of PR 2 / 3 / 4 — could be done in parallel with PR 4 |
| 6 — docs/agents/aletheia.md | ⏳ not started | — | Depends on PR 4 |

---

## Critical lessons that should be baked into every PR 3+ subagent dispatch

These were discovered the hard way during PR 1 + PR 2 + PR 3 work. The
implementation-plan doc does NOT cover these yet; future subagent prompts
should include them.

### 1. CI does not install the `aletheia-v2` optional extra

Kourai's CI workflows run `uv sync --all-packages --dev --frozen` which
pulls dev tooling + workspace packages but does NOT pull
`[project.optional-dependencies]`. So `httpx`, `tenacity`, `rapidfuzz`,
`docling` are absent in CI.

**Two coordinated defensive measures are required** in every PR that adds
code touching these deps:

**(a) Test-side: `pytest.importorskip` at module top.** Tests silently
skip when the dep is missing.

```python
import pytest
pytest.importorskip("rapidfuzz")  # or httpx / tenacity / docling

from kourai_common.triangulate import (
    ...
)
```

**(b) Production-side: ty `allowed-unresolved-imports`.** `ty check` runs
over `shared/src` in CI and errors on `from rapidfuzz import fuzz` if the
dep is absent. Already added in `pyproject.toml`:

```toml
[tool.ty.analysis]
allowed-unresolved-imports = [
    "bridge", "test.**",
    "rapidfuzz", "rapidfuzz.**",
    "httpx", "httpx.**",
    "tenacity", "tenacity.**",
    "docling", "docling.**",
    "vcr", "vcr.**",
]
```

Future production modules importing any of these deps are now safe under
the existing allowlist. If a new aletheia-v2 dep gets added, extend the
allowlist.

**Follow-up (out of this scope but worth noting)**: a separate CI job
that runs `uv sync --extra aletheia-v2` and exercises the importorskip-
gated tests would actually verify them. Without that, the aletheia-v2
tests run only locally (when devs install the extra) and silently skip
in CI. Track as a Phase 1.7 follow-up.

### 2. Cassettes have a hard size budget

vcrpy serializes the entire response body to YAML. A 1MB PDF response →
~62MB cassette (base64 + YAML overhead). **Anything past ~5MB is too big
for git history.** During PR 3 work, the docling-via-PDF test produced
a 62MB cassette that got committed to commit `f5998e2` before I caught
it — required an amend + force-push to remove.

**Rule for any PR adding new cassettes**:
- Run the recording locally
- Immediately `du -sh tests/cassettes/*.yaml`
- If any file exceeds 5MB, do NOT commit — instead, mark the test as
  `@pytest.mark.nightly` (so it skips on the push/PR fast lane) and let
  the nightly job hit the real URL instead.
- The `nightly` marker is now registered in `pyproject.toml`
  `[tool.pytest.ini_options]` `markers`.

The existing PR 3 branch already applies this — `test_fetch_paper_pdf_via_docling`
is marked nightly and the 62MB cassette is gitignored.

### 3. Subagent self-review consistently lies about "make lint clean"

Three separate subagent dispatches reported "make lint clean" while CI
caught real failures. The pattern: the subagent ran `uv run ruff check
<file>` (file-scoped) instead of `make lint` (whole-repo). File-scoped
ruff misses whole-repo TC003 / UP035 / FURB / PERF / RUF100 hits.

**Fix in every subagent prompt going forward**: include the literal
instruction:

> Before committing, run BOTH:
> 1. `make lint` (whole-repo)
> 2. `uv run ty check shared/src/kourai_common/<your-new-file>.py tests/...your-new-tests>.py`
>
> The kourai pre-push gate is `make lint`. CI re-runs the same gate.
> Fix any new ruff/ty issues in YOUR files before committing.
> Pre-existing errors in unrelated files (~46 in hosts/cli) are not your
> concern unless your changes increased the count.

### 4. Stacked PRs need rebase after the lower one merges

PRs 2 and 3 were both developed stacked on PR 1's branch for parallel
progress. After PR 1 squash-merged, both stacked branches needed
`git rebase --onto origin/main <pr-1-tip-commit>` to drop PR 1's
individual commits and rebase the new work onto the squashed main.

The rebases were clean (no conflicts) — but the workflow should be
explicit in subagent prompts so they don't push pre-rebase branches
and confuse CI with PR-1-already-on-main commits showing as new.

### 5. Track monitor task IDs and TaskStop the old one before re-arming

When a CI run fails and you push a fix, the old `Monitor` watching the
PR doesn't auto-exit (its predicate `All checks were successful` never
fires). Re-arming a new monitor without stopping the old one fires
duplicate events. Memory captured: `feedback_monitor_kill_old_before_rearm.md`.

---

## PR 3 — exact next-action checklist

The PR 3 branch is in good shape; the work just needs to land:

1. Pull the latest of the branch:

   ```bash
   git checkout feat/aletheia-v2-pr3-academic-search
   git pull --ff-only
   ```

2. Sanity verify locally:

   ```bash
   uv sync --extra aletheia-v2
   uv run --extra aletheia-v2 pytest tests/integration/test_academic_search.py -v -m "not nightly"
   # Expected: 6 cassette tests pass (1 nightly deselected)
   make lint
   # Expected: clean (ty allowlist is on main already from PR 2's pyproject.toml fix)
   ```

3. Open the PR:

   ```bash
   gh pr create --title "feat(aletheia-v2): academic_search HTTP layer + cassette tests (PR 3/6)" --body "..."
   ```

   Suggested PR body (paraphrased from the plan):

   > PR 3 of 6 — direct httpx + tenacity clients for Semantic Scholar
   > (primary retrieval), arXiv (preprints + HTML5 paper text), OpenAlex
   > (triangulation gate cross-source). pytest-recording cassette tests
   > replay 6 real-API responses; the heavier docling-via-PDF test is
   > marked nightly to avoid bloating git with multi-MB cassettes.
   >
   > Real-API findings from cassette recording: S2 unauthenticated
   > rate-limits aggressively (added `S2_API_KEY` env support), OpenAlex
   > returns lowercase DOIs, arXiv HTML5 only renders for papers
   > submitted after late 2023 (changed test fixture to a 2026 paper).

4. Monitor + merge on green.

5. PR 4 (Aletheia integration) can branch from PR 3's tip if you want
   parallel progress, or from main after PR 3 merges. PR 4 has no other
   blockers.

---

## PR 4 — biggest remaining task, fresh-session-friendly

PR 4 is the most consequential and the biggest. A fresh session with
clean context is the right way to attack it. The plan has 5 sub-tasks
(4.1 through 4.6 — Task 4.6 is the small nightly-contract-tests
follow-up).

The plan code blocks should be mostly correct, but apply the lessons
above when dispatching subagents:

- importorskip httpx + rapidfuzz at the top of any test file that
  imports academic_search / triangulate transitively
- run `make lint` (not file-scoped ruff) before commit
- check cassette sizes after recording (none of PR 4's tests record
  cassettes — it uses the PR 3 cassettes + FakeLLM, so this shouldn't
  bite)
- the FakeLLM fixture pattern is in the plan; spec-review the
  implementer's version against it
- `tests/integration/test_aletheia_verify_cite.py` will need the same
  importorskip-gating dance + the `@pytest.mark.integration` marker
  already used in PR 3

PR 4's most complex piece is `verify_and_cite()` — the orchestrator that
chains the 5 tools. Use sonnet for that subagent, haiku for the smaller
extract_claim / match_evidence helpers.

---

## Score so far

- **Time spent**: ~3 hours of session real-time (multiple cycles of
  subagent dispatch → review → fix → push)
- **Code shipped**: 2 production modules + 1 test module + ~66 unit
  tests + 1 spec + 1 implementation plan
- **Real bugs caught by tests (not by the subagent)**: 1 hypothesis-
  surfaced filesystem-safety bug in `slug_for_paper`; CI caught 4
  separate lint failures the subagents missed
- **PRs merged**: #222 (spec), #223 (plan), #224 (PR 1), #225 (PR 2)
- **PRs remaining**: 4 (PR 3 ready-to-open, PR 4-6 to do)

The architecture is sound, the foundation modules are solid, and the
remaining work is mechanical execution of the plan with the
lessons-learned guardrails baked in.
