# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

_Nothing currently open._

**M6 status (UN-DEFERRED 2026-05-30):** Chatterbox-first local-expressive (build-ready
plan in ROADMAP M6). **Steps 1 + 3 shipped:** the engine seam (`KOURAI_TTS_ENGINE`,
dark) and the **per-maiden emotion adapter** (2026-05-30) — `AGENT_EXPRESSION_MAP` in
`tts_backend.py` casts each maiden's `exaggeration` + `cfg_weight` (derived from her
`VOICE_CASTING_PLAN` style + Kokoro speed; Kallos/Puck/Cupid expressive, Aidos/Aletheia
clinical), applied per-utterance in `_apply_voice` via `set_voice_parameters` (skips the
re-apply when unchanged, since setting exaggeration re-prepares the voice). Hermetically
TDD'd, mirroring step 1; the seam stays dark.

**Blocker found — RealtimeTTS upgrade (AJ's call).** The pinned **RealtimeTTS 0.6.1 has no
`ChatterboxEngine`** — it landed in 0.7.x (latest 0.7.3 ships the `chatterbox` extra), so
the chatterbox path can't construct on current deps; only the hermetic mocks exercise it.
M6 needs `realtimetts>=0.7.3` + the `chatterbox` extra. That bump touches the **shipping
Kokoro path**, so it's a deliberate upgrade + Kokoro-regression check, not a cold-session
bump — left to AJ. GPU + CUDA torch are confirmed live in this env (RTX 3060 Ti).

**Rig-bound remainder (AJ):** the RealtimeTTS upgrade above; step-2 voice-clip cast (5 s
reference clips per maiden — a creative call); by-ear A/B + value tuning (the cast numbers
are starting points). M20 word-timing: Chatterbox has no `on_word` → M20 Tier-2 reveal
(design-resolved). Audio cache shipped 2026-05-06 [#174].

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
