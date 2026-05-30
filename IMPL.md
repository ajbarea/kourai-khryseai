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
1. ✅ **Chatterbox service** (`services/chatterbox/`) — isolated torch-2.6 uv project,
   excluded from the workspace (`services/*`) so it can't downgrade the main torch-2.11
   lock. Loads `ChatterboxTTS` once on GPU; `GET /health` (503 while loading), `POST
   /synthesize` `{text, voice_ref?, exaggeration, cfg_weight} → audio/wav`. perth resolved
   properly: `setuptools<81` restores the `pkg_resources` the real `PerthImplicitWatermarker`
   needs (81+ removed it) — real watermark, not the dummy. GPU-validated end-to-end.
2. ✅ **HTTP client** (`kourai_common.chatterbox_client`) — async `ChatterboxClient`
   (`synthesize` / `health`), `KOURAI_CHATTERBOX_URL` env, raises `ChatterboxUnavailable`
   so the seam can fall back to Kokoro. 10 hermetic tests (httpx.MockTransport).
3. **Seam wiring (next)** — `KOURAI_TTS_ENGINE=chatterbox` routes `synthesize_to_wav`
   through the client (maiden voice_ref + `AGENT_EXPRESSION_MAP`), Kokoro fallback on
   `ChatterboxUnavailable`. REPLACES the superseded in-process
   `_load_chatterbox_engine_cls`/`set_voice_parameters` path (broken on RealtimeTTS 0.6.1 +
   wrong per the isolate decision); rewrite its seam tests. Add `AGENT_VOICE_REF_MAP` (empty
   until the audition). Kokoro path byte-for-byte untouched.
4. **Voice audition** — candidate female ref clips per maiden (fresh, NOT the unvalidated
   Kokoro `AGENT_VOICE_MAP`; respect gender — hephaestus/puck male); generate; AJ picks;
   chosen clips recorded in `VOICE_CASTING_PLAN.md` + wired into `AGENT_VOICE_REF_MAP`.

**DoD:** service runs + kourai synths through it on the GPU; per-maiden voices AJ-approved;
Kokoro path unaffected; tests green; M20 word-timing stays Tier-2 (Chatterbox has no
`on_word`). Rig confirmed: RTX 3060 Ti + isolated torch-2.6 venv at `/tmp/cbsmoke` work;
samples in `~/Downloads/kourai-m6-samples`.

Aletheia v2 Phase 2 (proactive inline guard — Techne / Kallos call
Aletheia when emitting citations) is unblocked but explicitly
**un-prioritized** pending real-usage data on how often
`verify_and_cite` is invoked manually in practice.
