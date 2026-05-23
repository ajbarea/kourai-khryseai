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

**M6 status (corrected 2026-05-23):** sub-task 2 (audio cache layer)
**already shipped** 2026-05-06 [#174]. Remaining M6 sub-tasks (1, 3,
4, 5) are **gated on Live VN smoke** (AJ-at-the-keyboard step under
ROADMAP "Live-smoke gated"). Don't start them until the VN smoke
exercises the vn_bridge `/tts` → `RealtimeTTSEngine.synthesize_to_wav`
path end-to-end with M20 sub-task 2/4 cps verification — that smoke is
the prerequisite signal that the synth + indicator stack is ready for
production swap.

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
