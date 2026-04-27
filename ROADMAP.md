# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-04-27 (M1 fully shipped + 5 Round 6 M6-future bullets closed (#34/#35/#36/#38) + research-driven ROADMAP additions (#37) + four OSS-CC lifts shipped (#39/#40/#41); 2026-04-27 live smoke pass uncovered + fixed two infrastructure bugs: forge worktree gitdir resolves from container (#42) and CLI input_required follow-up preserves forge tags (#43); spec drift watcher cron (this PR) makes "track latest aggressively" automated rather than nudge-driven; M7 scope grew the Message.metadata migration item informed by the v1.0 spec research; all the rest from the prior reviewed line still applies — see Shipped, revised M2/M7, and the M6 "Surfaced from external research" subsection)

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

**Three client capabilities to declare when M2 lands** (the host advertises
these to MCP servers during the
[initialization handshake](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle#initialization)
— researched 2026-04-26):

- **`roots`** — file:// URI boundaries the MCP server is allowed to operate
  within. Exact fit for our forge tools — when M2 carves out
  `kourai-forge-mcp`, the host declares the player's `project_root` as the
  sole root; the server's `read_file` / `write_file` / `edit_file` calls
  validate against the root list rather than re-implementing
  `validate_file_path`. Includes `notifications/roots/list_changed` so a
  `/project switch` mid-session re-scopes the server cleanly.
- **`elicitation`** — server-initiated request for additional information
  from the user. Spec-blessed analog of M13's homegrown `CONFIRM_ORDER`
  pause primitive. Once M2 is up, route `INPUT_REQUIRED` through
  elicitation rather than reinventing the channel — same UX, standard
  wire format, future MCP-aware hosts get the gate for free.
- **`sampling`** — server-initiated LLM call back through the host.
  Useful if a future `kourai-forge-mcp` skill (e.g., a synth-test
  generator) wants to ask Hephaestus to classify intent without
  bundling its own LiteLLM client. Comes with the MUST-explicit-consent
  rule per the spec, so it pairs naturally with the existing YOLO MODE
  toggle (`[yolo: on]` → auto-approve sampling; otherwise prompt).

Security note from the 2025-11-25 spec: tool annotations are explicitly
called out as **untrusted** unless the server itself is trusted.
Implication for M2 — when the forge MCP server publishes tool
descriptions, those descriptions can lie if the server is malicious;
the host's permission gate must be the source of truth, not the
server's self-described risk level.

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

**Spec deltas to mind during the migration** (per the
[A2A v1.0 specification](https://a2a-protocol.org/latest/specification/)
fetched 2026-04-26):

- **`A2A-Version` header is now required** — clients MUST send it; the
  server assumes v0.3 if absent. Add it to every outbound request in
  `remote_connections.py` before flipping the SDK pin. A missing header
  on a v1.0 server silently downgrades the negotiation.
- **TaskState gained `AUTH_REQUIRED`** alongside `INPUT_REQUIRED`. When
  M2 introduces an OAuth-scoped MCP server (e.g., a future GitHub-API
  forge tool), specialists can now pause for re-auth without crashing
  the task — wire a CLI handler that mirrors the M13 `INPUT_REQUIRED`
  flow but routes the player to a one-time auth prompt instead of a
  free-text response.
- **Multiple concurrent streams per task are explicitly supported**
  in v1.0. M14's parallel routing currently spawns Metis as a
  background `asyncio.create_task` and merges its output into the
  same `TaskStatusUpdateEvent` channel as Hephaestus. Once on v1.0,
  Metis can publish to a sibling stream of the same task and the CLI
  can render the two comms windows from independent SSE subscriptions
  — cleaner cancellation semantics than the current shared channel.
- **Kind discriminator removed from messages** — already known from
  the 2026-04-26 collection-error finding, but worth restating: every
  `Message(kind=...)` constructor needs to drop the field at the same
  time the `Part` rewrite happens.
- **Authenticated extended cards.** Skip until M2 — useful when the
  forge MCP server publishes both a public card (capability summary)
  and a credential-gated extended card (full tool list with internal
  schemas). Not load-bearing for the v1.0 cutover itself.
- **Migrate forge text-tags to `Message.metadata`.** The
  `[project_root: ...]` / `[yolo: on]` / `[auto_approve_reads: on]`
  /  `[relationship_tiers: ...]` text prefixes the CLI prepends today
  exist because a2a-sdk 0.3.x didn't guarantee `Message.metadata`
  propagation across every transport. v1.0 made metadata a key-value
  JSON map that propagates with the Message and is grouped by
  `contextId` across multi-turn (per the
  [v1.0 spec](https://a2a-protocol.org/latest/specification/) — "agents
  MAY use the contextId to maintain internal state, conversational
  history, or LLM context across multiple interactions"). Once the SDK
  migration lands, replace every `extract_*` / `parse_*` text-regex in
  `kourai_common.a2a_utils` and `agents.hephaestus.agent` with
  `message.metadata.get("project_root")` etc., and delete the
  text-tag construction in `hosts/cli/__main__.py` and the recursion
  patch in `hosts/cli/streaming.py`. This kills a whole indirection
  layer — text becomes for the user/LLM, metadata for the system.
  Surfaced 2026-04-27 during smoke-pass investigation of why M13
  `yes` confirmations dropped specialist context (text-tags lost on
  input_required follow-up — patched as text-tag re-prepending in
  the meantime).

**Spec drift tracker (lives in repo, runs on cron).** A weekly GitHub
Actions cron in `.github/workflows/spec-watch.yml` watches the canonical
MCP + A2A spec/SDK URLs (`scripts/watch_protocols.py`) and opens an
issue tagged `protocol-watch` on any drift — covers the MCP 2025-11-25
spec page, the MCP blog, the A2A latest spec, both repos' release atom
feeds, and PyPI for `a2a-sdk` + `mcp`. State persists between runs via
`actions/cache`; transient fetch failures carry the prior baseline
forward unchanged. Local dry-run via
`python scripts/watch_protocols.py --dry-run`. Built 2026-04-27 to
turn "track latest aggressively" from an ad-hoc nudge-driven habit
into a triageable inbox item — direct response to the 2026-04-27
finding that A2A v1.0's Message.metadata channel had landed months
before we noticed and built around it.

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

**Prioritization (player-experience-per-effort, highest first).**

1. ~~**`/compact`** — universal across every clone, we don't have it,
   Mneme already has the documenter persona. Single-PR-sized.~~
   **Shipped 2026-04-26** (see Shipped section).
2. **MCP `roots` + `elicitation` declared at M2 init** — design-time
   work, near-zero cost if done while M2 is being scaffolded;
   retrofitting later is much more painful.
3. ~~**`/permissions` granular tool gating** — small extension to
   `CLISettings`, big UX win for players who want partial autonomy
   without full YOLO. Maps onto existing `MUTATING_TOOL_NAMES`.~~
   **Shipped 2026-04-26** (see Shipped section).
4. ~~**`A2A-Version` header** — must-do prerequisite for any v1.0
   migration attempt. One header field, one line of code.~~
   **Shipped 2026-04-26** (see Shipped section).
5. ~~**`/cost` alias for `/usage`** — five-line cleanup matching
   OSS-CC vocabulary so muscle-memory carries over.~~
   **Shipped 2026-04-26** (see Shipped section).

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
  the maidens know about me." Output goes into `agent_memory.db`
  itself — same store, new `player_facts` table.

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
- 2026-04-27 — Spec drift watcher cron (this PR): new weekly GitHub Actions cron `.github/workflows/spec-watch.yml` invokes `scripts/watch_protocols.py` to check 7 canonical URLs (MCP 2025-11-25 spec page, MCP blog, A2A latest spec, A2A + MCP repo release atom feeds, PyPI `a2a-sdk`/`mcp`) and opens a `protocol-watch`-tagged GitHub issue on any digest drift. Per-source digest functions (`html` full-content hash, `feed` entry-title hash, `pypi` version string) keep the diff signal-rich rather than a noisy bytewise compare. State persists between cron runs via `actions/cache`; transient HTTP failures carry the prior baseline forward so a bad week doesn't wipe state. Local dry-run via `python scripts/watch_protocols.py --dry-run`. 29 unit tests in `tests/unit/test_watch_protocols.py` covering digest stability, diff detection, fetch-failure handling, state roundtrip, dry-run path, and watch-list contract (no duplicate keys, every kind has a digester, every URL is https, every watch has a non-empty note). Direct response to the 2026-04-27 finding that A2A v1.0's `Message.metadata` channel landed months ago without us noticing — turning "track latest aggressively" from ad-hoc nudge-driven into a triageable inbox item
- 2026-04-27 — CLI input_required follow-up preserves forge tags (#43): two coupled infrastructure bugs surfaced during 2026-04-27 live smoke. (1) `git worktree add` writes a `.git` pointer file containing a host-absolute `gitdir: /home/<host_user>/.kourai_khryseai/.git/worktrees/...` — the container previously only mounted at `/home/kourai/...` so git inside the container couldn't follow the pointer (`fatal: not a git repository: /home/ajbar/...`, `exit 128`). Fix: each specialist now bind-mounts `~/.kourai_khryseai` twice — once at the canonical container-side path AND once at `${HOME:-/root}/.kourai_khryseai` so compose's host-side ${HOME} expansion lands the same physical files at both paths inside the container. (2) git ≥2.35 dubious-ownership refusal (CVE-2022-24765 hardening) blocked the kourai container user from operating on host-owned files; added `git config --global --add safe.directory '*'` in the host.Dockerfile after `USER kourai`. Inspired by the Claude Code git-wtadd pattern researched 2026-04-27. Root-cause UID alignment lives in M5
- 2026-04-27 — CLI input_required follow-up preserves forge tags (this PR): the smoke pass that uncovered the gitdir bug ALSO uncovered a CLI bug — `hosts/cli/streaming.py`'s `input_required` follow-up loop recurses inside `send_and_stream`, bypassing the REPL's tag-prepending block in `__main__.py`. Every M13 confirmation `yes` (and every mid-pipeline ASK_USER reply) arrived at specialists without `[project_root: ...]` / `[yolo: on]` / `[auto_approve_reads: on]`, so they fell back to `Path.cwd()` = `/app` and broke git context — the same `exit 128` we just fixed at the infrastructure layer. Fix: new `forge_tags: list[str] | None = None` kwarg on `send_and_stream` carries the tags through the recursion; the input_required handler re-prepends them to the player's response before the recursive call. `__main__.py` constructs the tag list once per turn (replacing the previous string-concatenation pattern with a list-based one) and passes it. 3 new tests in `test_cli.py::TestForgeTagsPropagation` (re-prepend on follow-up, no-op when bare, /q quit doesn't recurse). All 32 tests in test_cli.py green. M7 scope grew a follow-on item: migrate text-tags to `Message.metadata` per A2A v1.0 spec once the SDK pin flips — text-tag carrier is the 0.3.x bridge
- 2026-04-26 — `A2A-Version` header + `/cost` alias bundled (tier-4 + tier-5 lifts from the OSS-CC research sweep, both small enough to share a PR): (1) new `kourai_common.a2a_utils.make_a2a_http_client(timeout=...)` helper constructs an `httpx.AsyncClient` carrying the spec-required `A2A-Version: 0.3` header — without it, an a2a-sdk 1.0.x server silently downgrades to 0.3 semantics. Centralising construction means one bump-site for the eventual M7 cutover. Wired into all four outbound A2A construction sites: `agents/hephaestus/remote_connections.py` (Hephaestus → specialists), `hosts/cli/__main__.py` (CLI → Hephaestus), `hosts/cli/headless.py` (scripted CLI), `agents/vn_bridge.py` (VN bridge → Hephaestus). New `A2A_PROTOCOL_VERSION = "0.3"` constant pinned in `a2a_utils.py` with a regression-guard test so M7's bump is deliberate. (2) `/cost` slash command added as an alias for `/usage` — matches the vocabulary every OSS Claude Code clone surveyed (ClawCode, Cline, OpenCode) ships, so players coming from those tools find the right command on first try. 8 new tests in `test_a2a_utils.py::TestA2AHttpClient` (5 — header carried, version-pin regression guard, extra-headers merge, timeout passthrough, explicit override) and `test_usage.py::TestUsageSlashCommand` (3 — `/cost` registered in completer, dispatch resolves to same handler, source-level guard against accidental refactor split). All 116 tests across the affected files green
- 2026-04-26 — `/permissions` slash command (tier-2 lift from the OSS-CC research sweep, second to ship): unified view + toggle for pipeline-gating policies. Adds a granular middle ground between `/yolo` (binary CONFIRM_ORDER bypass) and the always-on gate. New `auto_approve_reads` policy, when on, tells Hephaestus to skip CONFIRM_ORDER ONLY for read-only / planning-only routes (Metis-only, Mneme-only, CHAT) and still gate anything that would touch disk via Techne / Kallos / Dokimasia (the three agents whose tools are in `MUTATING_TOOL_NAMES`). Mechanism mirrors `/yolo`: CLI prepends `[auto_approve_reads: on]` text-tag, Hephaestus extracts via new `extract_auto_approve_reads` helper, system prompt augmented with explicit "ONLY when pipeline contains none of {techne, kallos, dokimasia}" guard so the LLM doesn't widen the bypass. `/yolo` still wins when both flags are set. CLI `/permissions` slash command shows current state of every gate; `/permissions <name>` toggles. Aliases (`yolo`, `reads`) keep typing short; the long names (`yolo_enabled`, `auto_approve_reads`) also work. 12 new unit tests across `TestAutoApproveReadsBypass` (6 — extract function, prompt augmentation, yolo-wins-when-both), `TestCLISettingsAutoApproveReadsField` (2), `TestPermissionsCommand` (4 — bare list, toggle persists, unknown gate help, yolo alias). All 33 tests in `test_confirmation_protocol.py` pass; full CLI + hephaestus suite (78 tests) green
- 2026-04-26 — `/compact` slash command (tier-1 lift from the OSS-CC research sweep — first to ship after the survey landed): player-triggered transcript compaction inspired by the universal `/compact` primitive in ClawCode / Cline / OpenCode. Mechanism: new `compact_memory(context_id, agent_name)` public wrapper around the existing `_manage_memory` (which already auto-summarizes once a per-agent message history exceeds `WORKING_MEMORY_LIMIT`); the wrapper passes `force=True` to bypass the threshold so even short conversations can be consolidated on demand. New `list_agents_with_history(context_id)` memory primitive lets the CLI handler discover which agents have buckets to compact without hard-coding the roster. CLI handler iterates them, totals folded turns, emits a Mneme comms-window narrating the action (`"I tucked N turns into long-term memory — agent (count), …"`) per M10 speech-vs-action convention. 7 new unit tests across `test_memory.py::TestListAgentsWithHistory` (4), `test_llm.py::TestManageMemory` (3 new — force-bypass, too-few-messages no-op, compact_memory wrapper), `test_cli.py::TestCompactSessionMemory` (3). All 90 tests across the affected files pass. Pairs with M4 caching: compacted prompts re-cache on the next call
- 2026-04-26 — Git context discovery for specialist agents in worktree (Round 6 bullet 5 of 5 — **all 5 Round 6 bullets closed**): both Round 6 runs showed `🔍 $ git status --short` then `🔍 exit 128` from Metis and Techne early in their flow because the agent containers' default cwd (`/app`) isn't the worktree. The `[project_root: ...]` tag was already in the user message; the executors just weren't threading it through to the git-context helpers. Cleaner than the ROADMAP's original "auto-prepend `cd && `" suggestion: just thread `parse_project_root(user_input)` through to `get_git_context(cwd=...)` (Techne) and `get_project_context(project_root=...)` (Metis). 2 new regression-guard tests in `tests/unit/test_executors.py::TestTechneExecutor::test_get_git_context_called_with_project_root_cwd` and `tests/unit/test_executors.py::TestMetisExecutor::test_get_project_context_called_with_project_root` lock in the fix. All 5 Round 6 M6-future bullets from AJ's live smoke now resolved in a 5-PR run (#34, #35, #36, this PR, plus the `/project delete` confirmation guard from the same session)
- 2026-04-26 — WSL audio noise suppression (Round 6 bullet 4 of 5): the existing `kourai_common.audio_env.configure_sdl_audio_driver()` was defined but never called anywhere in the codebase, so AJ's WSL2 launches fell through to SDL's default ALSA backend and produced `cannot find card '0'` chatter on every CLI/GUI startup. Wired the helper into `kourai_common.audio` at module load (runs BEFORE `import pygame` so SDL picks up the env var on first init). On WSLg with `PULSE_SERVER` and libpulse installed → selects `pulseaudio` (verified live: `SDL_AUDIODRIVER=pulseaudio` after `from kourai_common import audio`). Headless Linux (CI) → `dummy`. Player-set `SDL_AUDIODRIVER` always wins. New regression-guard test `test_audio_module_import_triggers_sdl_configure` ensures a future refactor doesn't silently un-wire the helper again. 4 pre-existing audio_env tests still pass. 1 Round 6 bullet still open (git context discovery)
- 2026-04-26 — CLI greeting attribution (3rd of 5 Round 6 M6-future bullets): startup line was rendering `( ◡‿◡)✧ Structure IS beauty.` — kaomoji + italic quote, no maiden name, players had to memorize the emoji-to-name map. Extracted `_format_greeting(name, face, quote)` helper in `hosts/cli/__main__.py` that prepends the capitalized maiden name in `_GOLD_BOLD` and wraps the quote in `"..."` so M10's italic-on-quoted-line speech convention reads naturally. Now renders `Metis ( ◡‿◡)✧ "Structure IS beauty."`. 5 new unit tests in `tests/unit/test_cli.py::TestGreetingFormat` (name-included, face-included, quote-wrapped, lowercase-input-capitalized, name-precedes-face reading order). 2 Round 6 bullets still open (WSL audio, git context discovery)
- 2026-04-26 — Round 6 bug cleanup (2 of 5 M6-future bullets): (1) `read_file` rejects directory paths — schema description tightened to call out "regular file path, not a directory", `read_file` handler adds an `is_file()` guard with a clear error pointing at "more specific path or list contents yourself"; (2) `forge_session._sanitize_branch_slug` replaces the old `replace(" ", "-")` one-liner with a `[a-z0-9-]` whitelist that handles backticks (the exact Round 6 case `please-add-a-function-\`d`), quotes, shell-meta, control chars, and unicode in one pass — collapses hyphen runs, strips edges, truncates without trailing hyphen, falls back to `"session"` on empty input. 14 new tests across `test_forge_tools.py::TestReadFile` (2) and `test_forge_session.py::TestSanitizeBranchSlug` (9), one of which is a property-style "every output char is in [a-z0-9-]" check across 6 weird inputs. 3 other Round 6 bullets still open (greeting attribution, WSL audio, git context discovery)
- 2026-04-26 — M9 shipped: `MODELS_SMART["metis"]` bumped from `anthropic/claude-opus-4-6` to `anthropic/claude-opus-4-7`. One-line config change; pricing was already in `ANTHROPIC_PRICING` for both at $5/$25, cache thresholds identical (4096 tokens minimum), Round 6 smoke at session start validated Metis's planning loop on 4.6 so the bump inherits that validation. No prompt change, no caching re-tune. New regression-guard test `test_metis_smart_tier_is_opus_4_7` so a future accidental rollback names itself in the failure message
- 2026-04-26 — `tier` kwarg symmetry on `chat_stream` + `chat_with_tools` (additive completion of PR #30): both now accept the same `tier: str | None = None` kwarg `chat()` already had, forwarding to `get_model(agent_name, tier=tier)`. Pure additive — no callers updated, default `None` preserves env-driven `KOURAI_MODEL_TIER`. Future callers (e.g., a cheap-tier lint-fix loop for Kallos, a low-stakes test-generation call for Dokimasia) can pin without llm.py plumbing. 4 new unit tests in `TestChatTierKwarg`, each with its backward-compat regression-guard pair
- 2026-04-26 — `/usage` per-(agent, model) keying shipped (caveat-fix from yesterday's tier-override PR): `SessionUsage.agents` switched from `dict[str, AgentUsage]` to `dict[tuple[str, str], AgentUsage]`. Removes the "first model wins per agent" masking that was hiding M14's cheap-tier discussion behind the smart-tier spec model. CLI `/usage` table grew a `tier` column (`haiku-4-5` / `sonnet-4-6` / `opus-4-7` short labels via `_short_model_label`) so multi-model agents render as two rows under the same agent name. 7 new unit tests across `TestRecordUsage` (1 — per-(agent, model) keying), `TestUsageSlashCommand` (1 — multi-model rendering with two costs + summed total), and `TestShortModelLabel` (5 — short-label edge cases). Full file 38 passed in 0.56s
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
