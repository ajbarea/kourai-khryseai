# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-04-26 (M1 fully shipped — Round 6 accept+discard validated end-to-end with 22 `tool_use` frames in techne logs, 11 `tool_result` frames closing the loop, zero `parse_and_apply_fixes` hits across all 6 agent containers; `/clear` ANSI escape fix; M13 Forge Order Confirmation + M14 Metis-First parallel routing both shipped — the player-experience load-bearing pair is complete; M15 forge logging architecture planned; M3 tool-call streaming gap closed for Kallos+Dokimasia; M4 within-loop caching shipped; M10 speech-vs-action convention shipped; M11 GUI attachment send path shipped; /usage CLI command shipped + /reset_usage + Gemini pricing follow-on; Kokoro slow tests extracted + a2a-sdk pinned `<1.0` after protobuf-migration finding; agent-level READMEs for the 6 main pipeline agents; /project delete two-tier confirmation guard — see Shipped and revised M7)

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
  Tracked in [M10](#m10--speech-vs-action-rendering-convention).
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

## M2 — Carve out `kourai-forge-mcp`

> Status: planned · Blocked by: M1

Once M1 proves the forge tool set, lift it into a real MCP server in
`mcp_servers/forge/`. Specialists become MCP clients. Future agents register
without re-importing Python helpers.

**Why.** Three specialists currently re-import the same write/edit/read
primitives. A fourth user makes the duplication unacceptable. MCP also gives:

- Free tool discovery via `tools/list`.
- Hot-add via `notifications/tools/list_changed`.
- A wire format that other AI hosts (Claude Code, Cursor, IDE plugins) can
  speak to the same forge.

**Scope.**

- Stdio transport server in `mcp_servers/forge/server.py` exposing the M1 tools.
- `MCPToolkit` is already a live registry as of 2026-04-23; M2 wires the
  first real client users through it.
- Specialists invoke MCP via the toolkit; LiteLLM tool-use bindings reflect
  the MCP-served schemas.

References: [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture).
Current MCP spec version: **2025-11-25**; 2026 roadmap prioritises streamable-HTTP
scalability, Tasks lifecycle, and enterprise readiness
([blog.modelcontextprotocol.io/posts/2026-mcp-roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)).

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

## M7 — A2A v1.0 migration

> Status: planned · Bigger-than-the-firewall-claimed (see 2026-04-26 finding) ·
> Pyproject pinned to `<1.0` until M7 lands properly

`a2a-sdk` 1.0.2 was on PyPI as of 2026-04-26 and `uv lock` cheerfully picked
it up when resolution allowed `<2.0`. We bumped, ran the suite, and **broke
hard on collection** — 16 test files failed to import because v1.0 went
**protobuf-based** rather than the member-discriminated-Pydantic shape the
ROADMAP entry originally anticipated. Concretely:

- `Part` is now a `google._upb._message.Message`, not a Pydantic model.
- `TextPart`, `FilePart`, `DataPart`, `FileWithBytes` are no longer importable
  from `a2a.types` — the unified `Part` carries member-discriminated fields
  (`text`, `data`, `raw`, `url`, `filename`, `media_type`).
- The `_is_file_part` / `_get_file_bytes` firewall in `a2a_utils.py` covered
  inspection (`hasattr`-based forward compat) but **not construction** — every
  `Part(root=TextPart(text=...))` and `Part(root=FilePart(file=FileWithBytes(...)))`
  call site needs rewriting in `remote_connections.py`, `hosts/cli/streaming.py`,
  `hosts/gui/client.py`, plus the test mocks that build A2A-shaped objects.

**Pin tightened to `<1.0` on 2026-04-26** in `shared/pyproject.toml`,
`hosts/cli/pyproject.toml`, `hosts/gui/pyproject.toml` so `uv lock` stops
auto-adopting 1.0.x until M7 actually lands. Lockfile reverted to 0.3.26.

**Scope (revised).**

- Replace every `Part(root=TextPart(text=...))` construction site with the
  v1.0 protobuf-style `p = Part(); p.text = "..."` (or whatever the canonical
  pattern turns out to be — confirm against the v1.0 SDK examples).
- Replace every `Part(root=FilePart(file=FileWithBytes(bytes=..., mime_type=...)))`
  with the unified-Part equivalent (`media_type` field, flat `bytes`).
- Keep the inspection firewall in `a2a_utils.py` — it already handles both shapes.
- Update test mocks that synthesise Part-shaped objects (FilePart roundtrip
  tests in `tests/unit/test_a2a_utils.py`, the GUI attachment tests landed
  in M11, etc.).
- Do **all** of the above behind a feature branch where `pyproject.toml` is
  re-bumped to `<2.0` so CI exercises the new SDK end-to-end.
- Live A2A smoke against `make up` is required — the protobuf wire format
  has subtle differences (oneof discrimination, default value semantics)
  that mocked unit tests won't catch.

**Optional follow-ons.**

- **Signed Agent Cards** (A2A 1.0 flagship). Valuable if an agent endpoint
  ever leaves the docker-compose network; skip until then — crypto-key
  management is non-trivial and has no return inside a shared bridge network.
- **`.well-known/agent-card` static manifest generation.** Hephaestus already
  has a fallback AgentCard on live-fetch failure (``agents_manifest.py``, 2026-04-23);
  a richer manifest synthesised via ``kourai-dev`` from each agent's
  ``build_agent_card()`` would eliminate the boot-time HTTP fan-out entirely.

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

## M9 — Model-version refresh

> Status: planned · One-file edit · No API changes

``shared/src/kourai_common/config.py`` still names
``anthropic/claude-opus-4-6`` in ``MODELS_SMART["metis"]``. Opus 4.7 is the
current Anthropic flagship. Cheap bump: rename ``4-6`` → ``4-7`` once pricing
is confirmed equivalent. Cache thresholds match (Opus 4.7 = Opus 4.6 = 4096
tokens minimum), so the M4 caching markers carry over without re-tuning.

No metric-based rollout is needed for a Claude-family minor: behaviour is a
super-set. Gate the bump on a Round 6 smoke that exercises Metis's planning
loop and verifies the JSON-schema specs still come out clean.

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

## M6 — Future / unprioritized

### Surfaced 2026-04-26 during M1 Round 6 validation

- **Branch label sanitization (`forge_session.py`).**
  `ForgeSession.start(label=prompt_text[:24])` slugifies the label but
  doesn't strip backticks, slashes, or other special chars. Round 6a's
  session branch was `forge/20260426-114210-please-add-a-function-\`d` —
  git accepted it but the trailing backtick is ugly in `git branch -a`
  and `/project status`. Strip non-alphanumeric (and non-hyphen) before
  slugifying.

- **`read_file` tool schema description tightening.** Both Round 6 runs
  showed Techne misusing `read_file` on directory paths (`(fail)` returned
  cleanly, but wasted tool turns and tokens). Tighten the JSON schema
  description in `shared/src/kourai_common/forge_tools.py` to say "must
  be a regular file path, not a directory" and add an explicit example.
  The dispatch error path works; this is a model-behavior tightening only.

- **CLI greeting shows maiden name alongside kaomoji.**
  `hosts/cli/__main__.py:454` renders `_MAIDEN_FACES[_greet_name]` as the
  startup greeting but never the name. Players have to memorize the
  emoji-to-name mapping. Render as `{kaomoji} {NameTitle}: {quote}` —
  same line, name in gold. Lifts the gallery's identity work into the
  greeting so first-time players learn the maidens by face + name
  together.

- **WSL audio environment graceful handling.** ALSA emits a `cannot find
  card '0'` cascade on every CLI startup under WSL2 without an audio
  device. The error path already disables audio cleanly (`AudioManager`
  catches and logs the warning), but the noise is alarming on first
  launch. Detect WSL2 (presence of
  `/proc/sys/fs/binfmt_misc/WSLInterop` is the canonical signal) and
  set `SDL_AUDIODRIVER=dummy` before pygame init when ALSA isn't
  reachable; suppress the ALSA chatter behind a conditional on the
  same signal. Non-WSL Linux audio is unaffected.

- **Git context discovery for specialist agents in worktree.** Both
  Round 6 runs showed `🔍 $ git status --short` then `🔍 exit 128` from
  Metis and Techne early in their flow. Exit 128 from git means "not a
  git repository" — the agent containers' default cwd (`/app`) isn't
  the worktree. The `[project_root: ...]` prefix is in the user message,
  but agents aren't `cd`-ing to it before `git status`. Pick option (c)
  for minimum scope: have the bash-tool helper auto-prepend
  `cd <project_root> && ` when `project_root` is in the agent's context.
  Doesn't change agent prompts; doesn't churn agent_executors.

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

### Resolved (2026-04-22)

- **aiohttp override — no recurring-process needed.** The override for
  `aiohttp>=3.13.4` (CVE fix for a litellm transitive) now has an
  inline comment in `pyproject.toml` with the verification recipe
  (remove line, `uv lock`, check `uv pip audit`). Running the recipe
  on a schedule is over-engineering for a single override; revisit in
  ~6 months or whenever litellm's dep chain is next touched. If kourai
  ever grows more overrides, consider switching to Renovate's
  vulnerability alerts for the whole class.

---

## Shipped

One-liner per item, newest first. Detail moves out of this file when work lands.

- 2026-04-26 — **M1 fully shipped — Round 6 live smoke validated end-to-end** (accept path 6a + discard path 6b, both clean). Provider tool-use loop replaces the `parse_and_apply_fixes` regex parser everywhere it ran. Validation: 22 `'type': 'tool_use'` frames in techne container logs (with `toolu_*` IDs proving real provider blocks); 11 `'type': 'tool_result'` frames closing the loop; **zero `parse_and_apply_fixes` hits** across all 6 agent containers (`techne`, `hephaestus`, `metis`, `dokimasia`, `kallos`, `mneme`). Wall-clock: 244.8s on 6a, 418.6s on 6b — both under the 462s v2 baseline; the provider tool-use loop is faster than the regex parser AND cleaner. Bonus emergent behavior: Aidos's slop-detection now actively *teaches* commit-message hygiene with `<FACT category="skill" confidence="medium">` markers tracking the player's improvement across runs (e.g., flagging "comprehensive" as repeated slop after the first run). M1 detail block removed from above; this is the canonical record
- 2026-04-26 — `/clear` ANSI escape mangled by `prompt_toolkit.patch_stdout` (printed `?[2J?[1;1H` literally instead of clearing the viewport). Fix: new `hosts/cli/rendering._clear_screen()` helper writes the standard cursor-home + erase-screen sequence (`\x1b[H\x1b[2J`, matching Ubuntu's `clear`) directly to `_raw_out` (the pre-`patch_stdout` stream) — same pattern `_echo()` already uses to bypass the proxy. `hosts/cli/__main__.py` calls the new helper instead of `click.clear()`; click import retained for the rest of the CLI. Caught in AJ's REPL during M1 Round 6 smoke
- 2026-04-26 — `chat()` per-call tier override shipped (M14 follow-on): `kourai_common.config.get_model(agent_name, tier=None)` and `kourai_common.llm.chat(..., tier=None)` accept a tier kwarg that overrides `KOURAI_MODEL_TIER` for that single call. Backward-compat preserved (default `None` reads env). Metis's `discuss_tradeoffs` pinned to `tier="cheap"` so the M14 parallel discussion runs on Haiku regardless of pipeline tier — drops ongoing token spend on every tier-1 confirmation where the discussion is dropped silently. 8 new unit tests across `test_config.py` (5), `test_llm.py` (2), `test_metis_parallel.py` (1). Caveat documented in IMPL: `/usage` accumulator keys on `agent_name` (not `(agent_name, model)`), so cheap-tier discussion now masks the smart-tier spec model in the per-agent display. Follow-up PR scoped
- 2026-04-26 — M14 Metis-First Parallel Routing (Phase 2) shipped: Hephaestus's executor now spawns Metis's `discuss_tradeoffs` as a parallel `asyncio.create_task` BEFORE awaiting `determine_pipeline`, with a deadline-bounded await + emit on tier-2 (smart) and tier-3 (clarify) confirmations. Cancellation matrix covers every other route silently — CHAT, ASK_USER, malformed CONFIRM_ORDER, tier-1 confirmation, yolo pipeline. `[yolo:` skips the spawn entirely (no token spend on chatter the player won't see). Metis's output emits as a `working_status` event with the 📐 emoji prefix so the existing `_maidenify_status` renders her as a Metis comms window alongside the Hephaestus confirmation card. Together with M13 the player-experience load-bearing pair is complete: M13 made the gate legible, M14 fills the dead zone with architectural context. 13 new tests in `tests/unit/test_metis_parallel.py` covering the parallel-timing, cancellation matrix, and tier-gated surfacing. T8 (ParallelContext shared buffer feeding Metis's partial output back into the classifier prompt to enrich the read-back text) and the cheap-tier override on `chat()` deferred to follow-ups
- 2026-04-26 — M13 Forge Order Confirmation (Phase 1) shipped: pre-pipeline gate via new `CONFIRM_ORDER: <tier> "<read-back>"` routing token in Hephaestus. Three tiers (clear / smart / clarify) scale verbosity to ambiguity; tier-1 is ≤15 words; tier-2 surfaces Metis's suggested upsells; tier-3 asks one specific question. Executor parses the token, prefixes the Hephaestus emoji so the existing `_maidenify_status` renders a comms window, appends tier-specific hints, fires `send_input_required` — pipeline does NOT start until the player responds. Resume happens implicitly via context_id memory (no explicit metadata plumbing). `/yolo` opt-out via `[yolo: on]\n` text-tag (same convention as `[project_root: …]`); persisted in `CLISettings.yolo_enabled`. Voice regression guardrails in `tests/integration/test_confirmation_voice.py` (banned-phrase list — Hephaestus never roasts the player; ≤15-word tier-1 cap; round-trip-through-parser corpus). Round 7 added to `SMOKE_TODO.md` as the conference-poster artifact (three-tier walkthrough + `/yolo` verification, capture to `assets/poster/forge-order-tier-{1,2,3}.txt`). 52 new tests across 3 files. T4 (ForgeSession `[forge_intent]` block for explicit specialist context) deferred to a follow-up PR — gate works without it via context_id memory. Phase 2 (M14 Metis-first parallel routing) follows in a separate PR. Fail-safe: malformed `CONFIRM_ORDER` tokens log a warning and surface a generic ask, never auto-execute. Side-cleanup: `CLISettings.load()` now drops unknown JSON keys silently so future field-add PRs don't break older settings files
- 2026-04-26 — `/project delete` now confirms before nuking. Two-tier guard via `_confirm_project_delete()` in `hosts/cli/commands.py`: bare `delete` (registry-only; project files survive at the path) prompts `[y/N]` default-no; `--purge` (`shutil.rmtree` on the project dir; irreversible) requires typed `DELETE <name>` confirmation matching the existing `_reset_progression_data` pattern. New `--yes` / `-y` flag bypasses both for headless / scripted use. Success message now distinguishes the two paths and tells the player how to recover after a bare delete (`re-add with /project new <name> against that path`). 16 new unit tests in `tests/unit/test_project_delete_confirm.py`. Caught in AJ's REPL — typing `/project delete hello-forge` deleted instantly with no warning
- 2026-04-26 — Agent-level READMEs landed for the 6 main pipeline agents (Hephaestus + Metis + Techne + Dokimasia + Kallos + Mneme). Each covers responsibility, A2A surface (port, skill ID, streaming, INPUT_REQUIRED, project root, attachments), output artifact, tools, pipeline neighbors, key files, smoke recipe, and persona notes. Template-from-Kallos approach per ROADMAP guidance. Companion / spirit READMEs (Puck, Cupid, Aidos, Aletheia) deferred to when M6 voice-lab / gossip / romance work crystallises so we don't document an in-flight design twice. Stale ROADMAP claim about hypothesis being unused was struck — it's already in 11 test files
- 2026-04-26 — `/reset_usage` slash command + Gemini pricing follow-on to today's `/usage` ship: `kourai_common.pricing` grew `GEMINI_PRICING` covering `gemini-2.0-flash` ($0.10/$0.40 per M tokens), `gemini-2.5-pro` ($1.25/$10 — under-200K context tier), and `gemini-2.5-flash` ($0.30/$2.50). Cache-write left at 0 because Gemini bills caching as per-hour storage, not per-write — documented under-count. New unified `_ALL_PRICING` lookup table so `get_model_pricing()` searches both providers. New `/reset_usage` slash command zeroes the session counter mid-REPL via `reset_session_usage()`. 31 tests in `tests/unit/test_usage.py` (was 21 — added `TestGeminiPricing` × 4, `TestResetUsage` × 2, `TestResetUsageSlashCommand` × 2, plus updates to `TestGetModelPricing` and `TestUsageSlashCommand` since Gemini is no longer the canonical "unknown" example)
- 2026-04-26 — Test hygiene + a2a-sdk pin tightening: 5 Kokoro neural-inference tests in `tests/unit/test_tts_backends.py` marked `@pytest.mark.slow` and the `slow` marker registered in `pyproject.toml`; the `make test-unit` invocation in `scripts/test.py` and the `Unit Tests` job in `.github/workflows/tests.yml` both pass `-m "not slow"` so the push/PR fast lane skips them (they were intermittently `SystemExit:1`-ing on shared CI runners — model-load timeout). The nightly workflow when committed should run with the inverse marker (`-m slow`). Separately: `uv lock` auto-bumped a2a-sdk 0.3.26 → 1.0.2 during a session, the suite hard-broke on collection (16 import errors — protobuf-based Part replaced the Pydantic shape M7's firewall anticipated), so pyproject pins were tightened from `<2.0` to `<1.0` across `shared`, `hosts/cli`, `hosts/gui` and the lockfile reverted. ROADMAP M7 entry rewritten with the actual scope (every Part construction site needs rewriting, not just the inspection firewall)
- 2026-04-26 — `/usage` CLI command shipped: new `kourai_common.usage` per-session token accumulator (`record_usage` hooked into `chat()` and `chat_with_tools()`) plus `kourai_common.pricing` with April 2026 Anthropic rates (Haiku $1/$5, Sonnet $3/$15, Opus $5/$25; cache_read = input × 0.1, 5-min cache_write = input × 1.25). `/usage` slash command in CLI prints a per-agent breakdown (calls, input/output/cache_r/cache_w tokens, dollar cost) plus a TOTAL row. Unknown providers (Gemini, Ollama) render `$—` with a footer hint pointing at `ANTHROPIC_PRICING`. 21 new unit tests in `tests/unit/test_usage.py`. Streaming undercount note: `chat_stream()` not hooked because LiteLLM doesn't surface final-chunk usage from inside the iterator — affects only Metis spec / Dokimasia test-gen display paths
- 2026-04-26 — M11 GUI attachment send path closed end-to-end: `pygame_event_handler._submit_text` now drains `_pending_images` into a `(target, text, attachments)` 3-tuple on `send_q`; `GuiClient._send_message` builds a multi-part A2A `Message` with `TextPart` + one `FilePart(FileWithBytes(bytes, mime_type, name))` per attachment, identical wire shape to the CLI's `send_and_stream`; `DemoGuiClient` tolerates the new tuple and silently drops attachments; `DialogueEntry` carries an `attachments` field and `DialogueHistory` lazily decodes b64→PIL→`pygame.Surface` thumbnails (80px tall, right-aligned beneath the user bubble) so the player visually confirms what was sent. 10 new unit tests in `tests/unit/test_gui_attachment_send_path.py`. Live multi-modal smoke (Alt+V → submit → Hephaestus references the screenshot) folds into the next interactive `make gui` session
- 2026-04-26 — M3 tool-call streaming gap closed for Kallos and Dokimasia: `apply_lint_fixes` and `apply_test_fixes` now accept an `on_tool_call` parameter and forward it to `chat_with_tools`; both executors wire an `_on_tool` closure that emits one `send_working_status` per tool call (`✨ edit_file <path> (ok|fail)` for Kallos, `🧪 write_file <path> (ok|fail)` for Dokimasia), mirroring Techne's M1 wiring. The protocol stack from M1 (`chat_with_tools.on_tool_call` → `send_working_status` → `TaskStatusUpdateEvent` → SSE → Hephaestus → CLI `_maidenify_status`) was already in place; this PR wired the missing two endpoints. 7 new unit tests in `tests/unit/test_tool_call_streaming.py`. Live visual smoke (multiple per-tool status lines streaming during fix loops) folds into the next interactive `/project` session
- 2026-04-26 — M10 speech-vs-action rendering convention shipped: a 9th rule in `UNIVERSAL_RULES` ("SPEECH VS ACTION") propagates to all 9 specialists via `build_system_prompt`; Hephaestus's hand-rolled `ROUTING_PROMPT` carries it too and every `HEPH_HANDOFFS` value is now quoted; CLI `_comms_window` flips `_ITALIC` (and `_DIM+_ITALIC` for whisper) on lines starting with `"`; GUI `_draw_line_with_emotes` accepts an `oblique` kwarg backed by `pygame.freetype.STYLE_OBLIQUE` (no font asset add); the orphan `what_prefix='"'` on the aidos/aletheia debug Character defs in `script_labels.rpy` was stripped — `grep -rn what_prefix hosts/vn/` returns zero. Live visual smoke (italic dialogue, plain status across CLI/GUI/VN) folds into the next interactive `/project` session
- 2026-04-26 — M4 prompt caching landed in `chat_with_tools`: `cache_control: {"type": "ephemeral"}` on the system block, last tool definition, and initial user message; iterations 2–N of every Techne/Kallos/Dokimasia run hit the cache for the `[system + tools + initial-user]` prefix (which routinely carries 2K–10K tokens of `file_contents`/`git_context`/docs). `chat` and `chat_stream` mark the system block too — sub-threshold prefixes are silently ignored at no charge. `usage.cache_read_input_tokens` / `cache_creation_input_tokens` debug-logged after every call. Note: cross-call caching of just the agent system prompt does NOT pay today (Techne 1101 tokens vs 2048 Sonnet / 4096 Opus minimums); within-loop is the actual win
- 2026-04-23 — OTEL spans around every MCP tool call (``mcp.context7.query``, ``mcp.memory.*``); per-call latency now lands in Jaeger alongside A2A hops
- 2026-04-23 — ``mcp_servers/shell`` ``run_command`` advertises ``_meta["anthropic/maxResultSizeChars"] = 500000``; Claude Code-style clients stop truncating pytest / ruff tracebacks at the 25K default
- 2026-04-23 — Hephaestus ``RemoteAgentConnection.connect()`` falls back to synthesized ``AgentCard`` when ``A2ACardResolver`` fails; docker-compose cold-start no longer blocks the orchestrator on slow specialists
- 2026-04-23 — ``shared/src/kourai_common/agent_cards.py`` consolidates the ten copies of ``build_agent_card()`` that used to live in each ``agents/*/__main__.py``; one place to add signed cards / v1.0 extension fields when M7 lands
- 2026-04-23 — ``a2a-sdk`` pins lifted from ``<1.0`` to ``<2.0`` across ``shared``, ``hosts/cli``, ``hosts/gui``; ``_is_file_part`` / ``_get_file_bytes`` firewall extended to handle v1.0 unified-Part shape for forward compat (``uv lock`` still resolves 0.3.26 today)
- 2026-04-23 — ``MCPToolkit.get_tool`` stub + ``ToolStub`` class deleted; the registry is now pure data with no dead-code paths masking the real ``query_context7`` / ``search_memory_nodes`` functions
- 2026-04-20 — `/project` REPL flow + forge-session worktrees end-to-end (Round 1 happy path + Round 2 discard, both smoked against live Hephaestus)
- 2026-04-20 — `parse_and_apply_fixes` regex tolerates markdown-bold-wrapped headers and translates host paths to container paths
- 2026-04-20 — `ForgeSession.accept()` auto-commits uncommitted pipeline writes before fast-forward merge
- 2026-04-20 — Zero-arg `/project accept` and `/project discard` resolve the latest active session
- 2026-04-20 — `pytest -p no:cacheprovider` in Dokimasia eliminates the zombie `.pytest_cache` dir source (M5 stop-gap)
