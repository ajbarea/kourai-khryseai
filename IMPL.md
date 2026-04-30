# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-29 · Working on: **M7 — a2a-sdk 1.0 migration.
Phases 1-3 shipped (the big-bang pin flip to `>=1.0,<2.0` landed
2026-04-29; messaging + server + AgentCard helpers all flipped to
the v1.0 protobuf shape; client code uses `await create_client(...)`;
SCREAMING_SNAKE_CASE enums; `enable_v0_3_compat=True` for transitional
0.3 wire compatibility). Phase 4 was absorbed into Phase 3 because
the Python API change forces both server and client migrations
together. Remaining: Phase 5 (text-tags → Message.metadata) → Phase 6
(drop compat flag + cleanup) → M13 fix.
Pre-release perfection stance: no workarounds. M19 fully shipped
(Phases 1+2+3 all landed 2026-04-29). Remaining sequence: M7
(a2a-sdk 1.0) → M13 regression fix on M7's `Message.metadata`
channel → M18 (structured streaming with content-kind metadata) →
M20 (audio-text sync). M17 itself ships clean once M13 unblocks the
readout path.**

## 2026-04-29 live smoke — what happened

Two end-to-end runs (sessions `bd1e413a` and `0dbafe91`) demonstrated the
M17 happy path **never executed** because Hephaestus drops the original
prompt across the CONFIRM_ORDER → resume → route handoff. Metis only
received the player's confirmation token (`"light it"` or `"y"`),
generated questions-as-prose as her "spec," and the rest of the
pipeline cascaded on garbage. Mneme's safety-net refusal ("I have
nothing to commit") is the only thing that worked correctly.
Pipeline still claimed `✨ Forged in 333.6s` with `commit_count: 0` —
no soft-fail signal.

The smoke surfaced 23+ findings beyond M13 — UX truncation, audio
chipmunk and crackling, agent-card poll storm, /yolo not bypassing
CONFIRM_ORDER, FACT-tag leakage into streaming status, phonemizer
warning spam, lazy-load latency on language switch, and the underlying
fact that **TTS gating turns 60-90 seconds of pipeline work into 333
seconds of wall-clock** because every status box awaits its narration.
The cluster is not 23 independent bugs — most symptoms share a root
cause in unstructured streaming. **The architectural answer is M18.**

In-flight quick wins applied this session, intentionally narrow scope,
no architectural commitment:
- `hosts/cli/rendering.py` — `[HH:MM:SS]` dim prefix in every comms-
  window header for per-step timing visibility.
- `shared/src/kourai_common/audio.py` — pygame mixer buffer 512 → 2048
  to address WSL2 + LLM-workload-induced underrun crackling. Verified
  fixed by AJ.
- `hosts/gui/tts_engine.py` — log full TTS text at INFO via `text=%r`
  (was `text_len=N`) for parity-debugging audio vs visual content.
- `hosts/gui/tts_engine.py` — wrap `chunk_bytes` in `BytesIO` for
  pygame's WAV header parsing. **Initially reported NOT fixed by AJ;
  empirically VERIFIED FIXED after `make rebuild` and clean CLI
  restart (2026-04-29).** Important mental-model correction:
  pygame-ce 2.5.7's `mixer.Sound(file=BytesIO(...))` path DOES
  resample 24 kHz mono → 44.1 kHz stereo correctly, contrary to the
  cautious docs caveats and the GitHub issues that web-search
  surfaced. Either the docs were over-conservative, or the GitHub
  issues described scenarios different from ours, or the rebuild
  shook loose stale bytecode that was masking the fix.
  **Implication: M19 (RealtimeTTS migration) remains architecturally
  desirable for word-level timings, ElevenLabs-swap path, and
  cleaner library boundaries — but it is NO LONGER URGENT.** The
  chipmunk relief is here today via the BytesIO fix.
