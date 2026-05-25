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

Unblocked mechanical chores (pick when AJ wants a low-risk session):
- `kourai_common` docstring deslop round 2 — shipped 2026-05-23, ~−65 LoC
  across 12 modules. Targets the "Split from player.py for focused
  responsibility" + "Pre-this-module" + "Moved from" history-narration
  patterns PR #238 missed. Pattern for future sweepers: `git log --oneline
  --grep=deslop` shows the prior arc.
