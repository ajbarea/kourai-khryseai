# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-05-21 (post-#215, post-platform-reliability sweep).
**NE AI Agents Day 2026 poster session shipped 2026-05-10** (NYC, Jane Street; QR-code demo live).
Polish phase complete. **M6 (ElevenLabs hybrid) is deferred post-funding**
(decided 2026-05-24): Kokoro ships as the TTS engine for the foreseeable
future, and the premium-voice expansion waits until funding plus a re-survey
of the fast-churning TTS landscape. Sub-task 2 (audio cache) already shipped
[#174]; M6 is no longer a pre-player-release blocker. See
[IMPL.md](./IMPL.md) for the live blocker list, open invariants, and
priority-ordered "Up next".
Pre-release perfection stance unchanged: current best practice no
matter the cost, **web-search the SPECIFIC target's primary docs at the
planning step**, architectural fix over expedient patch. Sister-repo
audit weekly cron runs Mondays 12:00 UTC.

---

## Why this file exists

If you've cloned the repo and want to know "what are they building next, and
why," this is the answer. We commit it because the forge isn't a black box —
the maidens, the pipeline, the protocol choices, all of it should be legible
to anyone watching.

If something here looks wrong-headed, open an issue. The roadmap is opinionated
but not precious.

---

## Guiding principles

- **Schema over prose.** When the LLM has to produce structured output (file
  writes, edits, deletes, lint fixes), use provider tool-use with JSON Schema —
  not regex on prose. A bold-wrapped keyword is a bug; a missing keyword
  silently succeeding is a disaster.
- **Stream what we can; don't fake what we can't.** Pipeline stages take
  minutes. Stream `working` updates so the player sees motion, not a spinner.
- **One protocol per concern.** A2A for agent ↔ agent. MCP for tool/resource
  access. Anthropic tool-use for the in-LLM loop. Don't reinvent any of them.
- **Fix-first, then delete.** Migrate before removing. The forge always runs.
- **Agents speak, don't emit.** The maidens are characters, not CLI tools.
  Render output by what the agent is doing, not who the agent is:

  | When an agent is… | Render as |
  |---|---|
  | **Talking** — greeting, question, handoff line, commentary, explanation addressed to the player | `"quoted"` + italic |
  | **Working** — analyzing, running tests, listing findings, streaming file ops | plain, with emoji prefix |

  One rule, two modes. Matches how fiction has marked dialogue vs action for
  300 years and makes clarifying questions pop against the status stream.
  Shipped in M10 (2026-04-26).
- **Dynamic-first sizing.** No pixel value is safe to hard-code. Panel widths,
  portrait dimensions, padding, button heights, line spacing, font sizes —
  all of them must respond to window size and font scale. Treat
  `screen.get_size()` and the active font-scale multiplier as the source of
  truth for every dimension; a constant expressed in pixels is a bug waiting
  for a resize or zoom step to surface it. When you notice a fixed value in
  `constants.py` being read at import time, convert it to a function of the
  current display dimensions. Tracked in
  [M12](#m12--dynamic-sizing-across-the-gui).

---

## M5 — Permissions / UID alignment (forge worktree)

> Status: planned · Quality-of-life

Container UID 1000 vs host UID 1001 produces zombie `.pytest_cache` dirs the
host can't unlink. Today's mitigation is `pytest -p no:cacheprovider`, which
suppresses one symptom. The real fix is one of:

1. Run specialist containers as the host UID via `--user $(id -u):$(id -g)`
   in compose.
2. Use POSIX ACLs on the worktree mount.
3. Cleanup pass via `docker exec -u 1000` to chmod-then-rm during teardown.

Option 1 is cleanest if it doesn't break agent-internal deps that assume UID 1000.

---
## M6 — ElevenLabs hybrid (deferred — post-funding)

> Status: spec'd 2026-05-05 · **Deferred 2026-05-24 — ship Kokoro-only until
> funding** · Spec preserved below for the eventual revisit. Re-survey the
> TTS landscape first (it churns yearly); ElevenLabs is the confirmed quality
> target (by ear + TTS Arena #1), with Gemini 3.1 Flash TTS a ~4x-cheaper
> middle option worth a bake-off.

Promoted from "future-future" 2026-05-03 after strategic review of the
character-voice-quality gap between Kokoro (current) and ElevenLabs.
Character voice IS the product (per-maiden personality is the core
mechanic); Kokoro plays 10 voicepacks but cannot deliver per-character
emotional control. ElevenLabs can.

Spec landed 2026-05-05; verified against ElevenLabs's May 2026 docs.
[VOICE_CASTING_PLAN.md](../tools/voice-lab/VOICE_CASTING_PLAN.md) has
voice IDs + per-maiden settings cast. The `tools/voice-lab/` Next.js
app is the casting/preview surface that landed pre-2026-05; production
wiring (M6) is the swap from Kokoro into the same `RealtimeTTSEngine`
public surface.

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

---

## M8 — MCP session pooling (upstream-blocked)

> Status: blocked on upstream SDK fix · Discovered 2026-04-23

We'd like repeated ``query_context7`` / ``search_memory_nodes`` calls to reuse
one ``ClientSession`` rather than re-doing TLS + ``initialize()`` per call.
Attempted on 2026-04-23 via ``AsyncExitStack``-based pool; reverted because
the MCP SDK's ``streamable_http_client`` yields inside an
``anyio.create_task_group()`` cancel scope. Cross-task teardown raises
``RuntimeError: Attempted to exit cancel scope in a different task``.

This is upstream — see
[python-sdk#466](https://github.com/modelcontextprotocol/python-sdk/issues/466),
[#713](https://github.com/modelcontextprotocol/python-sdk/issues/713),
[#915](https://github.com/modelcontextprotocol/python-sdk/issues/915) and
[PEP 789](https://peps.python.org/pep-0789/) (async-generators-inside-cancel-scopes).

**When the upstream SDK exposes pool-safe primitives**, revisit pooling.
Meanwhile OTEL spans around each call give us per-tool latency visibility
(landed 2026-04-23), which was the other half of the win.

---

## M12 — Dynamic sizing across the GUI

> Status: planned · Blocked by: nothing (can land anytime)

**The principle:** every pixel value in the GUI should respond to
window size × font scale. No fixed constants read at import time.
(See guiding principle "Dynamic-first sizing" above.)

**Where we are today.** The font layer is responsive: `constants.FontProxy`
reads a scale registry (`constants.set_font_scale`), and on 2026-04-23
a listener-callback registry landed so text-caching widgets
(`DialogueHistory`, `DialogueHistoryWithAutoScroll`) re-rasterise their
transcript surfaces when the scale changes. Ctrl+=/-/wheel scales text
crisply, panels reflow at their current width.

**Where we aren't.** Every **non-font** dimension is still a fossil:

- `PORTRAIT_W = 310` in `constants.py` — read at import, never revisited
- `DIALOGUE_X = PORTRAIT_W + 8`, `DIALOGUE_W = W - PORTRAIT_W - 8` — derived
  from a fixed base `W`/`H`, not the runtime window
- `INPUT_H = 80`, `AGENT_LINE_H = 14`, `LINE_H = 20`, `PAD = 14` — literal
  numbers sprinkled through `dialogue.py`, `render.py`, `input_bar.py`
- Settings-overlay panel padding, border thicknesses, overlay icon sizes,
  button corner radii — all pixel-literal
- Portrait-panel quote text geometry, alignment-gauge dial sizes, gossip-
  bubble inset offsets

At zoom ≤ 1.3× most of this is tolerable because of the text-wrap-at-
runtime behaviour in `dialogue.py::_entry_height`. Past 1.5× a long
user bubble still overflows its panel because `BUBBLE_MAX_W = DIALOGUE_W - 40`
anchors to the *import-time* constant, not the live dialogue rect width.
At 2.0× zoom the input bar chrome breaks visibly.

**Why it matters.** Accessibility (visually-impaired players *need* zoom
to work), high-DPI laptops (default rendering is tiny), screenshotting
for poster/docs/demo, and eventual multi-monitor use where someone drags
the window to a 4K panel.

**Scope.**

- Introduce a `LayoutMetrics` dataclass that computes all derived values
  from `(screen_w, screen_h, font_scale)`. Replace direct reads of
  `constants.PORTRAIT_W` etc. with `layout.portrait_w`. The metric values
  are recomputed on resize and on font-scale change.
- Extend the listener registry (`on_font_scale_change`) with
  `on_resize` for a uniform notification story, and have `sync_layout()`
  in `__main__.py` fire both when appropriate.
- Pass the live `LayoutMetrics` into `RenderPipeline.render()` the same
  way `dialogue_rect` is passed today; every draw method takes what it
  needs off the metrics object instead of re-reading `constants`.
- Audit `dialogue.py`, `input_bar.py`, `portrait.py`, `settings_overlay.py`,
  `alignment_gauges.py`, `gossip_panel.py`, `memory_viewer.py`,
  `onboarding_ui.py` for hard-coded pixels. Most can become
  `metrics.pad`, `metrics.line_h`, `metrics.bubble_max_w`, etc.
- When a widget's rendered surface depends on metrics (not just text),
  wire it to the resize/font-scale listeners so its `_dirty` flag trips
  the same way the dialogue history now does.
- At the very top: move `W`, `H`, `_PREFERRED_WINDOWED_SIZE` out of
  `constants.py` — they describe a "preferred" initial mode only, they
  should never be treated as the authority for runtime geometry.

**Done when.**

- `grep -rn "= [0-9]\+" hosts/gui/constants.py | grep -v "_scale\|MIN_\|DEFAULT_"`
  returns only the preferred-window-size defaults and literal colour
  values. No geometry literals.
- Zoom slider in settings goes 0.8× → 2.0× with no layout clipping,
  portrait resizing alongside text, input bar, panels, padding all
  growing proportionally.
- Resizing the window to a narrow aspect ratio doesn't push the user-
  message bubble off-screen.

Reference: font-scale registry landed 2026-04-23 in
`hosts/gui/constants.py::set_font_scale` + `FontProxy` + `on_font_scale_change`.
`DialogueHistory._mark_dirty_from_font_scale` is the template for every
widget that caches rendered surfaces.

---

## M15 — Forge logging architecture

> Status: partial — LiteLLM DEBUG demote shipped; OTel trace-ID
> correlation shipped (`_OtelTraceFilter` in `shared/src/kourai_common/log.py`);
> dev-runner-latest.log rename shipped. Host bind-mounts + tool-event JSONL
> + session-id correlation remain planned · Operational hygiene ·
> Surfaced 2026-04-26 during M1 Round 6 validation

What Round 6 exposed: the host's `logs/` directory has stale per-agent log
files (`logs/hephaestus.log`, `logs/metis.log`, `logs/kallos.log`,
`logs/dokimasia.log` all from earlier sessions, NOT from the live smoke
run). The live agent traces only live inside containers — `docker logs
kourai-khryseai-techne-1` was the only way to validate that 22 `'type':
'tool_use'` frames flowed during the smoke. That's brittle for post-mortem
work, smoke validation, and CI artifact collection.

**Why.** Smoke recipes that grep host log files (`SMOKE_TODO.md` Round 6
told you to grep `logs/dev-latest.log` for tool_use frames — that file is
now `logs/dev-runner-latest.log`) silently never matched because the log
mount was broken. Future smoke recipes will hit the same wall. Beyond
smoke, tool-event observability matters for poster demos, customer
support, and onboarding new contributors who want to see what the swarm
actually did.

**Scope.**

- **Host log volume mounts.** Compose services bind-mount each container's
  `/app/logs/` to the host's `./logs/<agent>.log`. Today only the CLI host
  log lives there reliably. Verify and fix in `compose.yaml`.
- **Structured tool-event log.** New emitter in
  `shared/src/kourai_common/llm.py::chat_with_tools` writes one line per
  tool call: `session=<id> agent=<name> tool=<name> path=<arg> ms=<elapsed>
  result=<ok|fail>`. Lands in `logs/tool_events.jsonl` on the host. Smoke
  recipes grep this file directly — no more LiteLLM DEBUG payload spelunking.
- **Session-id correlation.** Forge sessions have a stable `946e593a` ID;
  thread it through `setup_logging()` as a logger filter so every record
  emitted during a session carries `session_id=<id>` in the format string.
  Then `grep session=<id> logs/*.log` answers "what happened in session X"
  in one command. **Partial today:** `_OtelTraceFilter` already injects
  the OTel trace-id (32-char hex) into every record via the format string;
  session-id is the orthogonal correlation key that still needs threading.
- ~~**Rename / retire `dev-latest.log`.**~~ **Shipped 2026-05-19** —
  renamed to `logs/dev-runner-latest.log` across `dev_log.py`,
  `dev_cli.py`, the Makefile `logs` / `logs-tail` targets, and the
  per-script error pointers. The name now reflects its actual content
  (dev-runner wrapper output) instead of implying it holds live agent
  traces.
- ~~**Demote LiteLLM DEBUG default in containers.**~~ **Shipped** —
  `shared/src/kourai_common/llm.py:33` sets `litellm.suppress_debug_info = True`
  unconditionally; there are no `litellm.set_verbose = True` call sites
  anywhere in the codebase. Smoke runs that want LiteLLM verbosity can
  toggle locally; production-ish runs are quiet by default. (Verified
  2026-05-19 via `grep -rn 'litellm.set_verbose\|litellm.verbose'`.)

**Done when.**

- `ls logs/` on the host shows live, modified-during-the-run log files for
  every agent that ran (techne, hephaestus, metis, dokimasia, kallos, mneme).
- `grep -nE 'tool_use.*write_file' logs/tool_events.jsonl` returns hits
  during a smoke run (no more `docker logs` workaround).
- `grep session=<forge_id> logs/*.log` returns every event for that session
  across all agents.
- SMOKE_TODO.md Round 6 recipe updated to use the new grep targets.

---

## M18 — Structured streaming with content-kind metadata

> Status: Phase 1 + Phase 3 Part A shipped · Phase 2 (SSML) active in
> [IMPL.md](./IMPL.md) · Phase 3 Part B (KIND_CODE/SPEC render paths)
> deferred until a producer emits either kind

URI-namespaced extension key
`https://kourai.khryseai/ext/streaming/v1` carries
`{"content_kind": "dialogue" | "status" | "code" | "spec"}` on
`Message.metadata`. All eleven agents (10 producers + 1 consumer)
tag emissions, plus the hephaestus pipeline forwarder and
`BaseAgentExecutor`'s empty-input prompt. Hosts route by metadata
strictly: `kind == KIND_DIALOGUE` is the only TTS-eligible path on
the CLI; vn_bridge mirrors the same predicate for Ren'Py routing.
Untagged messages (`kind is None`) no longer fall back to a prose-
keyword guess — they're treated as not-dialogue, so any future
producer that forgets to tag will silently miss TTS rather than
mask the bug. Phase 2 (SSML inside dialogue bodies — strip-then-
synthesize for Kokoro, full subset for Azure/Google/non-v3-
ElevenLabs downstream) is the next architectural work; see
IMPL.md for the live spec.

### Content-kind taxonomy

| `content_kind` | Render path | TTS-eligible | Gate next event |
|---|---|---|---|
| `dialogue` | comms-window italic | yes (post-SSML) | yes |
| `status` | comms-window plain | no | no (fire-and-forget) |
| `code` | comms-window monospace | no | no |
| `spec` | wide markdown render | no | no |

Hosts route by metadata, not by parsing text or emoji-prefix
detection. Sibling fields (priority, subkind, ssml_version) live
under the same URI without colliding with other extensions.

---

## M20 — Audio-text synchronization across CLI / GUI / VN

> Status: in progress · Sub-task 1 (Kokoro voice + pipeline pre-warm)
> shipped 2026-05-02 · Sub-task 2 (audio-led reveal) Tier 1+2 shipped
> for CLI 2026-05-15 (boot greeting + streaming dialogue) and GUI
> Tier 1 shipped (typewriter word-paced mode); Sub-task 3 three-surface
> rollout — VN-side pending live smoke; Sub-task 4 settings toggles —
> `dialogue_sync_mode` shipped, `text_speed_factor` + `tts_everything`
> still planned · Surfaced 2026-04-29 (post-rebuild CLI session) ·
> Depends on M19 (RealtimeTTS provides word-level timing callbacks for
> Kokoro English voices) and M18 (content-kind metadata routes
> dialogue-only to the synced reveal path) · Player- and developer-
> experience improvement spanning all three player surfaces

### Why

A maiden's dialogue text appears in the CLI / GUI immediately, then
TTS audio plays whenever Kokoro is ready. The first speak() per
session pays a ~10-14 second cold-start (Kokoro lazy-loads pipelines
per `lang_code` on first use). Concrete 2026-04-29 example: AJ
launched `make cli`, saw Hephaestus's opening line `"I didn't get
thrown off Olympus to write bad software."` printed at 12:55:49,
heard the same line at 12:55:58 — **9 seconds of "text shown but
no audio" silence**, then 4 seconds of audible delivery.

**Steady-state lag (measured 2026-05-03 after sub-task 1 + #145
unblocked vn_bridge observability):**

| surface             | path                       | lag                  |
|---------------------|----------------------------|----------------------|
| CLI / GUI streaming | `RealtimeTTS.play()`       | ~3s to first chunk   |
| VN (vn_bridge)     | `synthesize_to_wav` (full) | ~4-7s for 50-char    |

Throughput is ~45 ms/char on streaming `play()` (audio + synthesis
overlap), ~120 ms/char on `synthesize_to_wav` (no overlap, full WAV
returned before Ren'Py plays). The ROADMAP's earlier "~1-2s
steady-state" framing was wrong on both surfaces — sub-task 2 is
load-bearing for both, not aesthetic-only on either.

The visible+audible disconnect breaks the character-presence
illusion the maidens depend on. Hephaestus's deadpan line lands in
print before the player can hear his voice deliver it; by the time
audio plays, the player has read past it. This is the exact failure
mode VN best-practice writes against — community guidance from
Fuwanovel and commercial VN engines (Ren'Py, Kirikiri, Visual Novel
Maker) is consistent: **adjust text reveal speed to match voice line
duration** so the player can't out-pace the actor.

The 2026 modern content-creation standard for synced text+audio is
**word-level timing**: each spoken word gets a precise audio
timestamp, the visual layer reveals each word as it's spoken
(karaoke-style highlighting). Used everywhere from TikTok captions
to professional subtitle workflows. RealtimeTTS exposes this
natively for Kokoro English voices via the engine's word-timing
callbacks (Phase 1 of M19 unlocks the API).

### Scope

**1. Pre-warm Kokoro at startup, per language code AND per voice.**
Eliminates the 10-14s first-speak cold-start. Two layers, both at
`RealtimeTTSEngine.__init__`: (a) `_prewarm_agent_languages` calls
`KokoroEngine._get_pipeline(lang_code)` once per unique
`AGENT_VOICE_MAP` lang_code, loading model weights + G2P (~80MB
per language) — already shipped pre-M20; (b) `_prewarm_agent_voices`
iterates every agent voice and calls `KPipeline.load_single_voice`
to materialize the .pt tensor (~5-10MB each) into the per-pipeline
voice cache so the first per-agent utterance skips the per-voice
download/parse cost. Trades startup latency (deterministic, ~7-10s
window) for a smooth first-utterance per agent. Both layers
shipped 2026-05-02.

**2. Audio-led text reveal.** Replace immediate text rendering with
deferred-render gated on TTS readiness. Two precision tiers:

- **Tier 1 (English voices, RealtimeTTS word-timing supported):**
  word-by-word reveal in lockstep with audio. Subscribe to the
  RealtimeTTS word-timing callback; advance a word cursor on each
  callback fire; render the next word into the visible region.
  Karaoke-style — the audio defines the cadence.
- **Tier 2 (no word timings — non-English Kokoro voices, Edge TTS,
  future engines):** hold text rendering until the first audio
  chunk is queued (i.e., synthesis has produced *something*
  playable). Renders the full text at audio start. Less precise
  but eliminates the "text precedes audio" disconnect. Falls back
  to instant-render only when TTS is disabled entirely.

**3. Three-surface implementation.**

- **CLI (`hosts/cli/streaming.py` + `hosts/cli/rendering.py`):**
  Replace immediate `_echo(_comms_window(...))` with a deferred-
  render that holds the box content until either (a) first audio
  chunk queued, or (b) word-timing callback fires. Box renders
  progressively as words speak.
- **GUI (`hosts/gui/tts_gui_integration.py` + the dialogue panel
  renderer):** Pygame text-rendering loop already polls per-frame;
  add a word-cursor that advances on TTS word-timing callbacks.
  Existing typewriter mechanics stay; cadence is now audio-driven
  rather than constant-rate.
- **VN (Ren'Py via `agents/vn-bridge`):** Ren'Py natively supports
  the `voice` statement with text-pacing through the `cps` (chars
  per second) variable. Bridge feeds audio + word-timing metadata;
  Ren'Py drives the typewriter natively. Per the 2022-2026 Ren'Py
  audio docs, `.ogg` and `.mp3` are the only supported formats —
  RealtimeTTS already produces compatible streams via the
  `KokoroEngine` output path.

**4. Settings toggles** (`/settings` in CLI, GUI dialog
preferences, VN config menu — all three surface):
- `dialogue_sync_mode`: `audio-led` (default — text reveals with
  voice) | `instant` (legacy — text appears immediately, audio
  catches up). Player preference; some readers want text first,
  audio as flavor.
- `text_speed_factor`: 0.5–2.0 multiplier on word-reveal speed
  for accessibility. Doesn't change audio rate; only adjusts the
  visual cursor when audio is muted or instant mode is selected.
- `tts_everything`: also TTS unquoted status updates (off by
  default — only quoted dialogue is voiced per SPEECH VS ACTION
  rule). Opt-in for blind / low-vision players who want fuller
  audio narration.

### Out of scope (defer to follow-on)

- Per-character mouth animation in GUI / VN (lip-sync to phonemes —
  separate animation milestone).
- Real-time STT for player voice input. RealtimeSTT exists in the
  same library family but is a distinct concern.
- Cross-language word-timing for non-English voices. Kokoro's word-
  timing API is currently English-only per RealtimeTTS docs;
  upstream feature, not ours to build.

### Acceptance

- CLI: maiden dialogue text reveals progressively in sync with audio
  playback. First-line lag eliminated by Kokoro pre-warm.
- GUI: dialogue panel typewriter matches voice cadence frame-by-frame.
- VN: Ren'Py `voice` + `cps` driven by RealtimeTTS word-timing
  metadata over the bridge.
- `/settings` exposes `audio-led` vs `instant` modes; default is
  `audio-led`. Player can switch.
- The 2026-04-29 reproducer no longer applies: Hephaestus's opening
  line text and audio appear together, not 9 seconds apart.

### Why now

UX/DX-default pre-release. The disconnect between text and audio is
a first-thing-the-player-notices issue — visible the moment any
maiden speaks. Pairs naturally with the M19 RealtimeTTS adoption
since the word-timing primitive is the load-bearing API; building
M20 on M18+M19 is one coordinated UX wave rather than three drips.

---


## M22 — Forge session replay + reproducibility capture

> Status: planned · Surfaced 2026-05-21 during platform-reliability sweep ·
> Combines the "killer VN mechanic" from the 2026-05-21 audit-of-audits
> backlog with reproducibility-capture as a platform guarantee
> (the article framing: "30-minute postmortem vs 3-day investigation").
> Depends on M24 (cleaner OTel attributes make replay/branch deterministic)

The forge already serializes every turn into `forge_sessions`. What's
missing is (a) the ability to stream those turns back through the same
UI for inspection / debugging / demo, (b) branching from an
intermediate turn to explore alternate maiden choices, and (c) capture
of the orchestration context needed to make a replay actually
deterministic. Today a discarded session leaves you with the diff; it
should leave you with everything needed to ask "why did Metis pick
this spec shape" three weeks later.

`research(2026-05)`: Anthropic's "How we built our multi-agent research
system" calls out replayable trajectories as load-bearing for
debugging multi-agent drift; platformengineering.org's Agent
Reliability framework (Test 14, reproducibility) frames the same
capture as turning open-ended postmortems into 30-minute scoped
investigations; Anthropic's [Managed Agents engineering essay](https://www.anthropic.com/engineering/managed-agents)
formalises the same primitive as a "session log [that] sits outside
the harness" — append-only, queryable by positional slice, durable
across harness crashes — which is exactly the API shape kourai's
`forge_sessions` SQLite layer + replay slash should converge toward.
Kourai stays local-first and provider-agnostic (not adopting the
hosted Managed Agents runtime), but the session-as-external-log
shape is the right design north star.

### Scope

**1. Per-session reproducibility capture.** Extend `forge_sessions`
SQLite schema with versioned-context columns:

- `per_agent_models JSON` — {agent_name: model_id} at session start;
  carries the full assignment, not just the tier, so a `standard`-tier
  session today vs after Sonnet 4.7 lands stays distinguishable.
- `prompt_template_hashes JSON` — {agent_name: sha256} hashed at
  session start; if `agents/<name>/prompts.py` changes mid-session,
  the hash anchors which version actually ran.
- `tool_schema_versions JSON` — {tool_name: version} for every
  forge / shell / memory-mcp / context7-mcp tool touched.
- `kourai_git_sha TEXT` — repo HEAD at session start; closes the
  "what code was the agent running" gap.

Populated lazily on first turn per session; `kourai_common.replay`
reads it as the canonical environment snapshot.

**2. `/forge replay <session_id>` slash.** Streams stored
A2A messages back through the same renderer (CLI, GUI, VN), with
configurable speed (`replay --speed 2x` or `replay --step` for
turn-by-turn). Branch points (where Hephaestus routed, where the
player accepted/discarded) get visual markers. Read-only — no
mutations, no LLM calls, no MCP writes.

**3. `/forge branch <session_id>:<turn_n>` slash.** Clones the
session up to turn N into a new `session_id`, then continues live
from that point — same environment snapshot (models / prompts / git
sha pinned via #1), different player input. Powers the dating-sim
"what if I'd told Metis to use sessions instead of JWT" exploration
without losing the original timeline.

**4. Replay-mode renderer affordances.** A small "REPLAY" / "BRANCH
FROM #N" badge in the CLI status bar + GUI title bar + VN
HUD so it's visually impossible to mistake a replay for a live
session. Mneme is suppressed entirely in replay mode (no commits
get drafted from re-rendered turns).

### Out of scope

- Cross-version replay (replaying a 2026-04 session against
  2026-08 models). Snapshot pins what *was*; deliberately not
  retro-fitting current model behavior onto historical context.
- Persisting MCP-server state alongside the session. memory-mcp
  drift between replay runs is accepted; replay re-issues queries
  but doesn't pin responses.

### Done when

- A discarded session can be re-streamed with `/forge replay <id>`
  and the dialogue lands character-for-character identical to the
  live run.
- `/forge branch <id>:5` produces a new session that picks up after
  turn 5 with the same environment snapshot, and Hephaestus's first
  routing decision in the new session uses the pinned model / prompt
  versions even if HEAD has moved.
- `SELECT per_agent_models, prompt_template_hashes, kourai_git_sha
  FROM forge_sessions WHERE id = ?` returns populated values for
  every session created post-M22.
- The 2026-05-21 backlog bullet "Forge session replay & branching"
  collapses to this milestone.

---

## M23 — Execution budgets + safety nets

> Status: planned · Surfaced 2026-05-21 during platform-reliability
> sweep · Combines T9 (execution guardrails) + T11 (fallback
> strategies) + T21 (emergency stop) from the
> [Agent Reliability framework](https://platformengineering.org/blog/the-agent-reliability-score-what-your-ai-platform-must-guarantee-before-agents-go-live).
> Promotes the 2026-05-21 "Cost dashboard" backlog item from
> visibility-only into actual budget enforcement.

Today's only soft guard is `KOURAI_MAX_ITERATIONS=5`. A buggy
Techne ↔ Kallos loop can still burn through hundreds of thousands of
tokens before that ceiling fires, because the iteration limit is
per-feedback-loop, not per-forge-cycle. The 2026 best-practice
framing is sharper: **workflow-level token budgets are THE primary
guardrail**, iteration limits are necessary but secondary.

`research(2026-05)`: MindStudio's "Deploy AI Agents to Production"
(workflow-level token budgets named as primary guardrail);
LeanOps "AI Agents Burn 50x More Tokens Than Chats" (multi-agent
forge cycles measured at 200k–1M+ tokens per task — exactly kourai's
range); platformengineering.org Agent Reliability T9 + T11 + T21.

### Scope

**1. Workflow-level token budget.** `KOURAI_FORGE_BUDGET_TOKENS`
(default e.g. 300_000) counted across every LLM call within one
forge cycle — Hephaestus routing + Metis spec + Techne diff +
Dokimasia tests + Kallos review + Mneme commit + all retries. When
80% consumed, Hephaestus emits a status warning to the player;
when hit, the active specialist gets a "wrap up — budget reached"
signal in its next prompt and Mneme finalizes whatever's done.
**Behavior is graceful summarize-and-escalate, not hard-stop** —
per Anthropic / MindStudio guidance, the agent should land
gracefully rather than crash mid-write.

**2. USD-derived budget.** `KOURAI_FORGE_BUDGET_USD` (default e.g.
$5) computed against `pricing.py` rates. Whichever fires first
between #1 and #2 wins. Caveat: Opus 4.7 tokenizer pin under
cross-cutting invariants means the USD-projection-from-tokens calc
under-quotes Opus traffic by up to ~35% — adjust the USD budget
generously to match.

**3. Per-turn caps.** `KOURAI_MAX_TOOL_CALLS_PER_TURN` (default 30)
and `KOURAI_MAX_INTERACTION_SECONDS` (default 600) layer on top of
the workflow budget. Same graceful-stop behavior.

**4. Per-tool circuit breakers.** Wrap `context7-mcp` and
`memory-mcp` calls in `kourai_common.circuit_breaker` (new module):
N consecutive failures → open circuit → return "no library docs
available" / "no memory available" structured fallback instead of
retry storm. Half-open after backoff window. Replaces the implicit
retry-until-timeout pattern.

**5. Per-agent emergency stop.** `/stop <agent>` slash command +
`/stop all` flips a `KOURAI_AGENT_KILLED` flag in
`kourai_common.agent_state` that Hephaestus's routing layer checks
before dispatching. Killed agents return a structured
`{"status": "halted", "reason": "operator_stop"}` artifact; pipeline
gracefully unwinds. Reachable from any host (CLI / GUI / VN) within
~5 seconds. Doesn't require `make down`.

**6. Cost visibility (promoted from backlog).** `/cost` slash
already exists; extend to show session-running + monthly-running
totals against the active budgets ("$1.23 / $5.00 this forge,
$87.40 / $200 this month"). GUI gets a subtle bottom-right panel
mirroring the same numbers. Visibility first; AI-driven
"Hephaestus suggests dropping to cheap tier" follow-on stays in
backlog.

### Out of scope

- Per-player budget tiers (shared instance / multi-tenant). Single-
  player local app doesn't need it yet; revisit if a hosted
  deployment lands.
- Automatic model-tier downgrade on budget pressure. Stays manual
  via existing `KOURAI_MODEL_TIER` / `/model` slash.

### Done when

- A Techne ↔ Kallos thrash loop hits the workflow budget at
  ~300k cumulative tokens and gets gracefully wound down by Mneme
  instead of running to `KOURAI_MAX_ITERATIONS=5`.
- `docker stop context7-mcp` mid-session triggers the circuit
  breaker; Metis gets a structured "no library docs available"
  fallback instead of a 30s retry loop.
- `/stop kallos` mid-pipeline halts Kallos within 5s; Hephaestus
  acknowledges the operator stop in-character and Mneme drafts a
  commit against whatever Techne completed.
- `/cost` shows live forge-vs-budget + month-vs-budget numbers.
- 2026-05-21 backlog "Cost dashboard in CLI + GUI" collapses into
  this milestone.

---

## M24 — OpenTelemetry GenAI semconv adoption + reasoning-trace depth

> Status: planned · Surfaced 2026-05-21 during platform-reliability
> sweep · Promotes the 2026-05-21 "Streaming metrics to client per
> turn (`--stats`)" backlog item.

Kourai already emits OTel spans into Jaeger, but the span names and
attribute keys are kourai-bespoke — they don't match the GenAI SIG
semantic conventions that became the de-facto standard in 2026. Two
costs: (a) any third-party trace viewer (OpenInference dashboards,
Phoenix, Langfuse) sees opaque spans instead of recognised
agent-shape, (b) the article's sharp critique applies — "traces
capture what agent did without capturing what it saw" — because the
current spans encode A2A hops + tool calls but not the *reasoning*
shape behind each routing decision.

`research(2026-05)`: OpenTelemetry GenAI SIG semantic conventions
([gen-ai-agent-spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/),
[gen-ai-spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/),
[gen-ai-metrics](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/));
[platformengineering.org Agent Reliability T22](https://platformengineering.org/blog/the-agent-reliability-score-what-your-ai-platform-must-guarantee-before-agents-go-live)
(reasoning-trace observability gap).

### Scope

**1. Standard operation names.** Migrate span names to the
`gen_ai.operation.name` enum: `invoke_agent` for each maiden call,
`invoke_workflow` for the parent forge cycle (Hephaestus owns this
span — every other agent span becomes its child), `execute_tool` for
forge / shell / memory-mcp / context7-mcp calls, `chat` for the
underlying LLM completion. Replaces the current ad-hoc span naming.

**2. Standard attribute keys.** Replace bespoke keys with the
spec set:

- `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.agent.name`,
  `gen_ai.agent.id`
- `gen_ai.request.model`, `gen_ai.request.temperature`,
  `gen_ai.request.max_tokens`
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
  `gen_ai.usage.cache_creation.input_tokens`,
  `gen_ai.usage.cache_read.input_tokens`
- `gen_ai.response.finish_reasons`, `error.type`

The token-usage keys are the exact ones Anthropic + OpenAI + Gemini
SDKs already emit; kourai's LiteLLM bridge can pass them through
unchanged once renamed.

**3. Reasoning-depth events on `invoke_agent` spans.** The semconv
spec leaves "alternatives considered / decision rationale" open;
encode them as structured span events keyed under a kourai-namespaced
extension (`kourai.reasoning.*`) so the standard attrs stay clean:

- `kourai.reasoning.context_assembled` — Forge Transcript turn count
  + token count + fingerprint hash (NOT full transcript — too large)
- `kourai.reasoning.tools_considered` — list of tool names the
  agent had access to this turn
- `kourai.reasoning.tools_invoked` — subset actually called (Jaeger
  already shows execute_tool children, but the explicit list lets a
  "considered 12 tools, called 2" comparison surface)
- `kourai.reasoning.decision` — short structured rationale string
  (specialist's one-line answer to "why this approach") — opt-in
  per agent prompt; not all agents need it

Hephaestus's routing decision is the highest-value place to emit
this — recording which agents were considered vs which got
dispatched is exactly the "what the agent saw" depth the article
critiques today's traces for missing.

**4. Player-facing `/stats` slash (promoted from backlog).** Renders
the same span data as a per-turn summary at the CLI boundary:
tokens / wall-time / tool-calls-fired / cache-hit-ratio. Reuses the
OTel instrumentation — pure render layer, no new measurement code.

### Out of scope

- Migrating from Jaeger to an OpenInference-native viewer (Phoenix,
  Langfuse). Standard attrs + standard span names mean those become
  drop-in if we ever want to; not picking the day-1 fight.
- Auto-generating evals from span data. Adjacent capability,
  separate milestone if a real caller surfaces.

### Done when

- `gen_ai.operation.name in ('invoke_agent', 'invoke_workflow',
  'execute_tool')` covers every span emitted by the 10 agents in a
  smoke run. Bespoke names retired.
- `gen_ai.usage.input_tokens` + `gen_ai.usage.cache_read.input_tokens`
  show up on every LLM-call span, matching the values LiteLLM
  already reports per-call.
- A Jaeger trace for a single forge cycle shows one
  `invoke_workflow` root → six `invoke_agent` children → N
  `execute_tool` grandchildren. Replaces the current flat-ish
  multi-root pattern.
- Hephaestus's routing-decision span carries a
  `kourai.reasoning.tools_considered` event listing every specialist
  it could have dispatched, plus `kourai.reasoning.decision`
  naming why it picked the actual pipeline.
- `/stats` renders the last-turn token / wall-time / tool-call
  summary at the CLI prompt.
- 2026-05-21 backlog "Streaming metrics to client per turn" collapses
  into this milestone.

---

## M25 — Outcome + trajectory metrics

> Status: planned · Surfaced 2026-05-21 during platform-reliability
> sweep · Smallest scope of the four reliability milestones, biggest
> research-poster + UX signal-per-line-of-code · Depends on M24
> (standard semconv) for the trajectory side

The `/project accept | discard <session_id>` slashes have shipped —
the player explicitly tells the system whether the forge output was
good. Today that signal goes into the project's git history and
nowhere else. The article's sharpest concrete failure mode applies
directly: "an agent that resolves 500 tickets/day, 200 reopened, is
a liability pretending to be productivity." Kourai has the
acceptance signal *and* the per-pipeline trajectory data; what's
missing is wiring them into a feedback loop.

`research(2026-05)`: Galileo "Agent Evaluation Framework" + Confident
AI "Definitive Agent Evaluation Guide" both name the
**outcome-vs-trajectory** metric split as 2026 production baseline.
AlphaEval paper (cited in Future AGI 2026 framework review) finds
production agents track 2.8 leaf-node evaluation types per task on
average — kourai's six-specialist pipeline maps cleanly onto that.

### Scope

**1. Outcome counter.** New Prometheus counter
`kourai_outcome_resolution_total{pipeline, kind, terminal_agent}`
where `kind ∈ {accept, discard, re_forge, abandon}` and
`terminal_agent` is the last specialist before the player decided.
Wired at the `/project accept | discard` slash handler; `re_forge`
fires when the same session_id gets a second pipeline; `abandon`
fires when a session goes idle past the M23 timeout without resolution.

**2. Trajectory metrics.** Per forge cycle, recorded against the
M24 `invoke_workflow` span:
- `kourai_forge_iterations` — Techne ↔ Kallos round count
- `kourai_forge_tool_calls` — total `execute_tool` count
- `kourai_forge_tokens_by_agent{agent_name}` — token sum per maiden
- `kourai_forge_circuit_breaks_total{tool_name}` — M23 breaker fires

**3. Correlation panel.** New Grafana dashboard
`agent-reliability.json` joining outcome × trajectory: discard rate
when Kallos iterations >5, accept rate when Aletheia citations
returned 0 hits, re_forge rate by terminal_agent. Opens via
`uv run kourai-dev observe` next to the existing Jaeger / Prometheus /
Dozzle panels.

**4. Aletheia retrospection (opt-in).** Aletheia already validates
citations. On `/project discard` with `--reason "..."`, the reason
string + the trajectory snapshot get appended to a
`forge_post_mortems` table. Aletheia can be invoked offline against
the table (`uv run kourai-dev review-discards`) to surface
correlated patterns — e.g. "60% of discards in the last 7 days had
Kallos iterations >3 and zero context7 hits." Read-only analysis,
no auto-action.

### Out of scope

- Auto-tuning prompts based on discard patterns. That's a follow-on
  research milestone, not this one. This milestone just closes the
  loop on visibility.
- Multi-player aggregation. Single-player local, single set of
  outcomes; aggregation question shifts only if a hosted instance
  lands.

### Done when

- `curl localhost:9090/api/v1/query?query=kourai_outcome_resolution_total`
  returns non-zero values after a few `/project accept` /
  `/project discard` cycles.
- The correlation panel surfaces the discard / accept ratio per
  terminal_agent — answering "which maiden's output gets discarded
  most often" in one glance.
- `uv run kourai-dev review-discards` prints Aletheia's offline
  pattern summary from `forge_post_mortems`.
- Discard reasons (when provided) are queryable.

---

## Next up — priority order

Pre-release perfection stance: no workarounds, web-search current best
practice **at the planning step**, architectural fix over expedient
patch. Pick by impact + caller reality, not file-of-origin.

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

**Anticipatory — re-audited 2026-05-16, gated on real second consumer**:

These looked self-contained but the current-caller picks are exhausted —
see IMPL.md "Next pickups" for the per-item verdict. Each requires
either an intentional anticipatory-gate override (flag in the PR body)
or a real second consumer landing.

- **Puck Slice 2 helper** — `_invoke_agent_live(agent, prompt, fallback,
  timeout)` A2A timeout-and-fallback wrapper. Skip the
  `/replay-tutorial` command pending Slice 3 (replays a still-stub
  flight scene = anticipatory).
- **Cross-host status-feed** — `kourai_common.status_feed` (RingBuffer[T]
  + StatusEvent typed record). One writer, three subscribers (CLI
  `/debug` slash, future GUI bottom overlay, file-write). Replaces
  debug_log.py + the deleted status_bubbles parallel state stores.
  Anticipatory until the CLI `/debug` slash command actually lands.
- **Cross-host gossip-render** — `kourai_common.gossip_render`
  (RenderedRound). gossip_core / gossip_models already canonical
  from #170; what's missing is the host-agnostic structured-render
  translation. Renderers collapse to ~30-line ANSI / pygame / Ren'Py
  adapters. Anticipatory until a host renderer exists.
- **Cross-host codex** (in-game encyclopedia) — biggest scope; fixes
  the broken VN codex screens; Mass Effect-shape data + unlock triggers.
  Best done as one large PR; live smoke needed for VN parchment-book
  renderer.
- **Per-agent motion language** — polish, lands last.

Music playlist — content-driven; AJ adds tracks to
`assets/audio/music/` over time. No code work.

---

## Cross-cutting invariants

Design rules and known-deferrals that constrain every milestone — not
tied to any single one. Update when an invariant changes.

- **MCP elicitation deferred-by-design.** Real-caller-driven only.
  Architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design when the first forge MCP tool wants `ctx.elicit()`.
- **MCP spec version pinned to 2025-11-25** — confirmed still current as
  of 2026-05-16 (no new revision since November 2025; v2.1 SEPs in
  flight, not yet adopted). Spec drift watcher cron
  (`scripts/watch_protocols.py`, runs Sundays 13:00 UTC) flags any
  subsequent revision.
- **Opus 4.7 tokenizer caveat.** Same per-token rates as Opus 4.6, but
  the new tokenizer can consume up to ~1.35× more tokens for the same
  source text. Cost *accounting* stays correct (LiteLLM reports actual
  tokens), but cost *projection* from Opus 4.6 historical usage
  under-quotes by up to ~35%. Affects metis (the only SMART-tier
  Opus 4.7 caller today). Captured in `pricing.py` header comment so
  the planning surface, not the accounting one, carries the caveat.
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
- **Subagent contract discipline (Anthropic 4-part).** Every maiden's
  system prompt must declare: (1) objective, (2) output format,
  (3) guidance on which tools / sources to use, (4) clear task
  boundaries. Anthropic's "How we built our multi-agent research
  system" calls out that "missing any of these causes the subagent to
  drift." `scripts/check_agent_contracts.py` greps each
  `agents/*/prompts.py` for the four sections and fails CI on a gap;
  audit pending — file when adding a new maiden or extending an
  existing prompt. Anti-pattern is the inverse: dumping the Forge
  Transcript at a maiden and hoping the role inference holds.
  `research(2026-05)`: [Anthropic engineering, multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system);
  [effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- **Stale-assumption audit (whenever a frontier model ships).** Every
  Hephaestus routing rule, every specialist boundary, every piece of
  forge scaffolding encodes an assumption about what Claude — or any
  model in the active provider rotation — couldn't do at the time the
  scaffolding was written. Anthropic's Managed Agents engineering
  essay frames this as a recurring failure mode: *"harnesses encode
  assumptions about what Claude can't do on its own. However, those
  assumptions need to be frequently questioned because they can go
  stale."* When a new frontier model lands (Sonnet 4.7, Opus 5,
  Mythos-class), audit which kourai scaffolding existed to compensate
  for a capability gap that's now closed; collapse or retire what no
  longer earns its keep. This is the inverse of speculative-generality
  YAGNI — it pulls *down* over-engineered orchestration that the
  model now handles natively, rather than blocking new building.
  Captured as a recurring invariant rather than a milestone because
  the work is diffuse and triggered by external events (model
  releases), not a finite scope.
  `research(2026-05)`: [Anthropic engineering, Managed Agents](https://www.anthropic.com/engineering/managed-agents);
  [Building Effective Agents — "start with simplest architecture, add complexity only when simpler solutions demonstrably fall short"](https://www.anthropic.com/research/building-effective-agents).

---

## Future / unprioritized backlog

Real items not yet on a milestone. Many are tractable; pick by caller pain rather than file-of-origin.

### Surfaced 2026-04-26 from external research (OSS Claude Code clones, Typer, MCP/A2A specs)

Sweep of post-leak OSS Claude Code rewrites (ClawCode, OpenCode, Cline, Aider, Plandex, Roo Code, Kilo) + Typer CLI patterns + current A2A/MCP specs. MCP/A2A bullets are captured in M2 and M7 above; player-experience bullets live here. Convergent finding: three-layer memory architecture (session persistence → in-session compaction → context discovery on resume); keep in mind when M15 logging lands.

- **MCP `roots` + `elicitation` declared at M2 init.** Design-time work, near-zero cost if done while M2 is scaffolded; retrofitting later is painful. Only remaining item from the prioritized OSS-CC lift list — `/compact`, `/permissions` granular tool gating, `A2A-Version` header, and `/cost` alias all shipped 2026-04-26.

- **`/model` slash command — runtime tier switching without restart.**
  We have `KOURAI_MODEL_TIER` as an env var, but switching mid-session
  requires `/q` and re-launch. `/model cheap|standard|smart` (and
  per-agent `/model metis smart`) flips the dispatch in-place. Aligns
  with the per-call `tier` kwarg shipped in M9-follow-on PRs (#30/#32)
  — the plumbing is already there; this is just the player-facing
  UI for it. Useful when a player notices Hephaestus is being
  expensive on a chatty session and wants to drop to Haiku for
  routing-only turns.

- **`/session` slash command — inspect / fork / resume context.**
  Today `/project status` covers projects + forge sessions but not
  conversation context. `/session show` prints turn count,
  cumulative usage, and last-N-turns digest; `/session fork` clones
  the current `context_id` for branching exploration ("what if I
  asked Metis for a different plan?"); `/session resume <id>` jumps
  back to a prior conversation. Mirrors ClawCode's `/session`
  command and our existing forge-session vocabulary so players don't
  have to relearn the term.

- **Plan Mode toggle (Cline-style).** Persistent plan-mode where
  Hephaestus loops on planning — runs M14 Metis-first parallel
  routing every turn but **never dispatches** the pipeline until
  the player explicitly types `/plan execute`. Distinct from
  M13's per-pipeline confirmation gate: M13 confirms one specific
  read-back; Plan Mode lets a player iterate the *shape* of the
  ask across multiple turns before any specialist runs. Pairs
  with `/permissions`: in Plan Mode, all tool gates are forced on
  regardless of YOLO — by definition the player isn't ready to
  execute yet.

- **Background memory consolidation (Mneme "autoDream").** ClawCode's
  autoDream pattern: between sessions, a low-priority background
  agent rolls forward yesterday's transcripts into long-term player
  knowledge (skill markers, recurring patterns, unfinished threads).
  We have Aidos's slop-detection + Mneme's documenter persona
  separately; consolidating them into a `make consolidate-memory`
  cron-style sweep that runs Mneme over the prior 7 days of
  `agent_memory.db` would cohere the player's mental model of "what
  the maidens know about me." Output goes into the `kourai_common.facts`
  knowledge graph as the natural home (already shipped, supports
  relationships and confidence decay) rather than a parallel
  `player_facts` table. **See [M17](#m17--hotl-answer-persistence-project-scoped-facts)**
  for the structured-pause case (real-time write of project-scoped
  facts on `INPUT_REQUIRED` resolution); autoDream is the *batch
  prose-consolidation* peer that scans Memoir entries for
  un-tagged-but-extractable patterns and promotes them into the
  same fact graph M17 populates.

- **Custom-agent-via-markdown registration (OpenCode-style).**
  OpenCode lets users drop a `.md` file with frontmatter into
  `~/.config/opencode/agents/` to register a new sub-agent. We have
  10 hard-coded agents in `kourai_common.agents.AGENT_METADATA`. A
  pluggable layer would let a player draft, say, "Eros — copywriter
  for marketing-flavoured strings" without forking the repo.
  Architecturally large (touches A2A registration, MCP toolkit,
  routing prompt) — flag as a long-term direction, not a near-term
  PR.


- **Typer-style sub-app pattern for `hosts/cli/commands.py`
  cleanup.** Honest verdict on Typer (Sebastián Ramírez, FastAPI):
  it does NOT replace our async REPL — `asyncclick` + `prompt_toolkit`
  is already deeper than Typer's sweet spot for long-running
  interactive sessions. But the type-hint-driven sub-app pattern
  (`projects = typer.Typer(); @projects.command() def new(name: str)`)
  would clean up the ad-hoc string parsing in `_handle_project_command`
  if we ever refactor that file. Not a milestone — flag as a
  refactoring direction when `commands.py` next gets touched.

- **Tree-sitter project mapping (Plandex-style).** Plandex ships
  with a 2M-token context window AND a tree-sitter-based project map
  it injects into prompts so the LLM gets a structural index instead
  of the raw file tree. Our specialists today receive directory
  listings via `bash` calls; a pre-computed
  `<PROJECT_MAP>` block (functions, classes, imports per file) would
  burn fewer tool turns. Synergy with M4 caching — the project map
  is stable across most turns, so it caches reliably.

- **LSP integration for forge tools (OpenCode pattern).** OpenCode
  invokes the project's Language Server (pyright, ruff-lsp,
  rust-analyzer) as a tool the agent can call for type info,
  diagnostics, and rename-aware refactors. Today our forge tools are
  text-substitution only — no semantic awareness. A new
  `lsp_diagnostics(path)` tool would let Dokimasia validate Techne's
  changes without spinning up `pytest`; a new `lsp_rename(old, new)`
  would let Kallos rename across the codebase atomically. Big lift,
  big return on safety.

### Older items

- **MCP Tasks primitive (experimental):** when stable, replace our hand-rolled
  `forge_sessions` SQLite table with MCP Tasks for durable execution.
- **A2A `INPUT_REQUIRED` handling:** wire it through Hephaestus → CLI so a
  specialist mid-pipeline can ask the player a question instead of failing.
  *(Lifts via M13 — the Forge Order Confirmation feature builds the same
  primitive end-to-end. Once M13 lands, this bullet collapses to "extend
  M13's INPUT_REQUIRED plumbing to mid-pipeline specialists.")*
- **Strict tool use** (`strict: true` on tool defs): once M1 lands, turn it
  on for forge tools to guarantee schema conformance.
- **Anthropic Agent SDK:** evaluate when it stabilises; could replace some
  REPL plumbing in `hosts/cli/__main__.py`.
- **Sandbox container UID alignment** (M5 implementation choice).
- **ElevenLabs SFX library regeneration:** when M6 lands the TTS swap, regenerate the `.ogg` library under `assets/audio/sfx/` that `hosts/gui/emote_sfx.py` plays. Use Sound Effects API (`client.text_to_sound_effects.convert` → `POST /v1/sound-generation`, model `eleven_text_to_sound_v2`). One-shot into the asset tree, **not** per-line at runtime — keeps latency and credit spend off the hot path. Tier strategy: Starter at $5/month (commercial license + perpetual rights on audio generated during the paid month) is the legitimate one-month-burn-then-cancel pattern. Never commit Free-tier-generated audio (non-commercial + requires `elevenlabs.io` attribution in titles).
- **Companion / spirit READMEs (Puck, Cupid, Aidos, Aletheia):** the
  6 main pipeline agents got READMEs on 2026-04-26; the
  4 secondary agents are deferred until M6 voice-lab / gossip /
  romance work crystallises so we don't document an in-flight design
  twice.
- **Property-tested agent-coordination invariants:** `hypothesis` is
  already heavily used (~11 test files use `@given` strategies for
  GUI scaling, settings, dialogue history, etc. as of 2026-04-26).
  Missing: agent-level invariants over randomised pipeline state
  machines. Target invariants: every `AgentInputRequired`
  (`agents/hephaestus/remote_connections.py:38`) resumes on exactly
  the agent that raised it; every pipeline exits in exactly one of
  {complete, discarded, error}; every A2A `Message` round-trips
  through serialisation. Start with the `AgentInputRequired`
  round-trip invariant and expand from there.
- **Bonds + Codex as player-accessible panels (VN):** dating-sim
  convention — the player can check relationship status anytime, but
  it's never in their face during scenes. Today `screen affinity_hud`
  (`hosts/vn/kourai_vn/game/screens_hud.rpy:69`) is an always-on
  overlay and `screen codex`
  (`hosts/vn/kourai_vn/game/screens_codex.rpy:2`) exists but has no
  entry point. Refactor the affinity HUD into a full-screen `screen
  bonds` panel and wire both panels into (a) the game menu alongside
  Save/Load/Prefs, (b) `B` and `C` hotkeys via `config.keymap`,
  (c) optional text links in the quick-menu bottom row. Drop the
  always-on affinity HUD from shipped scenes — the `poster_demo` flag
  keeps it visible there only. Matches Doki Doki / Katawa Shoujo /
  Hades-Codex UX, keeps the stage clean during dialogue, makes opening
  a panel feel like consulting a dossier.

### Surfaced 2026-04-27 during M16 live-smoke session

- **VN Codex broken (`hosts/vn/kourai_vn/game/codex_data.rpy`,
  `screens_codex.rpy`).** Symptom and reproduction TBD; needs a
  debugging session next time the VN host (`make vn`) is exercised.
  See "Cross-host shared rebuilds" below — the codex extraction
  supersedes a fix-in-place; rebuilding the encyclopedia under
  `kourai_common.codex` lets the broken VN screens get rewritten
  fresh against the canonical data, with CLI + GUI surfaces gained
  for free.

### Surfaced 2026-05-06 from cross-host dead-infra audit

After #170/#171/#172 shipped the ten-item cross-host DRY sweep, a
follow-up audit surfaced a stratum of staged-but-unwired GUI features
(Scratchpad, PipelineStatusIndicator, StatusBubbles, AgentPersonality
indicators, plus the CLI's `gossip_cli`). Their integration shims had
been instantiated in `gui_components_integration.py` but never called
from any rendering or logic path; tests exercised the APIs against
`Mock()`, giving false coverage signal (the *Mockery* anti-pattern in
modern test-design literature). The legacy modules were deleted in
preference to wiring them, on the explicit understanding that any
rebuild lands as a shared-across-hosts feature rather than a
GUI-defines-then-waits pattern.

The rebuild items below are **deliberately host-agnostic** at the data
layer (frozen dataclasses + pure logic in `kourai_common.*`); each
host owns thin renderer adapters. Pick by player-journey impact, not
file-of-origin.

- ~~**Cross-host scratchpad — per-agent CoT / TODO display.**~~
  **Phase 1 shipped 2026-05-06 [#176]:** `kourai_common.scratchpad`
  data layer (`ScratchpadEntry` + per-agent ring-buffered
  `Scratchpad` + lazy module singleton) + CLI `/scratchpad` slash
  command. CLI streaming buffers classifier-shaped non-dialogue
  messages as a side-effect (display routing unchanged). GUI's
  post-#175 logger.debug-and-drop path now buffers to the same
  module. ScratchpadEntry stores raw text rather than the originally-
  spec'd kind union — kind classification is a renderer concern,
  not a buffer property. **Phase 2 follow-on:** GUI overlay
  renderer + VN side parchment renderer (each gated on live smoke);
  vn_bridge classifier-side wiring (today vn_bridge routes through
  KIND_DIALOGUE metadata, so non-dialogue scratchpad content from
  VN-side specialists isn't a current pattern); cross-session
  persistence (file when a player asks).
- **Cross-host pipeline-status — active agent + queue + loading
  flag.** Real metis-parallel work exists (M0); each host re-derives
  "who's active" from event streams independently today. New shared
  module: `kourai_common.pipeline_status` exporting `PipelineState`
  (frozen) + `PipelineTracker` with hooks into the central A2A event
  stream (`working` → set_active, handoff → dequeue+set_active,
  `complete` → clear). Renderers: CLI status-line above prompt
  (`🔥 hephaestus → 📐 metis (analyzing)`), GUI active-agent badge
  + queue indicator, VN HUD overlay highlighting the active maiden.
- **Cross-host status feed — debug events ring buffer.** Today
  `debug_log.py` writes events to disk and the deleted
  `status_bubbles.py` buffered the same shape in memory — two
  parallel state stores. New shared module: `kourai_common.status_feed`
  exporting a generic `RingBuffer[T]` and a `StatusEvent(level,
  agent, text, timestamp)` typed record. One writer, three
  subscribers (CLI `/debug` slash, GUI bottom overlay, VN optional
  codex page); file-write becomes just another subscriber.
- **Cross-host gossip render layer.** `gossip_core` and
  `gossip_models` already canonical from #170; what's missing is a
  structured-render translation. New shared module:
  `kourai_common.gossip_render` exporting `RenderedRound(speakers,
  lines, options)` and host-agnostic format helpers. Renderers
  collapse to ~30-line ANSI / pygame / Ren'Py adapters that consume
  `RenderedRound`.
- **Cross-host codex — encyclopedia entries with auto-unlock
  triggers.** Today the VN owns ~550 lines of `codex_data.rpy` plus
  401 lines of `screens_codex.rpy`, and the VN screen path is broken
  (above). Mass-Effect-shaped data: 6 categories (Characters,
  Technology, Lore, Virtues, Tutorials, Systems), entries with `id /
  title / subtitle / content / unlock_trigger`, triggers like
  `start | agent_met:<name> | affinity:<name>:<threshold> |
  tutorial:<id>`. New shared modules: `kourai_common.codex` exporting
  `CodexEntry`, `CODEX_CATEGORIES`, `CODEX_ENTRIES`, plus an
  `is_unlocked(entry, player_state)` pure-function trigger evaluator.
  Renderers: CLI `/codex` slash + ANSI table, GUI overlay panel, VN
  parchment-book screen (replaces the broken Ren'Py screens with a
  fresh implementation reading the canonical data).
- **Per-agent motion language.** Each maiden gets a distinctive
  visual idle behaviour (the deleted `agent_personality_indicators`
  reached for this with pygame-only `pulse / glow / shimmer / none`
  primitives but never wired). Polish layer, lands last. New canonical
  field on `AGENT_METADATA` — `motion: Literal["pulse", "glow",
  "shimmer", "drift", "static"]` — with each host translating: GUI
  pygame primitives, VN Ren'Py ATL transforms, CLI no-op (or subtle
  ANSI shimmer for very-active agents). Filed for after the static
  visual tightening below.
- **VN dialogue-presentation polish (illuminated-manuscript
  framing).** Static improvements landing the VN's existing parchment
  + plaque concept closer to its visual reference: ornate corner
  flourishes on the dialogue frame, decorative motif at the
  plaque-to-dialogue join, epithet subtitle rendered under the
  speaker name in the plaque (data already exists at
  `AGENT_METADATA[*]["epithet"]`; render-side wiring is the gap).
  Live-smoke required (AJ at the keyboard) for each visual change to
  confirm against the parchment background.

### Surfaced 2026-05-17 from app-SDK freshness sweep

- **RealtimeTTS 0.6.1 → 0.7.1 migration.** `KokoroEngine` now consumes
  `KokoroVoice` instances rather than the previous voice-name string
  interface (breaking). `tools/voice-lab/` casting metadata and
  `shared/src/kourai_common/tts_realtime.py` voice-load paths both need
  updating. Companion wins available in 0.7.x: built-in trim-silence +
  fade hooks (could retire bits of `kourai_common.audio_dsp`), expanded
  `on_word` callback coverage. **Gated on AJ-in-loop live smoke** for
  CLI + GUI + VN since Kokoro is the karaoke path's primary engine and
  voice-name regressions are easy to miss without ear-on. Captured
  here rather than M6 (M6 is the ElevenLabs hybrid). source:
  github.com/KoljaB/RealtimeTTS/releases

### Surfaced 2026-05-18 from make-delegation audit

- **`smoke-m18` + `sandbox-image` `kourai-dev` registration.** The
  demo-target fix [#200] resolves the bulk of the Makefile-delegation
  drift, but two non-demo targets still bypass `$(UV_DEV)`:
  `smoke-m18` (uses `uvx --with pexpect python scripts/...`) and
  `sandbox-image` (uses `docker build`). The tail helpers (`logs`,
  `logs-tail`) are trivial enough to stay shell-only. The two
  non-trivial holdouts are honest registration candidates once a
  second caller surfaces — Windows-without-make dev, or a CI matrix
  that wants to invoke them via the cross-platform CLI. Defer until
  the second caller exists.

### Surfaced 2026-05-21 from audit-of-audits

Items from the 2026-05-17 Copilot ecosystem audit that survived a current-state + 2026-05 web-search review. The source folder (`~/ajsoftworks/copilot-audit-ideas/`) was deleted after extraction; everything load-bearing lives here.

- **Live affinity display in CLI.** The affinity mechanic is real and
  exercised heavily across `tests/unit/test_relationship_math.py` +
  10 other affinity tests; the VN renders an affinity HUD; the CLI
  doesn't render any of it. The interesting design question (which
  Copilot's spec under-addresses) is the high-vs-low-affinity
  *personality shift* — high affinity → "I'd suggest we…" /
  permission-seeking, low → "Let's just…" / directive. That's a
  prompt-injection axis at the A2A layer, not a render-bar UI.
  Persistence should go through the existing
  `shared/src/kourai_common/player_context.py` rather than a
  parallel `~/.kourai_khryseai/player/<id>/affinity.json` path.
  Backward-compat default: existing sessions start at 5.0 across
  all agents. Sized as a single milestone-grade slice; defer until
  M6 + M20 cleanup ships.

- **Persistent agent memory namespace on memory-mcp.** `memory-mcp`
  exists as a Dockerized sidecar (`docker/memory-mcp-server.js`,
  `MEMORY_MCP_URL` wired into every agent). Today it's an opaque
  graph store. Adding a structured `patterns` namespace (user coding
  patterns, codebase idioms, test prefs) gives Metis spec-time
  grounding and Techne style-time grounding. The slash command
  surface should include `/project forget_patterns` and visibility
  for what was learned. Auto-decay old patterns past a threshold so
  the graph doesn't grow unbounded.

- **Cost dashboard + budget enforcement** — promoted to [M23](#m23--execution-budgets--safety-nets)
  2026-05-21. Visibility piece (`/cost` totals, GUI panel) bundled
  with hard budget caps + circuit breakers + emergency stop.

- **Streaming metrics to client per turn (`--stats`)** — promoted to
  [M24](#m24--opentelemetry-genai-semconv-adoption--reasoning-trace-depth)
  2026-05-21. The CLI renderer rides on top of the OpenTelemetry
  GenAI semconv adoption rather than landing as a one-off display.

- **Forge session replay & branching** — promoted to
  [M22](#m22--forge-session-replay--reproducibility-capture)
  2026-05-21. Replay + branch + the reproducibility-capture columns
  in `forge_sessions` ship as one coherent slice.

- **Skill-based agent leveling (narrative).** Stackable with affinity
  (orthogonal axes); tracks Kallos accept-rate-per-Techne-diff,
  Dokimasia coverage achieved, etc. — all already in
  OpenTelemetry span data. Reinforces the "this is a game"
  framing. Long-horizon narrative item; pairs with affinity work.

- **Techne system-prompt tweak: auto-emit docstrings + module
  overviews on new code.** Copilot's audit proposed a new "Sophia"
  documentation agent (an 11th agent host); refined-down version
  is much smaller — extend Techne's existing system prompt so its
  diff output includes Google-style docstrings on new functions
  and module-level overviews when scope is broad. Kallos already
  reviews the diff, so docstring quality enters the existing
  review loop without a new host. No new infrastructure, just a
  prompt change. Tier 1 low-lift.

### Surfaced 2026-05-21 from audit-of-audits — Cross-sister polish

> Source: 2026-05-21 audit-of-audits review "Insights worth keeping". Mirror items live in the matching ROADMAP for the other active sisters. Both items shipped 2026-05-21 (this commit's wave); kept here so the audit-of-audit trail stays legible.

- ✅ **`## Sister ecosystem` block in README.** Names Phalanx-FL / VelocityFL / LDQIS / techne / ajbarea.github.io with their ecosystem roles and one-line links. Shipped in 4b0a36c.

- ✅ **Project Glasswing posture cited in README + `docs/security.md`.** One-paragraph "Trust + security" section in the README cites [Anthropic's Project Glasswing](https://www.anthropic.com/glasswing) (April 2026) as the 2026 frame for trustworthy multi-agent code generation, names the canonical MCP transport posture (TLS 1.3 + OAuth 2.1 + OIDC + RBAC + RFC 8707), and links to the new `docs/security.md` for the full posture statement. The security doc covers what holds today (implicit Docker-network trust boundary for the MCP sidecars and A2A hops), what to harden before a multi-tenant or cross-host deploy, per-resource access-list policy on MCP tools, PQC hybrid (ML-KEM / Kyber) as a watcher item, and deliberate non-goals (Forge Transcript stays unencrypted to preserve auditability). Web-search verified May 2026 against the MCP authorization spec + Security Boulevard 2026-05 PQC guide.

### Surfaced 2026-05-21 from audit-of-audits — Security posture documentation

Copilot's audit included a "BONUS: Privacy-first multi-agent
communication" item proposing custom E2E encryption at the MCP layer.
That framing is wrong-shape per the 2026-05 MCP roadmap and the
Security Boulevard 2026-05-13 guide to PQC + MCP: the canonical
posture is TLS 1.3 + OAuth 2.0/OIDC + RBAC + AES-256 at rest, with
PQC hybrid (ML-KEM / Kyber) as the forward-looking layer. A custom
E2E protocol on top of MCP is not the call.

What *is* worth filing:

- **`docs/security.md` documenting Kourai's MCP transport posture.**
  TLS 1.3 between agents and MCP servers, OAuth 2.0 / OIDC where
  service-to-service auth applies (currently the MCP sidecars run
  in the same docker network — document the implicit trust
  boundary so it doesn't get extended to cross-network deploys
  silently), per-resource access lists on MCP tools (which agent
  can call which capability). The page exists as a doc surface
  before the access-list code exists; treat it as a posture
  statement that the implementation evolves toward, not a code-
  generated artifact. Ref: [Security Boulevard 2026-05](https://securityboulevard.com/2026/05/the-2026-guide-to-post-quantum-ai-infrastructure-security-protecting-model-context-protocol-mcp/),
  [MCP 2026 roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/).

- **Per-resource access-list config on MCP tools.** Each MCP
  capability declares which agents can call it (today: implicit
  trust). Mechanical small slice once the security doc establishes
  the model. The "credential tool that only Techne / Dokimasia
  can decrypt" framing from Copilot becomes "the credential tool
  is in the access list for exactly those two agents" — same
  outcome, no custom encryption protocol.

- **PQC hybrid (forward-looking, not 2026-Q2 work).** The MCP 2026
  roadmap names PQC as a 2026 priority but the actual library
  ecosystem (Rustls / OpenSSL hybrid Kyber backends) is still
  maturing. Note as a watcher item; pick up when the
  Rustls / Hyper stack offers a stable hybrid Kyber + X25519
  configuration. Don't pre-empt with a hand-rolled PQC layer.

---

## Shipped

Detail lives in git history (`git log`), the agent code, and `docs/`. This log is pruned once work is durably shipped — these docs are plans + scratchpad, not a historical archive.

- 2026-05-25 — **GitHub Actions SHA-pinned (supply-chain hardening).** All `uses:` refs across the 7 workflows (incl. the `docker/*` build actions) pinned to full commit SHAs (`# vX.Y.Z` comment kept); Dependabot `github-actions` gains a 7-day cooldown, freshness via the existing version updates. Fleet convention + rationale in techne `docs/conventions.md`. research(2026-05): GitHub "Secure use reference"; CNCF GH-Actions CI-deps recipe.
