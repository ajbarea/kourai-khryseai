# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-05-16. **NE AI Agents Day 2026 poster session shipped
2026-05-10** (NYC, Jane Street; QR-code demo live). Polish phase complete.
Now resuming full-speed development with **M6 ElevenLabs hybrid** as the
next priority (sub-task 2 audio cache layer shipped [#174]; sub-tasks
1/3/4/5 still gate on M20 + VN smoke). See [IMPL.md](./IMPL.md) for
the live blocker list, open invariants, and priority-ordered "Up next".
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
## M6 — ElevenLabs hybrid (pre-player-release blocker)

> Status: spec'd 2026-05-05 · Implementation queued · Gated on M20
> audio-led reveal + VN smoke landing first

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

> Status: planned · Operational hygiene · Surfaced 2026-04-26 during M1 Round 6 validation

What Round 6 exposed: the host's `logs/` directory has stale per-agent log
files (`logs/hephaestus.log`, `logs/metis.log`, `logs/kallos.log`,
`logs/dokimasia.log` all from earlier sessions, NOT from the live smoke
run). The live agent traces only live inside containers — `docker logs
kourai-khryseai-techne-1` was the only way to validate that 22 `'type':
'tool_use'` frames flowed during the smoke. That's brittle for post-mortem
work, smoke validation, and CI artifact collection.

**Why.** Smoke recipes that grep host log files (`SMOKE_TODO.md` Round 6
told you to grep `logs/dev-latest.log` for tool_use frames) silently never
matched because the log mount was broken. Future smoke recipes will hit
the same wall. Beyond smoke, tool-event observability matters for poster
demos, customer support, and onboarding new contributors who want to see
what the swarm actually did.

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
  in one command.
- **Rename / retire `dev-latest.log`.** It's the dev-runner wrapper output
  (~933 bytes), not a live agent trace. The name implies otherwise. Either
  rename to `logs/dev-runner-latest.log` or kill it entirely and rely on
  the timestamped `logs/dev-<ts>-<cmd>.log` files.
- **Demote LiteLLM DEBUG default in containers.** Useful for smoke
  testing; verbose noise for steady state. New env var `KOURAI_LLM_DEBUG`
  (default unset / INFO) gates the `litellm.set_verbose = True` line.
  Smoke recipes set it; production-ish runs don't.

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

**Self-contained workable** (ship clean without AJ in-loop):

- **Puck Slice 2 helper** — `_invoke_agent_live(agent, prompt, fallback,
  timeout)` A2A timeout-and-fallback wrapper. Skip the
  `/replay-tutorial` command pending Slice 3 (replays a still-stub
  flight scene = anticipatory).
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

---

## Future / unprioritized backlog

Real items that aren't on a milestone yet. Lifted from the
"M6 — Future / unprioritized" framing that hosted them before M6 got
re-purposed for the ElevenLabs hybrid (2026-05-03). Many are tractable;
pick by caller pain rather than file-of-origin.

### Surfaced 2026-04-26 from external research (OSS Claude Code clones, Typer, MCP/A2A specs)

AJ asked for a sweep of the post-leak open-source Claude Code rewrites
(ClawCode in Python+Rust, OpenCode, Cline, Aider, Plandex, Roo Code,
Kilo, etc.) and Typer for CLI patterns we could lift, plus the latest
Anthropic A2A/MCP spec primitives. Findings below — each is a candidate
slash command, UX pattern, or architectural lift for the CLI host;
sized for individual focused PRs, not bundled. The MCP/A2A bullets are
captured in M2 and M7 above; the player-experience bullets live here.

**Cross-cutting observations.**

- **Three-layer memory architecture is the convergent pattern.** Every
  serious clone organises persistence as three deliberate layers:
  (1) session persistence to disk (we have `forge_sessions` SQLite
  table — covered), (2) transcript compaction within a session
  (we have within-loop caching from M4 but no compaction step —
  the `/compact` bullet below), and (3) context discovery on resume
  (we have project-root injection but no "what threads were open
  last time we talked" surfacing — the `/session show` bullet
  below). Worth keeping the three-layer framing in mind when M15
  logging architecture lands so the layers don't drift apart again.
- **SSE-only forecloses some integrations.** ClawCode supports six
  MCP transports (Stdio, SSE, HTTP, WebSocket, SDK, ClaudeAiProxy).
  We're SSE-only end-to-end. M2 should at minimum offer Stdio
  alongside SSE so a future IDE-side integration (Cursor, VS Code,
  Zed) can reach `kourai-forge-mcp` without standing up an HTTP
  server. Already noted in M2 scope.

**Open from the prioritized OSS-CC lift list.**

Four of the five originally-prioritized items shipped on 2026-04-26
(`/compact`, `/permissions` granular tool gating, `A2A-Version`
header, `/cost` alias) — see Shipped log. One remains:

- **MCP `roots` + `elicitation` declared at M2 init.** Design-time
  work, near-zero cost if done while M2 is being scaffolded;
  retrofitting later is much more painful.

The remaining bullets (Plan Mode, autoDream, custom-agents-via-markdown,
tree-sitter project map, LSP integration) are higher-effort
architectural moves; valuable but not the first lift.

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
- **ElevenLabs SFX library regeneration:** when M6 lands the TTS
  swap, also regenerate the `.ogg` library under `assets/audio/sfx/`
  that `hosts/gui/emote_sfx.py` plays by emote-keyword lookup. Use
  the Sound Effects API
  (`client.text_to_sound_effects.convert` → `POST /v1/sound-generation`,
  model `eleven_text_to_sound_v2`, 0.5–30 s clips). One-shot into the
  asset tree (checked in or pulled from HF like the other voice
  assets), **not** per-line at runtime — keeps request latency and
  credit spend off the hot path. Tier strategy (verified 2026-04-23):
  Free tier (10k credits/month) is non-commercial AND requires
  `elevenlabs.io` in the title of any published content — fine for
  casting inside `tools/voice-lab`, unusable for shipped assets.
  Cheapest viable path is **Starter at $5/month**: commercial license,
  30k credits, and audio generated during the paid month retains
  commercial rights *perpetually* after cancellation, so a one-month
  burn (generate the whole SFX library, then cancel) is the legitimate
  pattern. Hygiene rule: never commit Free-tier-generated
  `.mp3/.wav/.ogg` files anywhere; `.gitignore` doesn't block audio
  today, so it's a discipline rule, not a tooling guard. (The M6 spec
  in IMPL.md owns the per-line voice-line caching strategy; this
  bullet is just the asset-regeneration peer.)
