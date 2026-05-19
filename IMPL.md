# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-19

## In flight

Nothing currently open. The 2026-05-16 → 2026-05-18 wave landed cleanly:

- #192/#193 — May 2026 model + pricing verification + docs propagation
- #194 — May 2026 infra freshness sweep (uv, context7-mcp, dozzle, nodejs)
- #195 — May 2026 app-SDK freshness sweep (7 bumps via uv.lock)
- #196 — feat/theoros (observed live REPL session)
- #197 — feat/voice-examples (few-shot voice examples for distinctive character)
- #198 — feat/theoros-autopilot (3-pane autopilot layout)
- #199 — docs/generalize-poster-title (CHAI 2026 poster generalization)
- #200 — fix/dev-cli-demo-targets (cli-demo / gui-demo / vn-demo registration)
- #201 — chore/license-mit-swap (Apache 2.0 → MIT)

Deferred from this wave, still tracked:

- **RealtimeTTS 0.6.1 → 0.7.1** — KokoroEngine → KokoroVoice breaking change.
  See ROADMAP "Surfaced 2026-05-17 from app-SDK freshness sweep". Gated on
  AJ-in-loop live smoke (Kokoro is karaoke's primary engine; voice-name
  regressions are easy to miss without ear-on).
- **`smoke-m18` / `sandbox-image` `kourai-dev` registration** — see
  ROADMAP "Surfaced 2026-05-18 from make-delegation audit". Gated on a
  real second caller (Windows-without-make dev or CI matrix).

## Next pickups

Live-smoke-gated work dominates the priority list (M6 sub-tasks 1/3/4/5,
VN polish, Puck Slice 3/4). Without AJ at the keyboard, the productive
moves are:

- **Audit-mode work** — `/techne:sisters` cross-repo drift, `/techne:docsync`
  on docs/**/*.md + README.md + AGENTS.md, CLAUDE.md drift check.
- **Planned non-gated milestones** — M5 (UID alignment), M12 (dynamic
  sizing across GUI), M15 (forge logging architecture). None require
  live smoke; each lands as a focused PR.
- **DRY-sweep follow-ups deferred from #170** — pyloudnorm migration of
  `AudioNormalizer`, VN demo-script bridge, Pydantic v2 migration of
  `CLISettings`. File when the corresponding pain point surfaces; not
  blocking.

Next priority milestone: **M6 ElevenLabs hybrid** (full spec in
[ROADMAP.md → M6](./ROADMAP.md#m6--elevenlabs-hybrid-pre-player-release-blocker)).
Gated on M20 + VN live smoke landing first.
