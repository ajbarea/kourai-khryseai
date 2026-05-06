# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When a
milestone lands, its detail block in [ROADMAP.md](./ROADMAP.md) collapses
to a one-liner under "Shipped" and this file resets to the next milestone.
Git history is the archive — these docs are plans + scratchpad, not a
historical record.

Updated: 2026-05-06 · Active focus pivoted to **NE AI Agents Day 2026
poster prep** (May 8, Jane Street NYC; one of 55 posters, title
"Kourai Khryseai: Transparent Human-on-the-Loop Multi-Agent Software
Development"). The realistic review surface is QR-code-driven repo
browsing, not a live demo — so the next 48 hours go to: clean
README + getting-started, slop-free comments and docstrings, a
fresh-clone path that actually works. Once Friday is past, focus
returns to **M6 ElevenLabs hybrid** (sub-task 2 audio cache layer
shipped [#174]; sub-tasks 1/3/4/5 still gate on M20 + VN smoke).

Pre-release perfection stance unchanged: no workarounds, web-search
current best practice **at the planning step**, architectural fix
over expedient patch.

## Pre-presentation hygiene (next 48h)

Concrete blocker list for the QR-code reviewer experience.

### Shipped today

- **Docker runtime image fix** [#182]. `kourai_common.paths` walks for
  the workspace pyproject; runtime stage didn't ship it. All 10 agents
  plus vn-bridge crash-looped at import (11 Python services total).
  One-line `COPY` in the runtime stage.
- **ROADMAP Shipped section collapsed to one-liners** [#183]. 959 →
  811 lines. Per the section's own header convention.
- **Pre-presentation slop sweep + doc-accuracy fixes** [#184 — open].
  4 parallel deslop subagents → ~30 high-confidence edits: dropped
  `{CURRENT_DATE} Best Practices` template prefix from 9 agent prompts,
  stripped floating `April 2026` / `as of 2026-05` markers from
  shared/ + scripts/ + docker-compose / Dockerfile / Makefile /
  pyproject. Plus four follow-on commits of fact-checking against the
  canonical code:
  - README + getting-started: wrong agent count ("6 agents" → 10),
    wrong clone target dir (underscore → hyphen), outdated VN launch
    instructions referencing a vendored SDK path that doesn't exist
    in-repo (replaced with `make vn` resolver pointer).
  - README LLM tier table: drift from `shared/src/kourai_common/config.py`.
    `standard` row had Metis as Opus (actual Sonnet) and Dokimasia as
    Sonnet (actual Haiku); `smart` row had Hephaestus + Techne as Opus
    (actual Sonnet for both). Fixed against the canonical mapping;
    pointer added to `docs/configuration.md` for the four spirits' rows
    that the README simplified table still omits.
  - `docs/cli.md`: missing `/scratchpad` (#176) and `/preferences`
    (alias `/prefs`, M17 Phase 2). Added.
- **Verified GitHub repo + docs site state.** GitHub description +
  topics + homepage URL are correctly set. Docs site at
  `https://ajbarea.github.io/kourai-khryseai/` builds and serves; nav,
  hero, agent grid all current; "Ten AI agents" framing matches
  README/getting-started post-fix. Top nav: Home, Overview, Getting
  Started, Agents, Architecture, Interfaces, Configuration, Pricing,
  Research.

### Open before Friday

- **Hephaestus aiohttp `TimeoutError` on M14 parallel routing.** Smoke
  on 2026-05-06 sent `"hi dokimasia, are you there?"` to hephaestus;
  HTTP 200 SSE opened but body never streamed. Container logs show
  `_execute_completion failed (attempt 2), retrying in 4.4s:
  TimeoutError`. Network from inside the container reaches
  `api.anthropic.com` cleanly via `urllib`; the hang is at the LiteLLM
  + aiohttp transport layer specifically. Retry logic IS firing — so
  the system is resilient, just slow. **Not a presentation blocker
  since AJ isn't live-demoing**, but a real DX bug. File a GitHub
  issue with reproduction + log capture; investigate after Friday.
- **`docs/configuration.md` accuracy pass.** Has it drifted alongside
  the agent count? Tier table in README references 6 specialists; the
  4 spirits (aidos/aletheia/cupid/puck) aren't listed. Decide whether
  spirits get tier rows.
- **`docs/cli.md` slash-command list audit.** `/scratchpad` shipped in
  [#176]; `/settings [0]` shipped in [#168]. Are they listed?
- **`docs/agents/index.md`** — does it still describe the right roster?
- **One more pass** of host-area narrative WHAT-comments that the
  initial deslop subagent flagged but #184 skipped to scope-control
  (Manages/Handles/Provides docstring rewrites). Lower priority than
  the doc-accuracy items.

## M6 — ElevenLabs hybrid (pre-player-release blocker)

Promoted from "future-future" 2026-05-03; spec'd 2026-05-05 against
ElevenLabs's actual May 2026 docs. Character voice IS the product
(Hephaestus gruff vs Kallos lilting); Kokoro swaps voicepacks but can't
deliver per-character emotional control. ElevenLabs can.
[VOICE_CASTING_PLAN.md](../tools/voice-lab/VOICE_CASTING_PLAN.md)
already casts voice IDs + per-maiden settings.

### Engine + model strategy

| Model | Use | Latency | Price | Markup support |
|---|---|---|---|---|
| `eleven_flash_v2_5` | routine dialogue, handoffs | ~75ms | $0.06 / 1k chars | `<break>` works but ElevenLabs warns against overuse — use natural punctuation |
| `eleven_v3` | victory lines, key handoffs, onboarding | ~1-2s | $0.12 / 1k chars | `[bracket]` audio tags for emotional control; **no** SSML break tags |

### Required add-ons before player release

#### 1. Per-engine markup adapter

Producers emit plain text with optional inline `[bracket]` audio
direction hints. The adapter at the engine boundary translates per
target engine:

| Engine | Behavior |
|---|---|
| `eleven_v3` | Keep `[bracket]` tags. Tag effect decays after ~4-5 words; producers should write short tagged segments. Layered tags supported (`[nervously][whispers]`). |
| `eleven_flash_v2_5` / `eleven_multilingual_v2` | Strip brackets — v3 audio tags don't apply. Emotional tone comes from `voice_settings.style` + low `stability` + per-maiden voice training. Skip `<break>` per ElevenLabs's instability warning. |
| `kokoro` (current) | Strip brackets. No SSML, no audio tags; punctuation carries everything. |

Tag vocabulary (lift from ElevenLabs's documented set, scoped to
maidens — skip the cinematic ones that don't fit pipeline dialogue):

- Voice cues: `[whispers]`, `[sighs]`, `[exhales]`, `[laughs]`,
  `[sarcastic]`, `[curious]`, `[excited]`, `[crying]`
- Layered (per ElevenLabs docs): `[nervously][whispers]`,
  `[softly][sighs]`, etc.
- Skip: `[applause]`, `[clapping]`, `[gasps]`, `[sings]`, accent
  tags — too rare or character-mismatched.

The existing `kourai_common.ssml.strip_ssml` defensive layer stays in
place. Order at the engine boundary: strip SSML (defensive) → apply
engine markup adapter → synthesize.

`research(2026-05)`: ElevenLabs `prompting/eleven-v3` audio-tag list,
help-center "How do audio tags work with Eleven v3" 4-5-word decay note,
help-center "Do pauses and SSML phoneme tags work" model support matrix.

#### 2. Audio caching layer — SHIPPED [#174]

`kourai_common.tts_cache.cached_synthesize`. Engine-agnostic via
fetch-injection; same module wraps Kokoro now and ElevenLabs at sub-task
3 swap. Cache key:
`sha256(length-prefixed(text, voice_id, model_id, sorted-keys-json(voice_settings)))`.
Layout: `${XDG_CACHE_HOME:-~/.cache}/kourai/tts/{key[:2]}/{key}.{ext}`;
oldest-mtime-first eviction at 500 MB cap. Opt-in via
`RealtimeTTSEngine(cache_dir=...)`; enabled at vn_bridge construction
where static dialogue dicts repeat across players. CLI / GUI integration
deferred — current `speak()` streams synth into PyAudio playback rather
than returning bytes; routing through cache is non-trivial. Re-enter
when ElevenLabs swap forces `speak()` to refactor against bytes.

#### 3. Per-persona prosody design pass

With adapter + cache shipped and ElevenLabs reference audio in hand
(via `tools/voice-lab` Next.js scratchpad), decide per-maiden defaults:

- Kallos: `[whispers]` for teasing asides, lower stability for expressiveness.
- Dokimasia: `[sarcastic]` defaults during validation failures.
- Aidos / Aletheia: highest stability + lowest style for clinical / authoritative validation tone (already in VOICE_CASTING_PLAN.md).
- Hephaestus: gruff via `style` slider + voice training (no `[gruff]` tag exists).

Deferred under the SSML plan; now design-tractable against real
reference audio post-adapter-ship.

### Sub-task order + gating

1. **Per-engine markup adapter** — `kourai_common.tts_markup.apply_engine_markup`. Ships when caller exists (i.e., bundled with sub-task 4).
2. **Audio cache layer — SHIPPED [#174]** (see #2 above).
3. **ElevenLabs SDK integration** — `pyproject.toml` adds `elevenlabs` dep; new `ElevenLabsEngine` class implementing the same `RealtimeTTSEngine` public surface. Engine selected via `KOURAI_TTS_ENGINE=elevenlabs|kokoro` env (default `kokoro` until cutover). `client.text_to_speech.convert(voice_id, text, model_id, voice_settings=VoiceSettings(...), output_format)` returns bytes.
4. **Voice-lab → production wiring** — flip default to `elevenlabs`, smoke through CLI / GUI / VN.
5. **Per-persona prosody pass** — tune voice_settings + audio tag defaults per maiden against reference audio.

**Production swap gated on M20 + VN smoke landing first** — character
voice quality is most visible against a polished dialogue UX; doing M6
before audio-led reveal lands would burn ElevenLabs spend chasing UX
bugs we already know about.

### Cost projections (2026-05 ElevenLabs API pricing)

- Pre-release dev (~200 lines/day × 50 chars): ~$22/month.
- 100 active players (~200 lines/session × 30 sessions): ~$2,160/month uncached → ~$430-1,080/month after cache layer (50-80% hit rate on static dialogue, near-100% on v3 lines after warm).
- 1000 active players: ~$21,600/month → ~$4,300-10,800/month with cache.

## Notes / open invariants

- **MCP elicitation deferred-by-design.** Real-caller-driven only.
  Architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design when the first forge MCP tool wants `ctx.elicit()`.
- **MCP spec version pinned to 2025-11-25** — confirmed still current as
  of 2026-05-06 (no new revision since November 2025; v2.1 SEPs in
  flight, not yet adopted). Spec drift watcher cron
  (`scripts/watch_protocols.py`, runs Sundays 13:00 UTC) flags any
  subsequent revision.
- **`run_post_task_hooks` orchestration unwired.** Layer is fully tested
  but no production call sites; `synthesise_fact_from_pause` lives
  directly in `streaming.py` as the pragmatic answer. Promotion is
  sibling work flagged for M5/M6.
- **Specialist parity for fact recall.** Today only metis reads
  `build_fact_context` with project scope; techne / kallos / dokimasia /
  hephaestus inherit the gap. Defer until a non-metis PAUSE caller
  surfaces.
- **Server-side conversation compaction (Anthropic Opus 4.6+).**
  Anthropic's 2026-05 cookbook recommends server-side compaction over
  manual `_manage_memory`-style summarization for Opus 4.6+ — handles
  context-window management automatically without SDK-level config via
  `client.beta.messages.tool_runner` with `compaction_control`.
  Migration is a multi-PR refactor: 1) verify LiteLLM passes the beta
  header (uncertain), 2) dual-provider design (Anthropic uses
  server-side, Gemini/Ollama keep manual), 3) existing `_manage_memory`
  becomes the fallback. The cheap-tier pin (#180) captures ~80% of the
  cost win without that refactor risk; defer until the remaining 20% is
  worth it.
- **Sisters audit weekly cron** (`trig_013uP9ryCLYscBKS7X6PB5og`, Mondays
  12:00 UTC) opens drift PRs and a rollup issue automatically.
- **Issue #126 auto-rescan** (`.github/workflows/issue-126-rescan.yml`)
  fires Saturdays 14:17 UTC from 2026-05-16 until npm bundles
  `@xmldom/xmldom>=0.8.13`. Upstream landed 0.8.13 in 2026; the rescan
  will detect once npm cuts a release with the bumped pin.
- **DRY-sweep follow-ups deferred from [#170]:**
  - **pyloudnorm migration of `AudioNormalizer`** in
    `kourai_common.audio_dsp`. Today's hand-rolled LUFS approximation
    works; ITU-R BS.1770-4 via pyloudnorm is technically correct but
    requires re-tuning the per-personality profiles in `AGENT_PROFILES`.
    File when an audio-quality callback surfaces.
  - **VN demo-script bridge.** `kourai_common.demo_script` is consumed
    by CLI and GUI; VN's `script_poster_demo.rpy` keeps a header comment
    cross-reference rather than a real import (Ren'Py can't import Python
    at script-time without bridge gymnastics). Build a `.rpy` codegen
    pass when the demo script needs another change.
  - **Pydantic v2 migration of `CLISettings` / `SettingsManager`.** The
    new `AudioSettings` is a `@dataclass` to match the surrounding style;
    full migration would touch settings persistence, slash-command
    panels, and tests. File when a settings-validation pain point
    surfaces.
- **M18 Phase 3 Part B** — distinct render paths for `KIND_CODE` /
  `KIND_SPEC`. Both kinds are reserved tokens with no producer; building
  host-side render paths is anticipatory infra. Re-enter once a
  specialist (likely techne for code, metis for spec) opts into emitting
  these kinds.

## Up next — priority order

Pre-release perfection stance: no workarounds, web-search May 2026 best
practice **at the planning step**, architectural fix over expedient patch.
Pick by impact + caller reality, not file-of-origin.

**Live-smoke gated** (need AJ at the keyboard):
- **Live VN smoke end-to-end** — exercises the vn_bridge `/tts` →
  `RealtimeTTSEngine.synthesize_to_wav` path + metadata-based dialogue
  routing. Includes M20 sub-task 2/4 cps verification (Ren'Py-side
  cps math from the `X-TTS-Duration-Seconds` header) and the VN
  synthesis indicator that's gated on the Ren'Py wrapper.
- **M6 sub-tasks 1, 3, 4, 5** — markup adapter / ElevenLabs SDK /
  production swap / per-persona prosody pass; gated on M20 + VN smoke
  landing first.
- **Puck Slice 3 + 4** — flight scene rewrite, first-message routing.
- **VN dialogue-presentation polish** (illuminated-manuscript framing) —
  parchment + plaque corner flourishes, epithet subtitle.

**Self-contained workable** (ship clean without AJ in-loop):
- **Puck Slice 2 helper** — `_invoke_agent_live(agent, prompt, fallback,
  timeout)` A2A timeout-and-fallback wrapper. Skip the
  `/replay-tutorial` command pending Slice 3 (replays a still-stub
  flight scene = anticipatory).
- **Cross-host pipeline-status** — `kourai_common.pipeline_status`
  data layer (PipelineState frozen + PipelineTracker with handoff hooks)
  + vn_bridge wiring (replaces the local `current_agent` variable). GUI
  integration (refactor of GUIState's agent fields) deferred to Phase 2.
- **Cross-host status-feed** — `kourai_common.status_feed` (RingBuffer[T]
  + StatusEvent typed record). One writer, three subscribers (CLI
  `/debug` slash, future GUI bottom overlay, file-write). Replaces
  debug_log.py + the deleted status_bubbles parallel state stores.
- **Cross-host gossip-render** — `kourai_common.gossip_render`
  (RenderedRound). gossip_core / gossip_models already canonical
  from #170; what's missing is the host-agnostic structured-render
  translation. Renderers collapse to ~30-line ANSI / pygame / Ren'Py
  adapters.
- **Cross-host codex** (in-game encyclopedia) — biggest scope; fixes
  the broken VN codex screens; Mass Effect-shape data + unlock triggers.
  Best done as one large PR; live smoke needed for VN parchment-book
  renderer.
- **Per-agent motion language** — polish, lands last.

Music playlist (#11) — content-driven; AJ adds tracks to
`assets/audio/music/` over time. No code work.
