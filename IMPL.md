# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

_Nothing currently open._

**M6 status (deferred 2026-05-24):** kourai ships **Kokoro-only** for now;
the premium-voice expansion is parked until funding. Rationale: pre-funding,
M6 was gated on the VN smoke + M20 regardless, and the TTS landscape churns
yearly so a specific integration built now would rot. Don't build any
premium-engine integration until AJ revisits post-funding. Sub-task 2 (audio
cache layer) already shipped 2026-05-06 [#174]. Quality context for the
revisit lives in ROADMAP M6 + memory `project_kourai_m6_tts_engine_decision`.

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
