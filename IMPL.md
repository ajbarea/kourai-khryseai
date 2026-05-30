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

**Audition (in progress, GPU-blocked):** recipe DIALED IN by ear over 5 rounds — see
the "validated recipes" section of `tools/voice-lab/VOICE_CASTING_PLAN.md`. Maidens =
warm Kokoro seed + slow/breathy/intimate delivery (`exag 0.4, cfg 0.3`) + optional clean
pyworld deepen (F0 ×0.85, breath ×1.35); the librosa phase-vocoder warbles "underwater"
(avoid). Hephaestus CAST (gruff3: am_michael + librosa pitch −3 + grit, "Poseidon"; don't
overcook). Winners: af_bella 9/10, af_nicole-deep 9/10. **PAUSED 2026-05-30** — AJ
traveling (NC / SCADS residency), rig disassembled; GPU generation resumes when it's back.

**Next:** AJ assigns a voice per maiden portrait (`assets/avatars/vn/`) → lock
`AGENT_VOICE_REF_MAP` (`tts_backend.py`) with each maiden's seed + recipe + per-maiden DSP
note. Locking assignments is laptop-OK (no GPU); regenerating/tuning needs the rig + the
service (`cd services/chatterbox && uv run python server.py`). All voices still want tuning.

**DoD:** per-maiden voices AJ-approved + wired; Kokoro path unaffected; tests green.

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
