# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

_Nothing currently open. The full Aletheia v2 6-PR plan closed
2026-05-23 [#222 → #234]; see ROADMAP `## Shipped` for the arc._

Natural next pickup is **M6 — ElevenLabs hybrid (pre-player-release
blocker)**. Sub-task 2 (audio cache layer) is the next slice per
ROADMAP line 11. Aletheia v2 Phase 2 (proactive inline guard — Techne
/ Kallos call Aletheia when emitting citations) is unblocked but
explicitly **un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
