# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

_Nothing currently open._

**M6 status (UN-DEFERRED 2026-05-30):** the post-funding gate is gone — the TTS
re-survey found local, $0, real-time engines that do per-character emotion.
Decision: **Chatterbox-first local-expressive** (full rationale + build-ready
plan in ROADMAP M6). Next action: the engine-seam refactor + Chatterbox wiring,
built and A/B'd **at AJ's GPU rig** — voice quality + the M20 word-timing gate
are by-ear, on-hardware checks I can't run in CI/WSL. Default stays Kokoro until
the A/B passes; the seam ships dark. Sub-task 2 (audio cache) shipped 2026-05-06
[#174].

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
