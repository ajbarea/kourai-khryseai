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
2026-05-16 → 2026-05-17:

- #192 + #193 (2026-05-16) — May 2026 model/pricing verification.
  Host-side gemini-2.5-flash-lite migration + cache threshold
  corrections + Opus 4.7 tokenizer caveat (+ sibling docs propagation).
- #194 (2026-05-16) — May 2026 infra freshness. `uv` 0.10.10 → 0.11.14,
  `@upstash/context7-mcp` 2.1.6 → 2.2.5, `dozzle` v10.5.0 → v10.5.3,
  `nodejs-22` → `nodejs-24` in sandbox.
- #195 (2026-05-17) — May 2026 app-SDK freshness. Seven safe bumps
  inside existing lower-bound ranges via `uv lock --upgrade-package`:
  a2a-sdk 1.0.2 → 1.0.3, huggingface-hub 1.13.0 → 1.15.0, litellm
  1.83.14 → 1.85.0 (cache-shape compat verified by passing all 31
  `test_llm.py` cache tests), mcp 1.27.0 → 1.27.1, numpy 2.4.4 → 2.4.5,
  pydantic 2.12.5 → 2.13.4, uvicorn 0.46.0 → 0.47.0. **RealtimeTTS
  0.6.1 → 0.7.1 deferred** (KokoroEngine→KokoroVoice breaking change;
  needs voice-load path updates + AJ-in-loop live smoke — backlog
  entry in ROADMAP under "Surfaced 2026-05-17").

See ROADMAP shipped log for one-liners.

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
