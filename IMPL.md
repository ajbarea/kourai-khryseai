# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-16

## In flight

Nothing actively building. 2026-05-16 shipped two sweeps back-to-back:
the May 2026 model/pricing verification sweep (#192 host-side
gemini-2.5-flash-lite migration + cache threshold corrections + Opus
4.7 tokenizer caveat; #193 sibling docs propagation) followed by the
May 2026 infra freshness sweep (#194 — `uv` 0.10.10 → 0.11.14,
`@upstash/context7-mcp` 2.1.6 → 2.2.5, `dozzle` v10.5.0 → v10.5.3,
`nodejs-22` → `nodejs-24` in sandbox; all other Docker/GHA/Python pins
verified FRESH against primary sources). See ROADMAP shipped log for
details.

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
