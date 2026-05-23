# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

### 2026-05-23 — Aletheia v2 Phase 1.7: CI job exercising the `aletheia-v2` extra

**Why.** The handoff doc shipped with PR #226 flagged this gap: the default
`unit-tests` / `integration-tests` jobs in `tests.yml` run
`uv sync --all-packages --dev --frozen` (no `--extra aletheia-v2`), so
tests gated by `pytest.importorskip("rapidfuzz" / "httpx" / "tenacity" /
"docling")` silently skip in CI. A regression in the aletheia-v2 stack
(`triangulate`, `academic_search`) would land green.

**Decisions.**
- Add a third CI job `Aletheia v2 Tests` (depends on `lint`) that runs
  `uv sync --all-packages --extra aletheia-v2 --group dev --frozen` and
  executes the gated test files for real.
- Separate job rather than matrix — only one optional extra to exercise,
  no Python-version sweep. Matrix becomes the right call when a second
  extra appears.
- Coverage uploads to Codecov under the `aletheia-v2` flag so the
  citation-verification stack tracks separately from `unit` / `integration`.

**Definition of done.**
- New job runs `test_triangulate.py`, `test_citation_artifacts.py`,
  `test_academic_search.py` (the `not nightly` slice) with extras installed. ✓
- Local verification: 66 unit + 6 integration pass with extras installed,
  `make lint` clean. ✓
- CI: Aletheia v2 Tests job green on PR push.
