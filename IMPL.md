# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight — M6 step 4: Chatterbox voice audition

**Approved by ear 2026-05-30 (AJ): Chatterbox wins decisively** on the emotion-range A/B.
The integration is built + live-validated on GPU; what's left is casting each maiden's voice.

**Shipped (steps 1–3):** isolated torch-2.6 Chatterbox service (`services/chatterbox/`,
out-of-workspace via `services/*` exclude; real perth watermark via `setuptools<81`, which
restores the `pkg_resources` setuptools 81+ dropped). `kourai_common.chatterbox_client` —
async, raises `ChatterboxUnavailable`. The `KOURAI_TTS_ENGINE=chatterbox` seam routes BOTH
`synthesize_to_wav` (cached, chatterbox-keyed) and `speak()` (synth → PyAudio WAV playback,
Tier-2 on_audio_start; no word timing) through the client with Kokoro fallback; the
superseded in-process path is gone and Kokoro is always the in-process engine + fallback.
Live happy-path + service-down fallback both verified; `make lint` + TTS units green.

**Next — the audition:**
- Source candidate female reference clips per maiden — fresh, NOT the unvalidated Kokoro
  `AGENT_VOICE_MAP`. Respect each maiden's gender (hephaestus / puck are male); fit each
  register (`tools/voice-lab/VOICE_CASTING_PLAN.md`).
- Generate per-candidate samples via the service (expression already in `AGENT_EXPRESSION_MAP`);
  AJ picks. Record chosen clips in `VOICE_CASTING_PLAN.md` + wire into `AGENT_VOICE_REF_MAP`
  (seam reads it; empty today → built-in voice).
- **Open question for AJ (only creative input needed):** I generate candidate options per
  maiden for you to pick, or you supply specific voices/clips?

**DoD:** per-maiden voices AJ-approved + wired; Kokoro path unaffected; tests green.
Rig: RTX 3060 Ti; service env at `services/chatterbox/.venv`; samples in `~/Downloads/kourai-m6-samples`.

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