- `shared/src/kourai_common/audio.py` — pygame mixer buffer
  512 → 2048 → 4096. 512→2048 fixed initial pop/click crackling
  from outright pygame underrun. 2048→4096 attempted but **did
  not resolve the residual music crackling AJ continues to hear
  on WSL2.** Diagnosed via `pactl info` on 2026-04-29: AJ's audio
  path is `pygame → /mnt/wslg/PulseServer → RDPSink (WSLg RDP
  relay)`, with `Latency: 31438 usec actual vs 2902 usec configured`
  — 10× the configured latency, smoking gun for WSLg's RDP audio
  relay being the bottleneck downstream of anything we can
  configure inside the kourai process. Confirmed by web-search as
  a widely-tracked WSLg-side issue (microsoft/wslg #908, #1257,
  #607, plus 2025 reports). 4096 is at the upper end of what
  application-side mitigation can do; bumping further (8192) only
  adds latency. **The crackling is a WSL2 dev-environment
  limitation, not a kourai code bug** — players running native
  Linux or native Windows (with PortAudio/ASIO) will not
  experience it. Long-term fixes are out-of-scope for kourai:
  (a) install PulseAudio-for-Windows + configure WSL `PULSE_SERVER=
  tcp:localhost:4713` (pre-WSLg pattern, requires Windows-side
  setup AJ owns), (b) run kourai natively, (c) wait for the M6
  ElevenLabs migration which changes the audio architecture
  entirely.

## Critical-path blocker: M13 CONFIRM_ORDER prompt-loss regression

`agents/hephaestus/agent.py` (and the resume handoff path) loses the
original development request when the player answers a CONFIRM_ORDER
prompt. The followup A2A dispatch to Metis carries only the player's
confirmation token, not the original ask. M13's ROADMAP entry says
"Resume happens implicitly via context_id memory (no explicit metadata
plumbing)" — that works for Hephaestus's own next-turn LLM call (where
the SDK preserves conversation history) but **does not carry across the
A2A boundary** when Hephaestus relays to a separate specialist process.

Fix shape (do not implement until M7 lands so the metadata channel is
clean): on resume, Hephaestus emits the original prompt as the first
Part of the dispatch Message. Either explicit `original_request` field
in `Message.metadata` (preferred — survives audit / replay), or as the
Message's primary text content with the confirmation as metadata.
Either way the pattern is: text bodies carry the player's request,
metadata carries operational state.

Symptom-level patch on 0.3 wire (text-tag style) is doable but deepens
the very text-tag pattern M7 wants to retire. **Do not patch on 0.3.**
Land M7 first, then fix M13 cleanly via Message.metadata.

## Architectural sequence ahead

**M7 — a2a-sdk 1.0 migration (status elevated to critical-path).**
Originally deferred "until M17 Phase 1 has miles." Phase 1 just
shipped, and the smoke proved the bracket-tag workarounds
(`[project_id: ...]`, `[yolo: on]`) cannot reliably propagate
load-bearing context across A2A boundaries. v1.0's structured
`Message.metadata` is the foundation for both M13 fix and M18.
Six-phase plan in ROADMAP §M7 is current. Pin still tightened to
`<1.0` until landed.

**M18 — Structured streaming with content-kind metadata (new).**
Each agent emission tags its content kind via `Message.metadata`:
`dialogue` (TTS-eligible, italic) | `status` (visual only, no TTS,
no gating) | `code` (monospace render, no TTS) | `spec` (markdown
wide-render, no TTS). Host's `streaming.py` routes by metadata, not
text parsing. Drops pipeline visual cadence back to ~60-90s by
eliminating the universal TTS gate. Resolves: #16 (truncation), #19
(captions semantics), #21 (TTS gating cadence). Builds on M7.