- **Companion / spirit READMEs (Puck, Cupid, Aidos, Aletheia):** the
  6 main pipeline agents got READMEs on 2026-04-26 (see Shipped); the
  4 secondary agents are deferred until M6 voice-lab / gossip /
  romance work crystallises so we don't document an in-flight design
  twice.
- **Property-tested agent-coordination invariants:** `hypothesis` is
  already heavily used (~11 test files use `@given` strategies for
  GUI scaling, settings, dialogue history, etc. as of 2026-04-26). What
  the original entry intended — agent-level invariants — hasn't
  shipped yet. Specifically: every `INPUT_REQUIRED` resumes on exactly
  the agent that raised it, every pipeline exits in exactly one of
  {complete, discarded, error}. (The original entry mentioned
  `HandoffMessage` round-trips, but that type doesn't exist in the
  codebase — the closest analog is `AgentInputRequired`.) Property
  tests over randomised pipeline state machines would catch
  coordination drift early. every `HandoffMessage` round-trips through
  serialisation, every `INPUT_REQUIRED` resumes on exactly the agent
  that raised it, every pipeline exits in exactly one of {complete,
  discarded, error}. Property tests over randomised agent call graphs
  would catch coordination drift early. Start with one invariant
  (`HandoffMessage` round-trip) and expand from there.
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

---

## Shipped

One-line per item, newest first. Detail moves to git history when work
lands — these docs are plans + scratchpad, not a historical archive.

