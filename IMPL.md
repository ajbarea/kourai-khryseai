# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When a
milestone lands, its detail block in [ROADMAP.md](./ROADMAP.md) collapses
to a one-liner under "Shipped" and this file resets to the next milestone.
Git history is the archive — these docs are plans + scratchpad, not a
historical record.

Updated: 2026-05-06 · Active focus: **Cache-tighten follow-on shipped
[#178]** — splits the previously-monolithic system content into two
cache breakpoints at the source: Block 0 truly-static (`SYSTEM_PROMPT` +
optional call-site `static_suffix`, **1h TTL**); Block 1 player-dynamic
(identity + memories + alignment + romance + personality adaptation +
memory moments + virtues, 5m default). Replaced string-returning
`get_enriched_system_prompt` with `get_enriched_system_blocks` returning
cache-marked text blocks; new public helper `cached_text_blocks(*chunks,
static_ttl="1h")` in `kourai_common.llm` for hephaestus's manual `_route`
path. Migration: 9 agent callers + hephaestus + 5 test files.
`_build_contextual_messages` appends summary block to upstream lists
rather than collapsing them; legacy string path preserved as safety net.
1h-TTL default is web-search-confirmed May 2026 Anthropic best practice
for long interactive sessions (Forge Party sessions routinely exceed 5min
idle; truly-static block re-use pays back the 2× write multiplier after
one hit beyond 5min). Stays within Anthropic's 4-breakpoint budget (BP1
static-1h / BP2 player-dynamic-5m / BP3 summary-5m / BP4 first-user-5m).
~5× reduction in static-block write tokens on top of the ~3-7× from #177.
**LLM cache breakpoint split shipped [#177]** —
`_build_contextual_messages` now structures the system prompt as two
`cache_control` text blocks (static + dynamic summary) instead of
concatenating them. Static block always cache-hits within a session;
summary block resets only on Mneme rewrite. Closes the
CODEX_ARCHITECTURE_PLAN.md note that flagged this issue but had never
been executed. Magnitude: ~3-7× reduction in cache-write tokens on long
Forge Party sessions. **Scratchpad rebuild Phase 1 shipped [#176]** —
`kourai_common.scratchpad` data layer + CLI `/scratchpad` slash command.
Replaces the post-#175 classifier-drop path with a real consumer; agent
reasoning is recallable per-agent instead of dropped. Aligns with 2026
best practice for LLM CoT visibility (distinct render, not spoken;
sources in module docstring). Same session: **M6 sub-task 2 shipped
[#174]** — `kourai_common.tts_cache` content-addressable disk cache
validated against the spec'd shape (sha256-of-length-prefixed inputs,
sharded `{key[:2]}/{key}.{ext}` layout, 500 MB cap with oldest-mtime-
first eviction); enabled at vn_bridge construction where the static
dialogue dicts give near-100% hit rate once warm. **GUI zombie call
sites cleaned [#175]** — 8 sites in `hosts/gui/{render,queue_event_handler,pygame_event_handler}.py`
referenced GUIComponentsIntegration attributes that #173 deleted;
ty: 22→14 diagnostics. M6 sub-task ordering: markup adapter
(sub-task 1) bundles with production swap (sub-task 4); ElevenLabs
SDK integration (sub-task 3) gated on M20 + VN smoke. Pre-player-
release blocker still M6 overall. SSML markup investment reverted
[#152]; defensive strip helpers stay. Cross-host DRY sweep merged
in [#170] — 10 extractions to `kourai_common/`. Dead host-side
anticipatory infra pruned in [#173] — 9 source / 6 test files /
~2.6k LOC; 7 cross-host rebuild items filed in ROADMAP backlog (one
shipped 2026-05-06, six remaining). main is clean; issue #126
(upstream-blocked `@xmldom/xmldom@0.8.12` HIGH bundled inside npm
11.13.0) is auto-managed by
`.github/workflows/issue-126-rescan.yml` — Saturdays 14:17 UTC from
2026-05-16, auto-closes once upstream lands `>=0.8.13`.

## M18 Phase 2 — walked back to plain-text dialogue (closed)

The original Phase 2 plan was producer-side SSML emission with
engine-side strip-then-synthesize, anticipating an M6 ElevenLabs swap.
PRs [#147] (strip layer), [#149] (hephaestus pilot), and [#150]
(handoff/victory rollout) shipped that direction; closed PR #151
(greetings/gossip) was queued. **All dialogue-content SSML reverted
in [#152] after verifying ElevenLabs's actual May 2026 docs:**

- **Eleven v3 (M6 high-impact-line target per VOICE_CASTING_PLAN.md)**
  does NOT support SSML break tags. Their idiom is `[bracket]` audio
  tags (`[whispers]`, `[sarcastic]`) + ellipses + natural punctuation.
- **Eleven Flash V2.5 (M6 routine-dialogue target)** supports `<break>`
  in theory but ElevenLabs explicitly warns *"too many break tags can
  cause instability"* and recommends ellipses/dashes anyway.
- **Kokoro mainline (current engine)** has zero native SSML
  (`hexgrad/kokoro#36` open).

So `<speak>...<break time="200ms"/>...</speak>` was the wrong markup
for both Kokoro AND the planned M6 target. Original strings already
had natural punctuation that BOTH engines honor for pauses without
any tagged markup.

**What stays as defensive infrastructure (not reverted):**
- `kourai_common.ssml.strip_ssml` + defusedxml dep — guards against
  any future LLM output that might wrap text in `<speak>` or other
  XML-shaped markup.
- `_comms_window` strip chokepoint, `_maidenify_status` strip,
  `RealtimeTTSEngine.speak()` + `synthesize_to_wav()` strips,
  vn_bridge NDJSON yield strip — idempotent and fast on plain text
  via the `<`-substring early return.
- Cross-platform TTS auto-mute [#146], uvicorn-takeover sweep [#148],
  vn_bridge headless unblock [#145] — unrelated to the SSML walk-back.

**Lesson logged in memory** ([feedback_websearch_before_arch_decision.md](
../../.claude/projects/-home-ajbar-ajsoftworks/memory/feedback_websearch_before_arch_decision.md)):
web-search the SPECIFIC target's primary docs at the IMPL/ROADMAP
planning step, not just at implementation time. The "portable subset"
claim from generic SSML web-search wasn't enough — verifying against
ElevenLabs's actual best-practices page would have flagged this on
day 1 instead of after 5 PRs.

## M6 — ElevenLabs hybrid (pre-player-release blocker)

Promoted from "future-future" 2026-05-03; spec'd 2026-05-05 against
ElevenLabs's actual May 2026 docs (see *Research log* below — same
discipline as the M18 Phase 2 walkback, applied at the planning step
this time per
[feedback_websearch_before_arch_decision](../../.claude/projects/-home-ajbar-ajsoftworks/memory/feedback_websearch_before_arch_decision.md)).

Character voice IS the product (Hephaestus gruff vs Kallos lilting);
Kokoro swaps voicepacks but can't deliver per-character emotional
control. ElevenLabs can. [VOICE_CASTING_PLAN.md](../tools/voice-lab/VOICE_CASTING_PLAN.md)
already casts voice IDs + per-maiden settings.

### Engine + model strategy

| Model | Use | Latency | Price | Markup support |
|---|---|---|---|---|
| `eleven_flash_v2_5` | routine dialogue, handoffs | ~75ms | $0.06 / 1k chars | `<break>` works but ElevenLabs warns against overuse — use natural punctuation |
| `eleven_v3` | victory lines, key handoffs, onboarding | ~1-2s | $0.12 / 1k chars | `[bracket]` audio tags for emotional control; **no** SSML break tags |

### Required add-ons before player release

Three layers, ordered by ship-readiness (smallest first):

#### 1. Per-engine markup adapter (replaces walked-back SSML approach)

Producers emit plain text with optional inline `[bracket]` audio
direction hints — same lowercase-bracket convention ElevenLabs documents.
The adapter at the engine boundary translates per target engine:

| Engine | Behavior |
|---|---|
| `eleven_v3` | Keep `[bracket]` tags. Tag effect decays after ~4-5 words; producers should write short tagged segments. Layered tags supported (`[nervously][whispers]`). |
| `eleven_flash_v2_5` / `eleven_multilingual_v2` | Strip brackets — v3 audio tags don't apply. Emotional tone comes from `voice_settings.style` + low `stability` + per-maiden voice training. Skip `<break>` per ElevenLabs's instability warning; punctuation carries pacing. |
| `kokoro` (current) | Strip brackets. No SSML, no audio tags; punctuation carries everything. |

Tag vocabulary (lift from ElevenLabs's documented set, scoped to
maidens — skip the cinematic ones that don't fit pipeline dialogue):

- Voice cues: `[whispers]`, `[sighs]`, `[exhales]`, `[laughs]`,
  `[sarcastic]`, `[curious]`, `[excited]`, `[crying]`
- Layered (per ElevenLabs docs): `[nervously][whispers]`,
  `[softly][sighs]`, etc.
- Skip: `[applause]`, `[clapping]`, `[gasps]`, `[sings]`, accent
  tags — too rare or character-mismatched for kourai's dialogue mix.

The existing `kourai_common.ssml.strip_ssml` defensive layer stays in
place as a second line of defence against any LLM that emits
XML-shaped markup. Order at the engine boundary: strip SSML
(defensive) → apply engine markup adapter (engine-aware) → synthesize.

`research(2026-05)`: ElevenLabs `prompting/eleven-v3` audio-tag
list, help-center "How do audio tags work with Eleven v3" 4-5-word
decay note, help-center "Do pauses and SSML phoneme tags work" model
support matrix.

#### 2. Audio caching layer (cost control — required for player scale)

**Open question answered (2026-05):** ElevenLabs has **no server-side
cache by content hash**. The History API stores every generation but
indexes by server-assigned `history_item_id`, not by request payload
hash. The cache is ours to build. Pattern follows ElevenLabs's own
Supabase cookbook: hash request params client-side, store bytes in
object storage, look up before regenerating.

Spec:

- **Cache key:** `sha256(text + voice_id + model_id + voice_settings_json)`.
  voice_settings serialized with sorted keys for hash stability.
- **Storage:** `${XDG_CACHE_HOME:-~/.cache}/kourai/tts/{key[:2]}/{key}.{ext}`.
  Two-char prefix shard prevents inode bloat in any one directory.
  Format extension matches `output_format` (mp3 default).
- **Eviction:** size cap (default 500 MB), oldest-modified-first when
  over cap. No TTL — cache hit on identical inputs is always valid;
  same engine + same `seed` is deterministic, our voice_settings are
  stable per-maiden.
- **API:** `cached_synthesize(text, voice_id, model_id, settings) -> bytes`.
  Cache miss → call engine → write bytes to cache → return.
  Idempotent.
- **Opt-out:** `cacheable=False` kwarg for one-shot dynamic content
  where the hit rate would be near-zero (e.g., long LLM-generated
  responses with high text variance). Default `True`.

Primary cache targets are **static dialogue dicts**: `HANDOFF_LINES`,
`HANDOFF_FALLBACKS`, `VICTORY_LINES`, `AGENT_QUOTES`, user_quotes
greetings. These repeat constantly across players — once warm,
near-100% hit rate.

`research(2026-05)`: ElevenLabs cookbook
`text-to-speech/streaming-and-caching-with-supabase` (canonical
client-side caching pattern); `api-reference/history/get` confirms
`history_item_id`-only lookup, no content-hash semantic.

#### 3. Per-persona prosody design pass

With adapter + cache shipped and ElevenLabs reference audio in hand
(via `tools/voice-lab` Next.js scratchpad), decide which maidens get
which emotional defaults:

- Kallos: `[whispers]` for teasing asides, lower stability for
  expressiveness.
- Dokimasia: `[sarcastic]` defaults during validation failures.
- Aidos / Aletheia: highest stability + lowest style for clinical /
  authoritative validation tone (already in VOICE_CASTING_PLAN.md).
- Hephaestus: gruff via `style` slider + voice training (no `[gruff]`
  tag exists).

Deferred under the SSML plan; now design-tractable against real
reference audio post-adapter-ship.

### Sub-task order + gating

1. **Per-engine markup adapter** — `kourai_common.tts_markup.apply_engine_markup`.
   Ships when caller exists (i.e., bundled with sub-task 4 below).
2. **Audio cache layer — SHIPPED under Kokoro [#174]** —
   `kourai_common.tts_cache.cached_synthesize`. Engine-agnostic via
   fetch-injection; same module wraps Kokoro now and ElevenLabs at
   sub-task 3 swap. Cache key:
   `sha256(length-prefixed(text, voice_id, model_id, sorted-keys-json(voice_settings)))`
   — length-prefixing for collision resistance even if a separator
   byte appears in any input (NUL-separator turned out to be an
   unverifiable invariant once a regression test demanded it).
   Layout: `${XDG_CACHE_HOME:-~/.cache}/kourai/tts/{key[:2]}/{key}.{ext}`;
   eviction: oldest-mtime-first when total > 500 MB cap, on
   miss-write via `asyncio.to_thread`; opt-in via
   `RealtimeTTSEngine(cache_dir=...)` (default `None` = uncached so
   existing tests stay green); enabled at vn_bridge construction
   where static dialogue dicts repeat constantly across players. CLI
   / GUI integration deferred — current `speak()` streams synth into
   PyAudio playback rather than returning bytes; routing through
   cache there is non-trivial and the high-volume target is the VN
   surface anyway. Re-enter when ElevenLabs swap forces `speak()` to
   refactor against bytes.
3. **ElevenLabs SDK integration** — `pyproject.toml` adds `elevenlabs`
   dep; new `ElevenLabsEngine` class implementing the same
   `RealtimeTTSEngine` public surface (`speak`, `speak_sync`,
   `synthesize_to_wav`, `on_word`, `on_audio_start`). Engine selected
   via `KOURAI_TTS_ENGINE=elevenlabs|kokoro` env (default `kokoro`
   until cutover). `client.text_to_speech.convert(voice_id, text,
   model_id, voice_settings=VoiceSettings(stability, similarity_boost,
   style, use_speaker_boost, speed), output_format)` is the SDK call;
   returns bytes.
4. **Voice-lab → production wiring** — flip default to `elevenlabs`,
   smoke through CLI / GUI / VN.
5. **Per-persona prosody pass** — tune voice_settings + audio tag
   defaults per maiden against reference audio.

**Production swap gated on M20 + VN smoke landing first** —
character voice quality is most visible against a polished dialogue
UX; doing M6 before audio-led reveal lands would burn ElevenLabs
spend chasing UX bugs we already know about.

### Cost projections (2026-05 ElevenLabs API pricing)

- Pre-release dev (~200 lines/day × 50 chars): ~$22/month.
- 100 active players (~200 lines/session × 30 sessions): ~$2,160/month
  uncached → ~$430-1,080/month after cache layer (50-80% hit rate
  on static dialogue, near-100% on v3 lines after warm).
- 1000 active players: ~$21,600/month → ~$4,300-10,800/month with
  cache.

### Research log

- **Eleven v3 audio tags** — vocabulary + layered-tag syntax + the
  4-5-word decay constraint that shapes how producers should write
  tagged segments. Source: ElevenLabs `prompting/eleven-v3` doc +
  help-center "How do audio tags work with Eleven v3" article.
  Verified 2026-05-05.
- **SSML / pause guidance** — `<break>` works on v2/v2.5 but with
  explicit instability warning; v3 doesn't support break tags;
  natural punctuation (ellipses, dashes) is the recommended
  cross-model pattern. Source: ElevenLabs best-practices doc +
  help-center pause article. Verified 2026-05-05.
- **No server-side cache by request hash** — confirmed via search
  of ElevenLabs cookbook, API reference, and 2026 cheat sheet. The
  Supabase cookbook is the canonical client-side caching pattern.
  Source:
  `elevenlabs.io/docs/cookbooks/text-to-speech/streaming-and-caching-with-supabase`.
  Verified 2026-05-05.
- **Latency / pricing** — Flash v2.5 ~75ms / $0.06 per 1k chars,
  v3 ~1-2s / $0.12 per 1k chars, multilingual_v2 ~1-2s. Source:
  ElevenLabs models doc + Webfuse 2026 cheat sheet. Verified
  2026-05-05.
- **Python SDK shape** — `ElevenLabs(api_key=...)`,
  `client.text_to_speech.convert(voice_id, text, model_id,
  voice_settings=VoiceSettings(stability, similarity_boost, style,
  use_speaker_boost, speed), output_format)` returns `bytes`.
  Source: official SDK README + Context7 mirror. Verified
  2026-05-05.

## M18 Phase 3 — KIND_CODE / KIND_SPEC distinct render paths (deferred)

**Part A — strict kind routing** shipped ahead of Phase 2 since it stood
on its own. The two surviving forwarders (hephaestus's pipeline-status
re-emitter; `BaseAgentExecutor`'s empty-input prompt) now tag explicitly,
so the `kind is None or` fallback is gone from `hosts/cli/streaming.py`
and the prose-keyword `DIALOGUE_KEYWORDS` heuristic is gone from
`agents/vn_bridge/__main__.py`. Untagged messages are now routed as
not-dialogue everywhere.

**Part B — distinct render paths for `KIND_CODE` / `KIND_SPEC`** is
deferred. Both kinds are reserved tokens with no producer; building host-
side render paths before any specialist emits them is anticipatory infra.
Re-enter Part B once a specialist (likely techne for code, metis for spec)
opts into emitting these kinds.

## Notes / open invariants

- **MCP elicitation deferred-by-design.** Real-caller-driven only.
  Architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design when the first forge MCP tool wants `ctx.elicit()`.
- **MCP spec version pinned to 2025-11-25.** Spec drift watcher cron
  (`scripts/watch_protocols.py`, runs Sundays 13:00 UTC) flags any
  subsequent revision.
- **`run_post_task_hooks` orchestration unwired.** Layer is fully tested
  but no production call sites; `synthesise_fact_from_pause` lives
  directly in `streaming.py` as the pragmatic answer. Promotion is sibling
  work flagged for M5/M6.
- **Specialist parity for fact recall.** Today only metis reads
  `build_fact_context` with project scope; techne / kallos / dokimasia /
  hephaestus inherit the gap. Defer until a non-metis PAUSE caller surfaces.
- **Cache-tighten `get_enriched_system_prompt` follow-on shipping** —
  see the active-focus block above. Active-focus also bundles the 1h
  TTL upgrade for the static block (web-search-confirmed Anthropic
  May-2026 best practice for long interactive sessions); collapses to
  one-liner under "Shipped" once the PR merges.
- **Sisters audit weekly cron** (`trig_013uP9ryCLYscBKS7X6PB5og`,
  Mondays 12:00 UTC) opens drift PRs and a rollup issue automatically.
- **Issue #126 auto-rescan** (`.github/workflows/issue-126-rescan.yml`)
  fires Saturdays 14:17 UTC from 2026-05-16 until the bundled
  `@xmldom/xmldom` lands `>=0.8.13` across our three npm-bearing images.
- **DRY-sweep follow-ups deferred from [#170]:**
  - **pyloudnorm migration of `AudioNormalizer`** in
    `kourai_common.audio_dsp`. Today's hand-rolled LUFS approximation
    works; ITU-R BS.1770-4 via pyloudnorm is technically correct but
    requires re-tuning the per-personality profiles in `AGENT_PROFILES`
    against new readings. File when an audio-quality callback surfaces.
  - **VN demo-script bridge.** `kourai_common.demo_script` is consumed
    by CLI and GUI; VN's `script_poster_demo.rpy` keeps a header comment
    cross-reference rather than a real import (Ren'Py can't import
    Python at script-time without bridge gymnastics). Build a `.rpy`
    codegen pass when the demo script needs another change.
  - **Pydantic v2 migration of `CLISettings` / `SettingsManager`.** The
    new `AudioSettings` is a `@dataclass` to match the surrounding
    style; full migration would touch settings persistence,
    slash-command panels, and tests. File when a settings-validation
    pain point surfaces.

## Up next — priority order

Pre-release perfection stance: no workarounds, web-search May 2026
best practice **at the planning step** (not just at implementation —
see [feedback_websearch_before_arch_decision](../../.claude/projects/-home-ajbar-ajsoftworks/memory/feedback_websearch_before_arch_decision.md)),
architectural fix over expedient patch. Pick by impact + caller
reality, not file-of-origin.

**Live-smoke gated** (need AJ at the keyboard):
- M20 sub-task 2 + 4 VN cps verification (item 1 below)
- Live VN smoke end-to-end (item 2)
- M6 sub-tasks 1, 3, 4, 5 — markup adapter / ElevenLabs SDK / production
  swap / per-persona prosody pass; gated on M20 + VN smoke landing
- Puck Slice 3 + 4 — flight scene rewrite, first-message routing
- VN dialogue-presentation polish (illuminated-manuscript framing) —
  parchment + plaque corner flourishes, epithet subtitle

**Self-contained workable** (ship clean without AJ in-loop):
- Puck Slice 2 helper-only — `_invoke_agent_live(agent, prompt,
  fallback, timeout)` A2A timeout-and-fallback wrapper. Skip the
  `/replay-tutorial` command pending Slice 3 (replays a still-stub
  flight scene = anticipatory).
- Cross-host pipeline-status — `kourai_common.pipeline_status` data
  layer (PipelineState frozen + PipelineTracker with handoff hooks)
  + vn_bridge wiring (replaces the local `current_agent` variable).
  GUI integration (refactor of GUIState's agent fields) deferred to
  Phase 2 — risky to bundle with the data layer.
- Cross-host status-feed — `kourai_common.status_feed` (RingBuffer[T]
  + StatusEvent typed record). One writer, three subscribers (CLI
  `/debug` slash, future GUI bottom overlay, file-write). Replaces
  debug_log.py + the deleted status_bubbles parallel state stores.
- Cross-host gossip-render — `kourai_common.gossip_render`
  (RenderedRound). gossip_core / gossip_models already canonical
  from #170; what's missing is the host-agnostic structured-render
  translation. Renderers collapse to ~30-line ANSI / pygame /
  Ren'Py adapters.
- Cross-host codex (in-game encyclopedia) — biggest scope; fixes
  the broken VN codex screens; Mass Effect-shape data + unlock
  triggers. Best done as one large PR; live smoke needed for VN
  parchment-book renderer.
- Per-agent motion language — polish, lands last.

**Original priority order** (M20 / Puck / M6 chain) below for
context. Items shipped 2026-05-06 marked with their PR.

1. **M20 sub-task 2 + 4 — audio-led text reveal + opt-out toggle.**
   Sub-task 2 shipped on all three surfaces: **CLI Tier 2 [#153]**,
   **CLI Tier 1 karaoke [#154]**, **GUI Tier 1 word-paced typewriter
   [#156]**, **VN audio-led cps [#157]**. Sub-task 4 settings toggle
   shipped [#158]: `dialogue_sync_mode = audio-led | instant` across
   all three surfaces (CLISettings + GUI TTSGUIManager + VN
   persistent + screens_menu). Default audio-led so behavior is
   unchanged for players who don't touch settings; "instant" reverts
   to the legacy text-first / audio-catches-up path on each surface. The engine grew per-call `on_audio_start` + `on_word`
   kwargs dispatched via stable trampolines; `speak_sync` forwards
   them so the GUI's daemon-thread wrapper can drive the typewriter
   without blocking the pygame loop. The VN surface uses a different
   primitive — `vn_bridge` `/tts` returns an `X-TTS-Duration-Seconds`
   header (computed from the WAV frames / framerate), Ren'Py's
   `bridge.request_tts` parses it and the main loop wraps each say
   in `{cps=N}...{/cps}` so the typewriter finishes when the voice
   does. **Live VN smoke needed** to verify the cps math feels right
   end-to-end (Ren'Py-side change can only be live-tested with AJ
   at the keyboard). Settings toggle
   (`dialogue_sync_mode = audio-led | instant`) is sub-task 4.

   Open follow-ups within sub-task 2 itself:
   - **CLI synthesis indicator shipped 2026-05-05 [#165]** — pre-render
     `Name face …` (dim ellipsis) before `await tts.speak(...)` in
     the audio-led karaoke path; cleared via CR + erase-line ANSI
     when `on_audio_start` fires (or before the Tier 2 box renders
     on auto-mute). Helpers `synthesis_indicator` /
     `synthesis_indicator_clear` in `hosts/cli/rendering.py`.
   - **GUI synthesis indicator shipped 2026-05-05 [#166]** — `TypewriterManager.set_pending_audio()`
     renders a single-ellipsis placeholder until the first
     `advance_word()` (or `clear_pending_audio()`) fires.
     `_on_tts_audio_start` flipped from no-op to clear the placeholder;
     `_add_with_word_paced_typewriter` arms it after `start_word_paced`.
     Motion-sensitivity respected (full text already revealed; no
     placeholder swap). VN equivalent still pending — gated on live-
     smoke since Ren'Py drives via `cps` not direct typewriter.
   - Box-with-progressive-body alternative if AJ wants the CLI
     comms window aesthetic preserved during the karaoke reveal.
   - Concurrent dialogue race: if a NEW dialogue entry arrives while
     the OLD entry's TTS is still firing on_word, the typewriter
     reset clears state and stale callbacks become no-ops. Edge-case;
     observed-tolerable for now.
   - extract_speakable mismatch: GUI strips action prose / code from
     spoken text but the typewriter shows full source — TTS word
     count won't match source word count. Cursor stops short until
     `flush_remaining` fires. Acceptable Tier 1 trade; revisit if
     player UX flags it.
2. **Live VN smoke** — exercises the vn_bridge `/tts` →
   `RealtimeTTSEngine.synthesize_to_wav` path + metadata-based
   dialogue routing end-to-end. Needs AJ at the keyboard.
3. **Puck-led first-run tutorial implementation** — spec at
   `docs/architecture/puck-first-run-tutorial.md` polished + added
   to docs nav in [#162]; implementation underway. Pairs with M6
   player-onboarding theme so first-run voice quality (the load-
   bearing first impression) lands on ElevenLabs prosody rather
   than Kokoro.

   Slices (smallest end-to-end first):
   - **Slice 1 — mode cascade + `/settings [0]` entry shipped 2026-05-05 [#168]** —
     `apply_mode_cascade(mode)` flips all 7 cascade settings across
     PlayerProfile.preferences + CLISettings in one pass; idempotent;
     opinionated (overrides individual toggles). `/settings` panel
     gains `[0] Session Mode: gamified|focused` entry that reads
     `current_mode()` and prints diegetic line on flip ("Puck slips
     back through the door, grinning." for focused→gamified;
     "The forge falls quiet." for gamified→focused). New module:
     `hosts/cli/mode_cascade.py`. 15 tests (11 cascade unit + 4
     panel integration).
   - **Slice 2 — `_invoke_agent_live` helper + `/replay-tutorial`
     command** (next): A2A timeout-and-fallback wrapper, plus the
     replay slash command that runs the (still-stub) flight scene
     against the existing profile.
   - **Slice 3 — flight scene beats 1-14** (substantive): the
     actual cinematic onboarding rewrite of `run_onboarding`.
     Replaces the current scripted form with the Puck-narrated
     flow, integrates the mode cascade at beat 13, captures the
     idea pitch as the first session message.
   - **Slice 4 — first-message routing in `__main__.py`**: feeds
     the captured idea pitch into Hephaestus as the session
     opener instead of the current hardcoded greeting.
4. **M6 ElevenLabs hybrid implementation** — spec'd 2026-05-05 (see
   "M6 — ElevenLabs hybrid" above for adapter design, cache layer,
   sub-task ordering). Open questions answered against ElevenLabs's
   May 2026 docs: client-side cache (no server-side cache by request
   hash); v3 keeps brackets, others strip; skip `<break>` everywhere
   per ElevenLabs's own instability warning. Implementation queued;
   production swap still gated on M20 + VN smoke landing first —
   character voice quality matters most when the rest of the
   dialogue UX is dialed.
5. **M18 Phase 3 Part B** — distinct render paths for `KIND_CODE` /
   `KIND_SPEC`. Blocked on a specialist actually emitting either kind.
6. **M5 / M12 / M15 follow-ons** — see ROADMAP for scope.

Music playlist (#11) — content-driven; AJ adds tracks to
`assets/audio/music/` over time. No code work.
