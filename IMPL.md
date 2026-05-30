# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight — M6 step 2: Chatterbox integration + voice audition

**Approved by ear 2026-05-30 (AJ): Chatterbox wins decisively** over Kokoro on the
emotion-range A/B (clinical→excited, same voice). Build it. Steps 1 (seam) + 3
(`AGENT_EXPRESSION_MAP` emotion adapter) already shipped; the expression map is
engine-agnostic and rides on whatever voice lands. Architecture decided: **isolate
Chatterbox** (the in-process `RealtimeTTS ChatterboxEngine` is rejected — `chatterbox-tts`
pins `torch==2.6.0`, which would downgrade the shipping Kokoro stack; `research(2026-05)`:
isolate a conflicting-torch model behind a local service, don't downgrade the host).

**Build plan:**
1. **Chatterbox service** — a minimal local HTTP service in its own torch-2.6 uv env
   (e.g. `services/chatterbox/`), loads `ChatterboxTTS` once on GPU, `POST /synthesize`
   `{text, voice_ref, exaggeration, cfg_weight} → wav`. Resolve perth properly (not the
   smoke `DummyWatermarker`). `research(2026-05)`: devnen/Chatterbox-TTS-Server is a ready
   reference for the FastAPI/OpenAI-compatible shape.
2. **Client engine in the seam** — `KOURAI_TTS_ENGINE=chatterbox` becomes a thin HTTP
   client to the service (NOT in-process), feeding the maiden's `AGENT_EXPRESSION_MAP`
   exaggeration/cfg_weight + her voice ref per request. Graceful fallback to Kokoro if the
   service is down. Hermetic tests (mock the client); the live Kokoro path stays untouched.
3. **Hybrid wiring** — Kokoro default (fast); maidens route to Chatterbox. (Per-line
   emotion modulation is a later refinement.)
4. **Voice audition** — source candidate female reference clips per maiden (fitting each
   character — fresh, NOT the unvalidated Kokoro `AGENT_VOICE_MAP`); generate samples;
   AJ picks. Chosen clips = the cast, recorded in `VOICE_CASTING_PLAN.md`.

**DoD:** service runs + kourai synths through it on the GPU; per-maiden voices AJ-approved;
Kokoro path unaffected; tests green; M20 word-timing stays Tier-2 (Chatterbox has no
`on_word`). Rig confirmed: RTX 3060 Ti + isolated torch-2.6 venv at `/tmp/cbsmoke` work;
samples in `~/Downloads/kourai-m6-samples`.

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
