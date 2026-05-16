# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-16

## In flight

**2026-05-16 model/pricing verification sweep** (branch
`docs/cache-thresholds-may-2026-verify`):

- `gemini-2.0-flash` deprecates 2026-06-01 per Google's pricing page;
  migrated `MODELS_*_GOOGLE` (21 refs across three tiers) to
  `gemini-2.5-flash-lite` — the price-identical, GA successor (input
  $0.10, output $0.40, cache $0.01 per MTok). Added the 2.5-flash-lite
  entry to `GEMINI_PRICING`; kept the 2.0-flash entry as a deprecated
  legacy line so historical `/usage` cost-resolution still works.
- Corrected the min-cacheable-prefix comment in `llm.py`: Sonnet 4.6
  is **1024 tokens** (not 2048), Haiku 4.5 is **4096 tokens** —
  important call-out for the default CHEAP tier since every agent rides
  on Haiku 4.5 and sub-4k prompts pass `cache_control` through without
  caching. Verified against
  `platform.claude.com/docs/en/build-with-claude/prompt-caching`.
- Freshened `pricing.py` date markers (April 2026 → 2026-05 verified)
  and added an Opus 4.7 tokenizer caveat: new tokenizer consumes up to
  ~1.35× more tokens for the same source text, so projecting Opus 4.7
  spend from Opus 4.6 historical usage will under-quote by up to ~35%.
  Per-token math stays correct (LiteLLM reports actual tokens).
- Anthropic rates re-verified against
  `platform.claude.com/docs/en/about-claude/pricing` — Haiku 4.5,
  Sonnet 4.6, Opus 4.6, Opus 4.7 all match. No code change needed on
  Anthropic side.

Tests: 3167 unit passed locally; lint clean.

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