- 2026-05-15 — **Cross-host pipeline-status Phase 1** [#191]. `kourai_common.pipeline_status` (PipelineState frozen + PipelineTracker) replaces vn_bridge's bare `current_agent` string. GUI Phase 2 (GUIState agent-field refactor) deferred until a concrete caller lands; handoff-hooks API likewise deferred.
- 2026-05-15 — **Host-area docstring deslop sweep** [#190]. Cleared `Manages/Handles/Provides` narrative WHAT-docstrings across `hosts/cli` + `hosts/gui`; 12 files, -152 lines, zero behavioral change. Closes the deferral from #184.
- 2026-05-15 — **`speak_with_karaoke` helper extraction** [#189]. Two near-identical karaoke state machines in `__main__.py` (boot greeting) + `streaming.py` (in-session dialogue) consolidated into one shared helper with `on_no_words` / `on_no_audio` / `before_open` hooks. Six new unit tests pin all three outcome branches.
- 2026-05-15 — **Karaoke boot-greeting empty-quote fix** [#185]. Kokoro CPU / muted-audio path opened the karaoke shell but never closed it with text — now slots the greeting inside the shell when no `on_word` callback fires. (Originally opened 2026-05-06; rebased + merged 2026-05-15.)
- 2026-05-15 — **CI fast-lane restoration** [#188]. Reverted the matrix-theater + `|| true` ruff-silencing parts of #187; switched to `--output-format=github` for inline PR annotations + restored `integration-tests` to the PR lane. Cleaned up the 11 ruff violations that snuck through during the gating outage. Codecov slug fix kept.
- 2026-05-15 — **M14 parallel timeout fix** [c46ce56] [f1481b8] [0d86fed]. Tuned aiohttp `TCPConnector` pool (limit_per_host=75 per LiteLLM docs) + disabled `request_timeout` for SSE streaming (Anthropic API guidance) so Metis + Hephaestus concurrent LLM calls no longer contend for pool slots. Diagnostic script + 170-line unit tests included.
- 2026-05-15 — **Karaoke streaming Tier 2 fallback fix** [ce1e438]. Audio-only path (Kokoro CPU emits `on_audio_start` without `on_word`) previously rendered an empty `""` quote pair; now falls back to the static formatted box.
- 2026-05-06 — **Pre-presentation polish bundle** [#184]. Slop sweep + first-impression CLI playthrough fixes for the NE Agents Day 2026 QR-code-clone audience. Five real bugs caught by playing through `make cli` as a first-time developer: Hephaestus contradicted himself on roster (said "four" / listed five / skipped four spirits — fixed with explicit 10-entity FULL ROSTER block); routing JSON `{"mode":"chat","target_agent":null}` leaked into every chat reply (added `include_data` flag to `extract_parts_text`/`extract_artifact_text`, CLI passes `False`); 47 KB of httpcore/PIL/HF/torch DEBUG flood on every boot (`setup_logging` now strips pre-existing root handlers + pins `logging.basicConfig` to no-op + `_RootDebugFilter` for bare `name="root"` records); TTS log lines landed inside speech-preview quotes (silenced `kourai_common.tts_realtime` INFO on console); torch FutureWarnings/UserWarning visible on every boot (scoped `module=torch\..*` filter before RealtimeTTS import). Plus: AGENTS.md (per arxiv 2511.12884v1), CITATION.cff + README BibTeX, MCC pillars in architecture docs, 10 broken GitHub URLs, 30+ deslop edits across agent prompts. Boot output went 47 KB → 5 useful lines.
- 2026-05-06 — **Docker runtime workspace pyproject** [#182]. Runtime stage missed the workspace `pyproject.toml`; `kourai_common.paths.find_project_root()` raised at import, crash-looping every Python agent.
- 2026-05-06 — **Retry exponential-backoff jitter (±20%)** [#181].
- 2026-05-06 — **Summarization cheap-tier pin** [#180].
- 2026-05-06 — **Cache telemetry split by 5m vs 1h TTL** [#179].
- 2026-05-06 — **Cache-tighten `get_enriched_system_blocks`** [#178]. Static block defaults to 1h TTL within the 4-breakpoint budget.
- 2026-05-06 — **Split system-prompt cache breakpoints** [#177].
- 2026-05-06 — **Cross-host scratchpad rebuild Phase 1** [#176]. `kourai_common.scratchpad` + CLI `/scratchpad`; GUI/VN renderers gated on live smoke.
- 2026-05-06 — **Drop GUI zombie call sites surviving #173** [#175].
- 2026-05-06 — **TTS audio cache layer (M6 sub-task 2)** [#174]. `kourai_common.tts_cache` content-addressable disk cache, engine-agnostic via fetch-injection.
- 2026-05-06 — **Prune dead host-side anticipatory infrastructure** [#173]. Replacements filed as `kourai_common.*` cross-host rebuilds in the backlog.
- 2026-05-06 — **Centralize VN companion-spirits palette** [#172].
- 2026-05-06 — **Re-canonicalize `hex_color` + `rgb` on `AGENT_METADATA`** [#171].
- 2026-05-05 — **Cross-host DRY sweep — 10 extractions to `kourai_common/`** [#170]. Behaviour change: GUI first-launch `music_volume` 0.05 → 0.65 (fixes a 13× silent-music divergence vs CLI).
- 2026-05-05 — **Puck tutorial slice 1: mode cascade + `/settings [0]` entry** [#168].
- 2026-05-05 — **GUI synthesis indicator via `TypewriterManager.set_pending_audio`** [#166].
- 2026-05-05 — **CLI synthesis indicator during ~3s Kokoro wait window** [#165].
- 2026-05-05 — **Cleared 3 pre-existing zensical build warnings** [#164].
- 2026-05-05 — **Puck tutorial spec polish + zensical nav add** [#162].
- 2026-05-05 — **GUI `maidens.py` dedup against shared/agents.py** [#161].
- 2026-05-05 — **Research-grounded M6 ElevenLabs hybrid spec** [#160].
- 2026-05-03 — **Walked back M18 Phase 2 SSML markup investment** [#152]. Eleven v3 uses `[bracket]` audio tags, not SSML break tags. **Lesson logged in memory**: web-search SPECIFIC target's primary docs at the planning step. M6 promoted to pre-player-release blocker.
- 2026-05-03 — M18 Phase 2 — handoff/victory dicts + display chokepoint [#150]. *(Reverted in #152.)*
- 2026-05-03 — M18 Phase 2 hephaestus producer-side pilot [#149]. *(Reverted in #152.)*
- 2026-05-03 — **Uvicorn-takeover sweep across 10 specialists** [#148]. `kourai_common.log.run_uvicorn` centralizes `log_config=None`; fixes silently-dropped `log.info(...)`.
- 2026-05-03 — **M18 Phase 2 — engine-side SSML strip layer** [#147]. `kourai_common.ssml.strip_ssml` via `defusedxml`; stays as defensive infrastructure post-#152.
- 2026-05-03 — **Cross-platform graceful TTS fallback** [#146].
- 2026-05-03 — **vn_bridge headless TTS unblock + observability** [#145].
- 2026-05-02 — **Smoke-driven polish wave** [#140] [#141] [#142] [#143].
- 2026-05-02 — **`/aj-deslop` sweep on session feature PRs** [#138].
- 2026-05-02 — **M20 sub-task 1 — Kokoro voice tensor pre-warm** [#136].
- 2026-05-02 — **M18 Phase 3 Part A — strict kind routing** [#134]. Phase 3 Part B deferred.
- 2026-05-02 — **WSL audio cascade silenced** [#133].
- 2026-05-02 — **Wolfi base-image migration** [#125] [#127] [#130] (closes #98). All 13 Docker images on Wolfi; introduced `# research(YYYY-MM):` inline-rationale convention.
- 2026-05-02 — **`/aj-deslop` IMPL TODO closed** [#124] [#128] [#129].
- 2026-05-02 — **UX/DX + CI batch** [#118] [#119] [#120] [#121] [#122] [#123] [#131]. Includes Okabe-Ito CVD-safe agent badges (closes #10), captions toggle for audio-only mode (closes #19).
- 2026-05-01 — **M18 Phase 1 verified GREEN end-to-end** via `make smoke-m18`; same-day post-smoke DX cleanup [#114] [#115] [#116] [#117].
