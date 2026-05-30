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
plan in ROADMAP M6). **Step 1 (engine seam) shipped 2026-05-30** —
`KOURAI_TTS_ENGINE=kokoro|chatterbox`; default Kokoro, seam ships dark. Remaining
work is **rig-bound** (AJ's GPU): per-maiden Chatterbox voice cast, emotion
adapter, by-ear A/B — voice quality is a by-ear check I can't run in CI/WSL. The
M20 word-timing gate is design-resolved: Chatterbox has no `on_word`, so it falls
to M20's Tier-2 reveal. Sub-task 2 (audio cache) shipped 2026-05-06 [#174].

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
