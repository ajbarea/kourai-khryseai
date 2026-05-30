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

**Integration decided (2026-05-30): isolate Chatterbox, do NOT downgrade in-process.** The
in-process `RealtimeTTS ChatterboxEngine` path is rejected — it needs `realtimetts>=0.7.3`
and `chatterbox-tts` hard-pins `torch==2.6.0`, which would downgrade torch **2.11→2.6** +
transformers **5.7→5.2** across the shipping **Kokoro** stack. `research(2026-05)`: best
practice for a conflicting-torch model is to isolate it (own env / local inference server),
not downgrade the host — matches kourai's architectural-fix rule. kourai stays on torch
2.11; Chatterbox runs out-of-process behind a thin client engine (design TBD). The step-3
adapter is engine-agnostic, so it stands. **Validated on the rig 2026-05-30:** Chatterbox loads + synthesizes on the RTX 3060 Ti
(isolated torch-2.6 venv); an emotion-range smoke (one neutral placeholder voice, lines from
clinical→excited with matched exaggeration) confirms the expression mechanism reads, pending
AJ's ear (`~/Downloads/kourai-m6-samples`).

**Voice casting is OPEN (reframed 2026-05-30).** The Kokoro `AGENT_VOICE_MAP` per-maiden
assignments were never auditioned — a skeleton, not a baseline — so Chatterbox must NOT clone
from them. The per-maiden cast (a fit reference clip each) is a fresh creative audition (AJ's
call); the step-3 expression map is voice-agnostic and rides on whatever voices land.

**Rig-bound remainder (AJ):** the by-ear A/B on the samples (is Chatterbox worth the
isolation build?); the out-of-process integration design (client engine → local Chatterbox
service); the step-2 per-maiden voice-clip cast (5 s reference clips — a creative call);
expression value tuning (the cast numbers are starting points). M20 word-timing: Chatterbox
has no `on_word` → M20 Tier-2 reveal (design-resolved). Audio cache shipped [#174].

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