**M19 — Audio backend separation for TTS (new).**
pygame.mixer cannot reliably resample (documented limitation). Today
the mixer is initialized at 44100 Hz stereo to match music/ambient
OGGs, but Kokoro produces 24000 Hz mono. Result: ~3.7× speed
"VHS rewind" playback for TTS even with WAV header parsing. Right
fix per deeper 2026 best-practice search: **adopt `RealtimeTTS[kokoro]`
as the unified synth + playback pipeline**. Replaces both
`tts_kokoro.py`/`tts_edge.py` synthesis AND pygame.mixer playback
with one library that's the 2026 standard for streaming TTS.
KokoroEngine supports all six of our agent voices natively, exposes
`set_voice`/`set_speed` for per-agent dispatch, runs on PyAudio
(`apt install portaudio19-dev` on Linux). M6 ElevenLabs migration
becomes a one-line engine swap. pygame.mixer keeps music + ambient
+ SFX where rates are known and matched. Independent of M7/M18 —
can be prosecuted in parallel.

**M20 — Audio-text synchronization across CLI / GUI / VN (new).**
Surfaced 2026-04-29 post-rebuild CLI session. Text appears
immediately, audio plays 9-14 seconds later (Kokoro cold-start +
synthesis lag). Breaks the character-presence illusion. Right fix
per VN/community best-practice and 2026 modern content-creation
standards: pre-warm Kokoro per lang_code at startup, then audio-led
text reveal — word-by-word in lockstep with audio when RealtimeTTS
word-timings are available (English voices, M19's KokoroEngine
exposes the API), held-until-first-chunk fallback otherwise.
Three-surface implementation (CLI deferred render in
`hosts/cli/streaming.py`, GUI typewriter sync in
`tts_gui_integration.py`, Ren'Py `voice`+`cps` via the vn-bridge).
Player toggle `dialogue_sync_mode` for `audio-led` vs `instant`.
Depends on M19 (word-timing API) and M18 (content-kind metadata
to route dialogue-only to the synced path). See ROADMAP §M20 for
full scope, acceptance criteria, and tier-1/tier-2 fallback design.

**M19 Phase 1 shipped 2026-04-29:**
- `shared/src/kourai_common/tts_realtime.py` — new `RealtimeTTSEngine`
  wraps RealtimeTTS's `KokoroEngine` + `TextToAudioStream`; mirrors the
  legacy `TTSEngine` ABI for drop-in replacement (`speak`, `speak_sync`,
  `stop`, `cleanup`, `set_master_volume`, `set_on_complete`,
  `is_playing`, `enable_effects`, `master_volume`). Module re-exports
  `VoiceConfig` / `VOICE_ROSTER` / `AGENT_VOICES` for parity with
  `hosts.gui.tts_engine`. Constructor accepts `on_word=` so M20's
  word-timing reveal hooks straight in once that lands.
- `hosts/cli/__main__.py` and `hosts/cli/streaming.py` flipped from
  `hosts.gui.tts_engine.TTSEngine` to
  `kourai_common.tts_realtime.RealtimeTTSEngine`. CLI greeting + every
  in-stream `await tts.speak(...)` now routes through PyAudio — no
  pygame.mixer in the TTS path on the CLI host.
- `tests/unit/test_tts_realtime.py` — 26 tests, all PyAudio touch points
  monkeypatched at module level so `pytest` never opens a real audio
  device. ABI-mirror coverage (init, volume clamping, voice resolution
  via `AGENT_VOICE_MAP`, `voice_key` override, `speed` override,
  exception-swallowing, `on_complete` firing on both paths,
  `speak_sync` event-loop wiring, `stop`/`cleanup` shutdown).
- Live tmux smoke (`script -qc python -m hosts.cli --voice` against
  the running agent stack) verified: greeting fires
  `RealtimeTTSEngine.speak()` with correct per-agent dispatch
  (`agent=techne, voice=bf_emma, speed=0.93`), engine swallows
  audio-device errors non-fatally, process exits cleanly. Subprocess
  PyAudio sees no default device (no PulseServer socket in the tmux
  child env) — AJ's interactive terminal has WSLg's PulseAudio socket
  on `$PULSE_SERVER`, so live `make cli` will actually emit audio.

**M19 Phase 2 shipped 2026-04-29:**
- `hosts/gui/tts_gui_integration.py` and `hosts/gui/tts_helper.py`
  flipped from the legacy `TTSEngine` to `RealtimeTTSEngine`.
  `TTSGUIManager.__init__` now constructs a `RealtimeTTSEngine`
  directly — the `set_backend()` runtime kokoro/edge swap and
  `_create_backend_from_settings()` selection logic dropped (RealtimeTTS
  bundles the engine; the swap surface returns in M6 once
  ElevenLabsEngine is on the table, at the engine layer rather than the
  backend layer).
- `hosts/gui/tts_settings_config.py` `tts_backend` config key removed
  from `DEFAULT_CONFIG`; `update_from_manager` no longer snapshots
  `manager.backend` (attribute is gone).
- `hosts/gui/tts_engine.py` deleted.
- `tests/unit/test_gui_audio_tts_engine.py` deleted (TTSEngine-specific
  tests; coverage moves to `test_tts_realtime.py`).
- `tests/unit/test_gui_tts.py` autouse fixture patches
  `RealtimeTTSEngine` instead of `TTSEngine`.
- `tests/unit/test_gui_voice.py` and `tests/integration/test_tts_demo.py`
  updated to import `VOICE_ROSTER` / `AGENT_VOICES` / `RealtimeTTSEngine`
  from `kourai_common.tts_realtime`.
- Two obsolete fallback tests removed (`test_tts_backends.py`
  `TestBackendFallback::test_create_default_backend_function` and
  `test_tts_kokoro_integration.py`
  `TestBackendInteroperability::test_backend_fallback_to_edge_tts`) —
  both depended on the deleted `hosts.gui.tts_engine._create_default_backend`.

**M19 Phase 3 shipped 2026-04-29:**
- `RealtimeTTSEngine.synthesize_to_wav(text, agent_name=None,
  voice_key=None, speed=None) -> bytes` added. Drives
  `TextToAudioStream.play(muted=True, on_audio_chunk=collector)` —
  RealtimeTTS's documented bytes-only path — then wraps the int16 PCM
  in one canonical WAV header sized from
  `KokoroEngine.get_stream_info()` (paInt16 / 1 ch / 24 kHz). 9 new
  unit tests in `test_tts_realtime.py` exercise the full surface
  (empty text, voice resolution, voice_key/speed overrides, RIFF/WAVE
  markers, header values match `get_stream_info`, no-chunks → b"").
  Real-Kokoro smoke produced a 102 KB WAV (~2.13 s, mono 24 kHz) for
  a five-word test sentence — correct duration, correct headers, no
  resample step in the path.
- `agents/vn_bridge.py` migrated. `_create_tts_backend()` retired;
  `lifespan` constructs a single `RealtimeTTSEngine` and calls
  `cleanup()` at shutdown (the legacy code never cleaned up).
  `handle_tts` calls `await engine.synthesize_to_wav(text,
  agent_name=agent)` and returns a `Response` with one WAV body —
  cleaner than the previous `StreamingResponse` of multiple
  WAV-headered chunks. The `get_voice_for_agent(agent)` site moved
  inside the engine.
- `kourai_common/tts_kokoro.py` + `tts_edge.py` deleted.
  `tts_backend.py` trimmed to `TTSVoiceConfig` + `AGENT_VOICE_MAP` +
  `get_voice_for_agent` (the `TTSBackend` ABC retired with its
  implementations). `tests/integration/test_tts_kokoro_integration.py`
  deleted; `tests/unit/test_tts_backends.py` trimmed to keep only the
  voice-config + agent-mapping classes (the kokoro/edge backend test
  classes followed their subjects out the door).
- `agents/hephaestus/pyproject.toml` flipped from `edge-tts` to
  `RealtimeTTS[kokoro]` + `audioop-lts; python_version >= '3.13'`.
  hephaestus is the package vn_bridge's container builds with
  (`PACKAGE_NAME=hephaestus`), so its deps are what reach the
  vn_bridge runtime. Moving the dep matches what's actually imported.
- `hosts/gui/pyproject.toml` dropped the transitional `kokoro` /
  `soundfile` / `edge-tts` declarations. `RealtimeTTS[kokoro]` and
  `audioop-lts` stay — `RealtimeTTS[kokoro]` pulls `kokoro` +
  `soundfile` transitively.
- `docker/host.Dockerfile` got the matching system deps.
  Builder stage: `build-essential` + `portaudio19-dev` for
  HOST_TYPE in {cli, gui, vn_bridge} so PyAudio (sdist-only on Linux
  per its 0.2.14 PyPI release) compiles. Runtime stage: `libportaudio2`
  for the same hosts so PyAudio dlopens. Closes the gap CI's
  `ed4d560` had filled for Actions runners but Docker images never
  got — affected GUI (Phase 2) and CLI (Phase 1) latently; Phase 3
  fixes all three at once because the root cause is identical.
- `make validate` green: 2838 unit tests (-12 backend tests removed
  with the deleted classes, +9 new synthesize_to_wav tests, the rest
  unchanged). Lint clean. ty's three pre-existing diagnostics
  (image-pixel iteration, `await_args.args` on Mock) unchanged.
- Net diff: ~10 modules touched, three deleted; net source loss
  matches the legacy backends being subsumed by RealtimeTTS.
  `kourai-common` no longer carries the `TTSBackend` ABC + Kokoro/Edge
  pair, so the M6 ElevenLabs swap is now a one-line engine change in
  `tts_realtime.RealtimeTTSEngine.__init__` (as the M19 architectural
  promise stated).

**M13 fix.** After M7 lands: emit the original request via
Message.metadata on resume dispatch. Tested via re-run of the
2026-04-29 smoke against `make up`.

Once that sequence is in, **M17 readout follows trivially**: the
PAUSE-on-coverage_target flow already works in unit tests
(2876 passing); it only needs Metis to receive a real planning
prompt to fire end-to-end. The smoke that's currently blocked
becomes a 5-minute exercise.

## Smoke findings — categorized

**Critical / blocking M17 readout:**
- M13 CONFIRM_ORDER prompt-loss across A2A boundary (above)
- /yolo only adds `[yolo: on]` tag; does NOT bypass CONFIRM_ORDER gate
  (verified via litellm RAW response on session `0dbafe91`)

**Architectural — solved by M18:**
- Comms-window streaming chunks render as discrete narrow boxes
  (truncation appearance) rather than coherent dialogue
- Final-render wide box only fires for some agents (Mneme yes, Metis
  no) — depends on artifact-vs-status emission path
- TTS gates pipeline visual cadence (333s for 60-90s of work)
- FACT tags leak into streaming status display (raw `<FACT
  category="..."` markup pre-filter)
- Mneme reads ENTIRE 905-char dialogue including markdown asterisks
  and backticks aloud (no dialogue-only filter on TTS path)

**Architectural — solved by M19:**
- TTS chipmunk-pitch / "VHS rewind" (pygame can't resample 24kHz mono
  → 44.1kHz stereo)
- pygame.mixer buffer underrun crackling (mitigated 512 → 2048,
  verified gone, but the right architecture decouples TTS from
  pygame entirely)

**Independent UX bugs — small focused PRs each:**
- Pipeline reports `Pipeline complete` and `commit_count: 0` together
  with no soft-fail surface (#17)
- Per-agent CLI color coding via colored-background "badge" pattern
  (Okabe-Ito CVD-safe, NO_COLOR-aware) (#10)
- Music playlist sparse (2 tracks) — independent of ElevenLabs
  migration (#11)
- Agent-card poll storm — 30+ GET `/.well-known/agent-card.json` per
  minute on idle agents; check Hephaestus capability discovery
  interval and Prometheus scrape config (#12)
- Context7 MCP integration broken: `MCP error -32602: Tool
  get-library-docs not found` AND URL template emits literal
  `[User]:` placeholder (#14)
- Duplicate empty `Project root:` field at end of Metis enriched
  prompt (#15)
- Phonemizer warning spam ("words count mismatch on 100.0% of the
  lines (1/1)") on every TTS call — downgrade to DEBUG (#22)
- Pre-warm Kokoro per-language at TTSEngine init (avoid first-speak
  pause when an agent in lang_code=b speaks for the first time) (#23)
- Explicit captions / TTS subtitle toggle for accessibility — SPEECH
  VS ACTION rule already provides de-facto captions; toggle would
  make it intentional and surface SPEECH VS ACTION violations (#19)

## Notes / open questions

- **MCP elicitation deferred-by-design.** Unchanged from prior — real-
  caller-driven only. When the first forge MCP tool wants
  `ctx.elicit()`, the architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design.
- **Smoke 1 from 2026-04-28 still queued** — environmental, blocked
  on `api.anthropic.com` egress stability from agent containers.
- **MCP spec version pinned to 2025-11-25.** Spec drift watcher cron
  (`scripts/watch_protocols.py`) will flag any subsequent revision.
- **`run_post_task_hooks` orchestration unwired.** Layer is fully
  tested but no production call sites; `synthesise_fact_from_pause`
  lives directly in `streaming.py` as the pragmatic answer. Promotion
  is sibling work flagged for M5/M6.
- **Specialist parity for fact recall.** Today only Metis reads
  `build_fact_context` with project scope; Techne / Kallos /
  Dokimasia / Hephaestus inherit the gap. Defer until a non-Metis
  PAUSE caller surfaces.

## Up next — priority order

UX/DX is the default between milestones, but the smoke session promoted
M13/M7/M18/M19 above the queue. AJ's pre-release perfection stance
applies — no workarounds, web-search 2026 best practice before any
implementation, architectural fix over expedient patch.

1. **M7 — a2a-sdk 1.0 migration.** Foundation for everything below.
   Six-phase plan in ROADMAP §M7. No more deferral.
2. **M13 fix on top of M7.** Original-request via Message.metadata
   on CONFIRM_ORDER resume dispatch. Re-run smoke to verify.
3. **M18 — Structured streaming with content-kind metadata.** New
   milestone, builds on M7. See ROADMAP §M18 for the kind taxonomy
   and per-agent rollout plan.
4. **M20 — Audio-text synchronization across CLI / GUI / VN.**
   Builds on M18 (content-kind routing) + M19 (RealtimeTTS word-
   timing API now wired via the `on_word=` callback in
   `RealtimeTTSEngine.__init__`). New milestone surfaced this session
   — the 9-14s text-precedes-audio gap is a first-thing-player-notices
   UX issue. See ROADMAP §M20.
5. **Live M17 Phase 1+2 smoke (re-run).** Trivial once M13 unblocks
   it. Original plan from this session unchanged: `make up`,
   `/project use <python-template>`, fizzbuzz prompt, watch PAUSE
   on coverage_target, answer next turn, watch narrator quote it
   back, see `fact.recalled=true` on `metis.execute` span in Jaeger
   via the M16 trace-ID-in-Dozzle pivot, exercise `/preferences`,
   restart for cross-session recall, manual SQL backdate for decay.
6. **Independent UX bugs from the smoke** (see "Smoke findings —
   Independent UX bugs" section above) — sized for individual focused
   PRs.
7. **Live VN smoke** — `make vn` exercises both fixes from PR #66 and
   now the new vn_bridge `/tts` → `RealtimeTTSEngine.synthesize_to_wav`
   path.
8. **`docs/architecture/puck-first-run-tutorial.md`** — pairs with
   the M6 player-onboarding theme (committed in `2ad93c1`).
9. **M5 / M12 / M15 / M6 follow-ons** — see ROADMAP for scope.
