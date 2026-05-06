# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-05-06. Active focus: **M6 ElevenLabs hybrid** as
pre-player-release blocker. M6 sub-task 2 (audio cache layer) shipped
under Kokoro [#174] and rides along into the swap; sub-tasks 1/3/4/5
gate on M20 + VN smoke landing first. See [IMPL.md](./IMPL.md) for the
active work, open invariants, and priority-ordered "Up next" list.
Pre-release perfection stance unchanged: May 2026 best practice no
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
> shipped 2026-05-02 · Sub-tasks 2-4 planned · Surfaced 2026-04-29
> (post-rebuild CLI session) · Depends on M19 (RealtimeTTS provides
> word-level timing callbacks for Kokoro English voices) and M18
> (content-kind metadata routes dialogue-only to the synced reveal
> path) · Player- and developer-experience improvement spanning all
> three player surfaces

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

## M6 — ElevenLabs hybrid (pre-player-release blocker)

> Status: spec'd 2026-05-05 · Implementation queued · Gated on M20
> audio-led reveal + VN smoke landing first

Promoted from "future-future" 2026-05-03 after strategic review of the
character-voice-quality gap between Kokoro (current) and ElevenLabs.
Character voice IS the product (per-maiden personality is the core
mechanic); Kokoro plays 10 voicepacks but cannot deliver per-character
emotional control. ElevenLabs can.

Spec landed 2026-05-05; full detail in [IMPL.md "M6 — ElevenLabs
hybrid"](./IMPL.md#m6--elevenlabs-hybrid-pre-player-release-blocker) —
Flash v2.5 + v3 model split (verified against ElevenLabs's May 2026
docs), per-engine markup adapter design (replaces the walked-back
SSML approach), client-side audio cache layer (confirmed: ElevenLabs
has no server-side cache by request hash; the History API indexes by
`history_item_id` only), per-persona prosody pass, sub-task ordering,
and cost projections at 100 / 1000 player scale.

Production swap gated on M20 audio-led text reveal + VN smoke landing
first — character voice quality is most visible against a polished
dialogue UX; doing M6 before audio-led reveal would burn ElevenLabs
spend chasing UX bugs we already know about.

[VOICE_CASTING_PLAN.md](../tools/voice-lab/VOICE_CASTING_PLAN.md) has
voice IDs + per-maiden settings cast. The `tools/voice-lab/` Next.js
app is the casting/preview surface that landed pre-2026-05; production
wiring (M6) is the swap from Kokoro into the same `RealtimeTTSEngine`
public surface.

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

- 2026-05-06 — **Retry exponential-backoff jitter (±20%)** [#181].
  `with_retry` was deterministic; concurrent agents hitting a 429
  retried in lockstep and re-collided. Apply `random.uniform(0.8, 1.2)`
  multiplier to the computed delay; API-provided "Please retry in Xs"
  path stays deterministic.
- 2026-05-06 — **Summarization cheap-tier pin** [#180]. `_manage_memory`
  was resolving the summarization sub-call to the agent's tier (Opus on
  smart). Pin to `tier="cheap"` per Anthropic's context-compaction
  cookbook (Haiku is 5× cheaper and sufficient for "summarize this").
  Mirrors M14's `metis.discuss_tradeoffs` pattern.
- 2026-05-06 — **Cache telemetry split by 5m vs 1h TTL** [#179].
  Post-#178 follow-on. `AgentUsage` splits into `cache_write_5m_tokens`
  + `cache_write_1h_tokens` from `usage.cache_creation` sub-object;
  `ModelPricing` gains `cache_write_1h_per_m` (2× input on Anthropic);
  `compute_cost` combines both rates. Closes the ~60% cost under-quote
  that #178 introduced.
- 2026-05-06 — **Cache-tighten get_enriched_system_blocks** [#178].
  Replaces string-returning `get_enriched_system_prompt` with
  `get_enriched_system_blocks` returning cache-marked
  `[truly-static, player-dynamic]` text blocks; new public helper
  `cached_text_blocks(*chunks, static_ttl="1h")` for hephaestus's
  manual routing path. Static block defaults to 1h TTL — Anthropic's
  May-2026 docs explicitly recommend it for long interactive sessions.
  Within the 4-breakpoint budget (static-1h / player-dynamic-5m /
  summary-5m / first-user-5m). ~5× reduction in static-block write
  tokens on top of #177's ~3-7×.
- 2026-05-06 — **Split system-prompt cache breakpoints** [#177].
  `_build_contextual_messages` was concatenating the dynamic
  `semantic_summary` onto the static system content, invalidating the
  prompt cache on every Mneme summarization. Restructure as a list of
  two `cache_control` text blocks (static + summary). ~3-7× reduction
  in cache-write tokens on long Forge Party sessions.
- 2026-05-06 — **Cross-host scratchpad rebuild Phase 1** [#176].
  `kourai_common.scratchpad` data layer + CLI `/scratchpad` slash;
  replaces the orphan classifier consumer left by #175. CLI streaming
  + GUI's post-#175 drop branch route to the same buffer. 2026 LLM
  CoT-visibility best practice is render-distinct (not spoken).
- 2026-05-06 — **Drop GUI zombie call sites surviving #173** [#175].
  Eight call sites referenced `GUIComponentsIntegration.get_scratchpad`
  / `.status_bubbles` attributes that #173 deleted; `render.py`'s
  per-frame `get_scratchpad().draw()` would have crashed every GUI
  frame. Tab key unbound; cross-host scratchpad rebuild rebinds when
  its renderer lands. ty: 22 → 14 diagnostics.
- 2026-05-06 — **TTS audio cache layer (M6 sub-task 2)** [#174].
  `kourai_common.tts_cache` content-addressable disk cache. Cache key
  is `sha256` of length-prefixed
  `(text, voice_id, model_id, sorted-keys-json(voice_settings))`;
  layout `${XDG_CACHE_HOME}/kourai/tts/{key[:2]}/{key}.{ext}`;
  oldest-mtime-first eviction at 500 MB cap. Engine-agnostic via
  fetch-injection — rides into the ElevenLabs SDK swap at M6 sub-task 3.
  Enabled at vn_bridge where static dialogue dicts yield near-100% hit
  rate once warm.
- 2026-05-06 — **Prune dead host-side anticipatory infrastructure**
  [#173]. Deleted the staged-but-unwired GUI stratum (Scratchpad,
  PipelineStatusIndicator, StatusBubbles, AgentPersonality
  indicators/handoff) plus CLI's `gossip_cli` surface; ~9 source files
  + 6 test files removed; ~105 false-coverage tests pruned (Mockery
  anti-pattern). Replacements filed under "Cross-host shared rebuilds"
  in the backlog as `kourai_common.*` data + thin host renderers.
- 2026-05-06 — **Centralize VN companion-spirits palette** [#172].
  5 named constants in `script_data.rpy` + 15 literal sites swapped to
  references. Walked back `_bright_hex(AGENT_COLORS[name])` after
  computing the actual outputs (RGB-distance 102 / 71 from VN's current
  literals) — VN's palette is a separate desaturated companion-spirits
  palette, not drift from canonical.
- 2026-05-06 — **Re-canonicalize `hex_color` + `rgb` on `AGENT_METADATA`**
  [#171]. Restores the keys #118 removed; missing VN as a consumer was
  a latent KeyError. Single canonical source: GUI's warm-gold theme for
  the 6 maidens; CLI styling's Okabe-Ito CVD-safe values for
  puck/cupid. GUI's `_AGENT_COLORS` derived from shared `rgb` instead
  of duplicated.
- 2026-05-05 — **Cross-host DRY sweep — 10 extractions to
  `kourai_common/`** [#170]. New shared modules: `paths`,
  `settings_audio`, `onboarding_data`, `demo_script`, `emote_sfx`,
  `audio_dsp`, `dialogue_pacing`, `message_classifier`. Extended
  `agents.py` with `EMOJI_PREFIX` + `detect_agent`. Behavior change:
  GUI first-launch music_volume default 0.05 → 0.65 (fixes a 13× silent-
  music divergence vs CLI). pyloudnorm + Pydantic v2 + VN demo-script
  bridge filed as follow-ups in IMPL.
- 2026-05-05 — **Puck tutorial slice 1: mode cascade + `/settings [0]`
  entry** [#168]. `apply_mode_cascade(mode)` flips all 7 cascade
  settings idempotently; `/settings [0]` panel entry reads + flips +
  prints diegetic line. `romance_enabled` stays False in both paths
  (separate two-step opt-in). Slices 2-4 queued.
- 2026-05-05 — **GUI synthesis indicator via
  `TypewriterManager.set_pending_audio`** [#166]. Companion to #165's
  CLI indicator; renders a single-ellipsis placeholder while
  `displayed_chars == 0` during the ~3s Kokoro CPU wait window. Cleared
  by `on_audio_start` / `advance_word` / `flush_remaining` / `reset`.
  VN equivalent pending live-smoke.
- 2026-05-05 — **CLI synthesis indicator during ~3s Kokoro wait window**
  [#165]. Pre-renders `Name face …` (dim ellipsis) before `tts.speak`;
  cleared via CR + erase-line ANSI when karaoke header opens or Tier 2
  box renders.
- 2026-05-05 — **Cleared 3 pre-existing zensical build warnings**
  [#164]. Mechanical drift sweep: escaped `\[0\]` / `\[status\]`
  link-reference patterns; retargeted stale
  `gui.md#text-to-speech-system-` anchor.
- 2026-05-05 — **Puck tutorial spec polish + zensical nav add** [#162].
  `docs/architecture/puck-first-run-tutorial.md` added to nav; status
  block matches ROADMAP convention. May 2026 best-practice cross-check
  confirmed the spec's progressive-disclosure + in-fiction-integration
  approach.
- 2026-05-05 — **GUI `maidens.py` dedup against shared/agents.py**
  [#161]. Promoted GUI's richer content (extra emote-prefixed quotes,
  missing return-handoff routes) into shared; GUI now imports + builds
  legacy `AGENTS` dict from a local color map. 327 → 101 lines.
- 2026-05-05 — **Research-grounded M6 ElevenLabs hybrid spec** [#160].
  Spec'd against ElevenLabs's actual May 2026 docs. Open question
  answered: no server-side audio cache by request hash; client-side
  cache per Supabase cookbook pattern. Per-engine markup adapter
  design; audio cache spec; sub-task ordering + M20+VN-smoke gating.
  ROADMAP cleanup: M6 section unmuddled; "Future / unprioritized
  backlog" H2 added.
- 2026-05-03 — **Walked back M18 Phase 2 SSML markup investment**
  [#152]. Reverted dialogue-content SSML from #149/#150 after
  web-searching ElevenLabs's actual docs: Eleven v3 doesn't support
  SSML break tags (uses `[bracket]` audio tags); Flash V2.5 supports
  `<break>` but ElevenLabs warns against overuse.
  `kourai_common.ssml.strip_ssml` + defusedxml dep stay as defensive
  infrastructure. **Lesson logged in memory**: web-search SPECIFIC
  target's primary docs at the planning step. M6 promoted to
  pre-player-release blocker.
- 2026-05-03 — **M18 Phase 2 SSML rollout — handoff/victory dicts +
  display chokepoint** [#150]. Reverted in #152.
- 2026-05-03 — **M18 Phase 2 hephaestus producer-side pilot** [#149].
  Reverted in #152.
- 2026-05-03 — **Uvicorn-takeover sweep across 10 specialists** [#148].
  `kourai_common.log.run_uvicorn` helper centralizes `log_config=None`;
  10 specialists swap their `uvicorn.run` for the helper. Fixes
  silently-dropped `log.info(...)` (uvicorn's default dictConfig was
  wiping `setup_logging`'s root handlers).
- 2026-05-03 — **M18 Phase 2 — engine-side SSML strip layer** [#147].
  `kourai_common.ssml.strip_ssml` via `defusedxml` (XXE / billion-laughs
  hardened); feeds plain text to Kokoro. Producer-side wrap reverted in
  #152; strip layer stays as defensive infrastructure.
- 2026-05-03 — **Cross-platform graceful TTS fallback** [#146].
  `audio_env.is_audio_output_available()` probes PortAudio after
  cheap-NO gates (`KOURAI_TTS=off`, WSL2-without-WSLg, headless Linux);
  `RealtimeTTSEngine.__init__` defaults `muted=None` (auto-detect) with
  per-platform fix recipe on auto-mute.
- 2026-05-03 — **vn_bridge headless TTS unblock + observability**
  [#145]. Three connected fixes: `RealtimeTTSEngine(muted=True)` at
  construction skips the audio-device probe; `log_config=None` on
  `uvicorn.run` stops uvicorn's dictConfig wipe; `force=True` on
  `basicConfig` so transitive imports can't no-op the handler install.
- 2026-05-02 — **Smoke-driven polish wave** [#140] [#141] [#142] [#143].
  Surfaced by driving `make cli` from the host: TTS playback +
  synthesize_to_wav timing logs (#140); Kokoro pre-warm INFO summary
  (#141); `get_host_agent_url` for direct host invocation (#142);
  Hephaestus router `max_tokens=200→800` (#143).
- 2026-05-02 — **`/aj-deslop` sweep on this session's three feature
  PRs** [#138]. -102 LoC of multi-paragraph docstrings + rationale
  comment blocks trimmed across 8 modules; behavior unchanged.
- 2026-05-02 — **M20 sub-task 1 — Kokoro voice tensor pre-warm** [#136].
  `_prewarm_agent_voices` materializes all 10 agent voice tensors at
  `RealtimeTTSEngine.__init__`; eliminates 1-3s per-voice download/parse
  cost on first per-agent utterance.
- 2026-05-02 — **M18 Phase 3 Part A — strict kind routing** [#134].
  Tagged remaining unmigrated forwarders; dropped `kind is None`
  fallback + `DIALOGUE_KEYWORDS` prose-keyword path. Untagged messages
  now route as not-dialogue everywhere. Phase 3 Part B deferred.
- 2026-05-02 — **WSL audio cascade silenced** [#133]. libasound noop
  handler at TTS module load + fd-redirect context around
  `_TextToAudioStream(...)` suppress ~55 stderr lines/startup under
  WSL2/headless. `KOURAI_AUDIO_DEBUG=1` opt-out.
- 2026-05-02 — **Wolfi base-image migration** [#125] [#127] [#130]
  (closes #98). All 13 Docker images on Wolfi (0H baseline vs 1H
  Debian-glibc on CVE-2026-5435); durable GH Actions rescan workflow
  tracks issue #126 (xmldom upstream block); introduced
  `# research(YYYY-MM):` inline-rationale convention.
- 2026-05-02 — **`/aj-deslop` IMPL TODO closed** [#124] [#128] [#129].
  Three sweeps; -118 LoC of "why we picked this" prose. Pre-release
  stance: keep only what helps a reader execute.
- 2026-05-02 — **UX/DX + CI batch** [#118] [#119] [#120] [#121] [#122]
  [#123] [#131]. `AGENT_METADATA` dead-fields drop, Okabe-Ito CVD-safe
  agent badges (closes #10), captions toggle for audio-only mode
  (closes #19), apt cache for portaudio19-dev, GHA layer cache for MCP
  Docker builds, NO_COLOR honored across `styling.py`, ty narrowings.
- 2026-05-01 — **M18 Phase 1 verified GREEN end-to-end** via
  `make smoke-m18`; full hephaestus → metis → techne → dokimasia →
  kallos → mneme cascade in 57.4s, defensive virtues fail-soft fired
  as designed. Same-day post-smoke DX cleanup: [#114] [#115] [#116]
  [#117].
