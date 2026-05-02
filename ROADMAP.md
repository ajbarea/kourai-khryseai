# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-05-02. Active focus: **M18 Phase 2 (SSML inside dialogue bodies)** — see [IMPL.md](./IMPL.md) for the active work, the open invariants, and the priority-ordered "Up next" list. Pre-release perfection stance unchanged: May 2026 best practice no matter the cost, web-search before any implementation, architectural fix over expedient patch. Sister-repo audit weekly cron runs Mondays 12:00 UTC.

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
per `lang_code` on first use); subsequent calls have ~1-2s synthesis
lag for 50-100 char dialogue. Concrete 2026-04-29 example: AJ
launched `make cli`, saw Hephaestus's opening line `"I didn't get
thrown off Olympus to write bad software."` printed at 12:55:49,
heard the same line at 12:55:58 — **9 seconds of "text shown but
no audio" silence**, then 4 seconds of audible delivery.

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

## M6 — Future / unprioritized

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
- **ElevenLabs TTS + SFX migration (replaces Kokoro; repopulates
  the emote SFX library):** swap the GUI's TTS stack from Kokoro +
  edge-tts to ElevenLabs, and use the Sound Effects API
  (`client.text_to_sound_effects.convert` → `POST /v1/sound-generation`,
  model `eleven_text_to_sound_v2`, 0.5–30 s clips) to regenerate
  the `.ogg` library under `assets/audio/sfx/` that
  `hosts/gui/emote_sfx.py` plays today by emote-keyword lookup.
  Matches the sibling `tools/voice-lab` Next.js scratchpad.
  When it lands: drop `kokoro`, `soundfile`, and `edge-tts` from
  `hosts/gui`; drop `edge-tts` from `agents/hephaestus`; add the
  ElevenLabs Python SDK (or hit the API via `httpx`). SFX
  generation is one-shot into the asset tree (checked in or
  pulled from HF like the other voice assets), **not** per-line
  at runtime — keeps request latency and credit spend off the
  hot path. The VN bridge's `PACKAGE_NAME=hephaestus` coupling
  (see ECOSYSTEM.md "Cross-cutting quirks") still holds —
  hephaestus stays the VN's voice package, but what it carries
  shifts from `edge-tts` to the ElevenLabs surface. Tier strategy
  (verified 2026-04-23): Free tier (10k credits/month) is
  non-commercial AND requires `elevenlabs.io` in the title of any
  published content — fine for voice casting inside
  `tools/voice-lab`, unusable for shipped assets regardless of
  whether kourai is ever monetized. Cheapest viable path is
  **Starter at $5/month**: commercial license, 30k credits, and —
  critically — audio generated during a paid month retains
  commercial rights *perpetually* after cancellation, so a
  one-month burn (generate the whole SFX + voice library, then
  cancel) is a legitimate pattern. Creator (~$22/month, ≈121k
  credits) is the drop-in when one Starter month isn't enough
  headroom. Hygiene rule: never commit Free-tier-generated
  `.mp3/.wav/.ogg` files anywhere in this repo; `.gitignore`
  doesn't block audio today, so it's a discipline rule, not a
  tooling guard.
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

---

## Shipped

One-line per item, newest first. Detail moves to git history when work
lands — these docs are plans + scratchpad, not a historical archive.

