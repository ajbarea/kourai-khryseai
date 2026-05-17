# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-17

## In flight

Nothing actively building. Three back-to-back freshness sweeps shipped
2026-05-16 → 2026-05-17 (#192/#193 model+pricing, #194 infra,
#195 app-SDK). See ROADMAP shipped log for one-liners. The one
deferred bump — **RealtimeTTS 0.6.1 → 0.7.1** (KokoroEngine →
KokoroVoice breaking change) — is captured in ROADMAP under
"Surfaced 2026-05-17 from app-SDK freshness sweep" and gates on
AJ-in-loop live smoke.

## Next pickups

Re-audited 2026-05-16 against actual call sites. Previously-listed
"small self-contained" picks turned out to be anticipatory:

- ~~Cross-host status-feed~~ — no CLI `/debug` slash command exists
  (greps empty in `hosts/cli/`); sole consumer remains
  `hosts/gui/debug_log.py`. Skip until a real second consumer lands.
- ~~Puck Slice 2 helper~~ — `/replay-tutorial` is still stub-gated.
- ~~Cross-host gossip-render~~ — no host renderers yet; shared-logic-only.
- ~~Cross-host codex~~ — needs live VN smoke for the parchment-book
  renderer.

The clean current-caller picks are exhausted. Next moves require
either an intentional anticipatory-gate override (flag it in the PR
body) or **M20 + VN live smoke** to unblock M6 ElevenLabs hybrid.

**Audit-mode work always available**: docs/*.md drift sweep,
/techne:sisters cross-repo audit, CLAUDE.md / AGENTS.md drift check.

Next priority milestone: **M6 ElevenLabs hybrid** (full spec in
[ROADMAP.md → M6](./ROADMAP.md#m6--elevenlabs-hybrid-pre-player-release-blocker)).
