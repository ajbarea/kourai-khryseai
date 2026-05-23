# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

_Nothing currently open. Aletheia v2 PR 4 (`verify_and_cite` +
`audit_existing_citations`, plus the five tool implementations and the
FakeLLM fixture) shipped 2026-05-23 [#230] — see ROADMAP `## Shipped`._

Next natural pickups from the Aletheia v2 6-PR plan:

- **PR 5 — `check_citations.py` CI gate.** Independent of PR 4; could
  have been done in parallel. Mechanical CI check that every claim
  carrying a `Research:` line in production code points to a real
  artifact under `docs/citations/`. Wires into pre-commit + CI.
- **PR 6 — `docs/agents/aletheia.md`.** Depends on PR 4 (now shipped).
  Documents the citation-verification surface and the two-mode shape
  (generic claim validation v1 + academic citation verification v2).
- **Task 4.6 — Nightly API-contract tests.** Tiny follow-up to PR 4:
  3 real API calls per night to detect upstream schema drift. Plan
  carries the literal code at lines 2730-2812 of the implementation
  plan doc; ship as its own micro-PR.