- 2026-05-02 — **Smoke-driven polish wave** [#140] [#141] [#142] [#143].
  Four follow-on fixes surfaced by driving `make cli` /
  `python -m hosts.cli --prompt` from the host instead of theorizing.
  `[#140]` Adds elapsed-time + voice/agent fields to the existing
  `TTS: playback complete` log + a parallel line for
  `synthesize_to_wav` so per-utterance lag is empirically measurable.
  `[#141]` Adds INFO summary log per Kokoro pre-warm phase
  (`langs N/M elapsed=Xs`, `voices N/M elapsed=Xs`) so a clean
  startup leaves visible evidence the prewarm fired (was only
  logging failures via `logger.debug` before). `[#142]` Adds
  `get_host_agent_url` so direct `python -m hosts.cli` /
  `python -m hosts.gui` invocations reach agents through
  `localhost:<port>/` instead of the unresolved Docker service name
  (`make cli` was papering over this with a `--agent` override).
  `[#143]` Bumps Hephaestus's router `max_tokens=200→800` —
  conversational CHAT-mode responses (e.g. "what can you do?") were
  truncating mid-sentence at the 200-token cap that was set when
  the router only emitted short structured outputs.
- 2026-05-02 — **`/aj-deslop` sweep on this session's three feature
  PRs** [#138]. -102 LoC of multi-paragraph docstrings + rationale
  comment blocks trimmed from `audio_env.py`, `tts_realtime.py`,
  `messaging.py`, `streaming.py`, `vn_bridge/__main__.py`,
  `hephaestus/agent_executor.py`, and three test modules — the
  history+rationale lives in PR descriptions and git, not in the
  source. Functional behavior unchanged.
- 2026-05-02 — **M20 sub-task 1 — Kokoro voice tensor pre-warm** [#136].
  Added `_prewarm_agent_voices` alongside `_prewarm_agent_languages`
  at `RealtimeTTSEngine.__init__`; calls `KPipeline.load_single_voice`
  for every entry in `AGENT_VOICE_MAP`, materializing all 10 voice
  tensors into the per-pipeline voice cache. Eliminates the 1-3s
  per-voice download/parse cost stacked on top of synthesis lag for
  the first per-agent utterance. Live verification: 7.38s init time,
  all 10 agent voices materialized. Sub-tasks 2 + 3 (audio-led text
  reveal across CLI/GUI/VN) remain.
- 2026-05-02 — **M18 Phase 3 Part A — strict kind routing** [#134].
  Tagged the last two unmigrated forwarders (hephaestus pipeline
  forwarder + `BaseAgentExecutor` empty-input prompt), dropped the
  `kind is None` fallback in `streaming.py`, retired the
  `DIALOGUE_KEYWORDS` prose-keyword path in `vn_bridge`. Untagged
  messages route as not-dialogue everywhere — surfaces any future
  producer that forgets to tag rather than masking the bug. Phase 3
  Part B (`KIND_CODE`/`KIND_SPEC` distinct render paths) deferred
  until a producer actually emits either kind.
- 2026-05-02 — **WSL audio cascade silenced** [#133]. PortAudio's
  ALSA enumeration (~50 stderr lines) plus libjack connect-error
  chatter (5 lines) on every CLI/GUI/vn_bridge startup under WSL2 /
  headless Linux now suppressed via libasound noop handler (ctypes
  `snd_lib_error_set_handler`) at TTS module load + fd-redirect
  context manager around `_TextToAudioStream(...)`. Both gated by
  `KOURAI_AUDIO_DEBUG=1` opt-out. Closes the last fixable Round 6
  player-smoke follow-up bullet (only M15 logging architecture
  remains from that list).
- 2026-05-02 — **Wolfi base-image migration** (closes #98) across all
  thirteen Docker images (10 agents + vn_bridge + sandbox + 2 MCP
  sidecars + the `templates/backend` reference Techne reads), 0H
  baseline vs 1H Debian-glibc on CVE-2026-5435; durable GH Actions
  rescan workflow tracks the upstream-blocked npm `@xmldom/xmldom`
  CVE (issue #126, auto-closes once `>=0.8.13` ships); introduced
  `# research(YYYY-MM):` inline-rationale convention for web-search-
  derived design choices. PRs `[#125]` `[#127]` `[#130]`.
- 2026-05-02 — **`/aj-deslop` IMPL TODO closed** via three sweeps:
  `[#124]` recent justification prose (-73 LoC), `[#128]` streaming +
  log filter blocks (-24 LoC), `[#129]` CI workflow comment blocks
  (-21 LoC). Pre-release stance: keep only what helps a reader
  execute, drop "why we picked this" prose.
- 2026-05-02 — **UX/DX + CI batch** in seven PRs. `[#118]` dropped
  dead `AGENT_METADATA` color fields (-19 LoC), `[#119]` Okabe-Ito
  CVD-safe agent badges (closes #10), `[#120]` captions toggle for
  audio-only dialogue mode (closes #19), `[#121]` apt cache for
  `portaudio19-dev` (cuts 15+min Azure-mirror flakes), `[#122]` GHA
  layer cache for MCP sidecar Docker builds, `[#123]` NO_COLOR
  honored across the rest of `styling.py`, `[#131]` ty narrowings
  surfaced by `/aj-ci-audit` (record.args tuple-narrowing + ContentKind
  literal in captions test).
- 2026-05-01 — **M18 Phase 1 verified GREEN end-to-end** via
  `make smoke-m18`; full specialist cascade hephaestus → metis →
  techne → dokimasia → kallos → mneme produced two commit groups in
  57.4s, defensive virtues fail-soft fired exactly as designed. Same-
  day post-smoke DX cleanup: `[#114]` honest rebuild-failure timer,
  `[#115]` `--voice/--no-voice` + `KOURAI_TTS` env + virtues fail-soft
  + smoke gate-ack regex narrowing, `[#116]` soft-fail banner on pre-
  mneme abort, `[#117]` uvicorn.access filter (44 lines/min healthcheck
  noise → 0).

