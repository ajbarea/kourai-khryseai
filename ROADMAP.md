# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-04-23 (M1 code shipped, awaiting Round 6 live smoke; cross-cutting agent/MCP/A2A polish landed — see Shipped)

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

## M1 — Tool-use migration (Techne · Dokimasia · Kallos)

> Status: **code shipped, awaiting live smoke** · Tracking: [IMPL.md](./IMPL.md)

Replace the `ACTION: CREATE/EDIT/DELETE` text-block convention plus the
`parse_and_apply_fixes` regex with **provider tool-use** (Anthropic tool-use
API, routed through LiteLLM's `tools=` parameter so non-Anthropic providers
keep working).

**Why.** The current parser silently accepts zero matches when the LLM wraps
headers in markdown bold. Once Techne reports "completed", Dokimasia runs on
whatever was on disk before — a green build with no actual changes. Tool-use
eliminates the entire class: the model literally cannot finish without emitting
a schema-validated `tool_use` block.

**Scope.**

- New `chat_with_tools()` in `shared/src/kourai_common/llm.py` driving the
  agentic loop until `stop_reason != "tool_use"`.
- Forge-tool registry in `shared/src/kourai_common/forge_tools.py`:
  `write_file`, `edit_file`, `delete_file`, `read_file` — each defined once
  with a JSON Schema and a callable that delegates to existing helpers
  (path validation kept).
- Migrate Techne, Dokimasia (test-write paths), Kallos (lint-fix paths).
- Retire `parse_and_apply_fixes` and its tests once the last caller is gone.

**Done when.**

- Smoke run produces non-empty `tool_use` blocks logged at debug. *(pending —
  Round 6 in [SMOKE_TODO.md](./SMOKE_TODO.md))*
- `grep -r parse_and_apply_fixes` returns zero hits in source. *(✅ 2026-04-20)*
- New unit tests cover the tool loop with mocked LiteLLM responses. *(✅
  2026-04-20 — 2322 unit tests passing, including 9 for `chat_with_tools`,
  20 for `forge_tools`, and refreshed Techne / Kallos / Dokimasia coverage)*

Reference: [Anthropic tool-use overview](https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview).

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

## M3 — A2A streaming task events

> Status: planned

Hephaestus already orchestrates specialists via the `a2a-sdk` (0.3.26 in the
lockfile). What's missing is per-stage UX. Today the CLI prints
`[2/4] Techne — Coder completed` *after* Techne finishes. With A2A's
`TaskStatusUpdateEvent` stream we can show `Techne: writing src/hello.py …`
in real time.

**Scope.**

- Specialists return a `Task` from `message/stream` and emit
  `TaskStatusUpdateEvent` from inside the tool loop (one event per tool call).
- Hephaestus subscribes via SSE (`Content-Type: text/event-stream`) and
  forwards events to the CLI through existing `a2a_events` helpers.
- CLI renders a live-updating line per active stage instead of a static
  "[N/4] completed" after the fact.

**Why.** Pipeline latency is the biggest UX threat (~7-8 min per session).
We can't make the model faster; we can make the wait *legible*.

Terminal states the CLI must handle: `COMPLETED`, `FAILED`, `CANCELED`,
`REJECTED`, `INPUT_REQUIRED`.

Reference: [A2A streaming & async](https://a2a-protocol.org/latest/topics/streaming-and-async/).

---

## M4 — Prompt caching on agent system prompts

> Status: planned · Cheap polish · Can land alongside any M

Agent system prompts (Techne, Kallos, Hephaestus) are 1-3 KB each and re-sent
verbatim every call. Marking a `cache_control: {"type": "ephemeral"}`
breakpoint at the end of the system block cuts that cost by ~10× on cache hits.

**Scope.**

- Pass `cache_control` block in system messages from `llm.py`.
- Verify via `usage.cache_read_input_tokens` on the second call within 5 min.
- Consider 1-hour TTL (`{"type": "ephemeral", "ttl": "1h"}`) for stable
  prompts that survive long idle windows; the 2× write cost amortizes.

**Threshold note.** Min cacheable tokens (April 2026): Opus 4.7 / 4.6 / 4.5 = 4096,
Sonnet 4.6 = 2048. Techne's system prompt sits ~3500 tokens — caches on Sonnet,
not yet on Opus. M1 has now stripped the format-instruction block (2026-04-20),
so to land caching on Opus we need to bundle `get_enriched_system_prompt`'s
persona enrichment into the cached prefix to cross the threshold. Kallos is
similarly trimmed and will need the same treatment.

Reference: [Anthropic prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching).

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

> Status: planned · Cheap-once-SDK-is-stable

`a2a-sdk` shipped 1.0.1 in March 2026 with a stable v1.0 on
[a2a-protocol.org](https://a2a-protocol.org/latest/announcing-1.0/) targeted
for May-June 2026. Pyproject pins already permit `a2a-sdk<2.0` (2026-04-23),
so `uv lock` will auto-adopt 1.0.x when resolution prefers it.

**Scope.**

- When `uv lock` starts pulling 1.0.x, walk the ``_is_file_part`` /
  ``_get_file_bytes`` firewall in ``shared/src/kourai_common/a2a_utils.py``
  (already dual-shaped as of 2026-04-23 for forward compat).
- Verify unified Part roundtrip in ``remote_connections.py:send()`` —
  ``TextPart``/``FilePart``/``DataPart`` unify into member-discriminated
  ``Part`` in v1.0 (``"text" in part``, ``"url" in part``).
- ``mimeType`` → ``mediaType`` field rename on file parts.
- AgentCards are backward-compatible so specialists keep running
  mid-migration; no coordinated re-deploy needed.

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
and cache thresholds are confirmed equivalent (see M4 — Opus 4.7 caches at
4096 tokens, same as 4.6).

No metric-based rollout is needed for a Claude-family minor: behaviour is a
super-set. Gate the bump on a Round 6 smoke that exercises Metis's planning
loop and verifies the JSON-schema specs still come out clean.

---

## M10 — Speech-vs-action rendering convention

> Status: planned · Blocked by: nothing (can start anytime)

Apply the "agents speak, don't emit" guiding principle across all three
hosts. Today the convention is splintered: the VN auto-quotes every line
via `Character(..., what_prefix='"', what_suffix='"')`, the CLI has a
half-implemented version (only Hephaestus's handoff narration is quoted —
see `hosts/cli/onboarding.py:209` and the README transcript), and the GUI
renders everything plain. Result: Metis asking a question looks visually
identical to Metis reporting test results, flattening her as a character.

**Why.** The maidens are the product. Portraits, voices, affinity tiers,
romance routes all signal *these are people you're collaborating with*.
But the terminal stream treats "One decision before I draft the spec."
the same as "found 3 models with datetime fields" — both unstyled, both
emoji-prefixed, both indistinguishable. Speech-marked dialogue reinforces
character presence AND makes clarifying questions pop against the
unstyled status stream — the human-on-the-loop checkpoint becomes
visually unmissable instead of scrolling past in the same typographic
colour as a lint warning.

**Scope.**

- Update agent system prompts (`agents/*/agent.py` SYSTEM_PROMPT blocks)
  to distinguish speech vs action in their output. One-line addition:
  *"When you address the player directly — greeting, question, commentary,
  explanation — wrap that line in double quotes. When you describe what
  you're doing (analyzing, running tests, listing findings), leave it
  unquoted."* Hephaestus's `HEPH_HANDOFFS` dict already uses quotes
  implicitly in the README sample — bring Metis, Techne, Dokimasia,
  Kallos, Mneme to the same bar.
- CLI rendering (`hosts/cli/events.py::_maidenify_status`,
  `hosts/cli/rendering.py::_comms_window`): when a rendered line starts
  with a double quote, auto-apply italic styling around it. Keeps the
  status/action lines plain and makes spoken lines read as dialogue.
- GUI dialogue rendering (`hosts/gui/queue_event_handler.py` +
  `hosts/gui/typewriter.py`): same italic-on-quoted pass, so speech
  visually differs from action in the dialogue history.
- VN: drop `what_prefix='"', what_suffix='"'` from the Character
  definitions in `hosts/vn/kourai_vn/game/script_data.rpy`. Let agent
  output decide per-line whether a line is quoted, matching the CLI/GUI
  convention instead of blanket-quoting status reports.
- README transcript and getting-started examples (`README.md`, `docs/cli.md`):
  re-render sample output under the new convention so documentation
  matches shipped behaviour.

**Done when.**

- Every core-specialist agent prompt includes the speech-vs-action
  instruction, with unit tests asserting the instruction is present.
- An end-to-end smoke run shows a clarifying question (e.g. Metis:
  `"Should CSV export stream chunked I/O for large files?"`) rendered
  visually distinct from an analysis line in all three hosts.
- `grep -n 'what_prefix' hosts/vn/kourai_vn/game/*.rpy` returns zero
  hits; the VN takes quoting from agent output.
- README sample + `docs/cli.md` transcripts match what the CLI actually
  produces on a fresh run.

Reference: poster work on 2026-04-23 surfaced the inconsistency;
see `hosts/cli/demo.py` for the target convention applied to a
scripted pipeline.

---

## M11 — GUI attachment send path

> Status: planned · Blocked by: nothing

The CLI has full image-attachment support through the A2A stream:
`hosts/cli/commands.py::_capture_image` grabs clipboard pixels via
`PIL.ImageGrab`, base64-encodes them, and stacks them onto `pending_images`;
`hosts/cli/streaming.py::send_and_stream` then builds a multi-part `Message`
(`TextPart` + `FilePart(FileWithBytes(...))`) so Hephaestus actually sees
the image on the other side.

The **GUI is asymmetric** — after the 2026-04-23 shortcut pass, Alt+V
captures clipboard images into `PygameEventDispatcher._pending_images`
and a `[📎 image #N queued]` placeholder shows up in the input bar. But
`_submit_text` still puts bare `(target, text)` tuples on `send_q`, so
the captured image never reaches `GuiClient` and is silently discarded
when the pipeline completes.

**Why.** Multi-modal work (screenshot → "describe this UI bug", design
mockup → "refactor components to match") is one of the most asked-for
agent patterns. The CLI proves the wire format works; the GUI just
needs to match so the entire demo/poster/UX tier isn't second-class.

**Scope.**

- Extend `send_q` message shape from `(target, text)` to
  `(target, text, attachments)` (attachments: `list[(b64, mime)]`).
  Update every `send_q.put()` call site in `pygame_event_handler.py`
  and `__main__.py` to pass `[]` for the new slot by default.
- `_submit_text` drains `self._pending_images` when submitting and
  includes them in the send payload. Reset the list after submission
  so one image doesn't duplicate across turns.
- `GuiClient.run()` consumes the richer tuple and builds `FilePart`
  entries the same way `send_and_stream` does in the CLI — same
  `FileWithBytes` + `Part` dance, routed through `_send_with_retry`.
- Update the dialogue history to show attached images inline when the
  user submits (image thumbnail next to their `DialogueEntry`), so the
  player can visually confirm what was sent.
- `DemoGuiClient` — picks up attachments for parity but silently
  discards them (demo mode doesn't round-trip to a real agent).

**Done when.**

- Alt+V → type a prompt → Enter → pygame log shows A2A message with
  `parts=[TextPart, FilePart]` and Hephaestus receives both.
- End-to-end: screenshot a code panel, Alt+V in the GUI, "fix the
  off-by-one in this function" — Techne edits the correct file.
- `grep send_q.put hosts/gui/ | grep -v "(.*, .*, "` returns zero hits
  (every producer passes the attachments slot).

Reference: CLI implementation at `hosts/cli/commands.py:481-505`
(`_capture_image` + `pending_images`) and `hosts/cli/streaming.py:79-93`
(multi-part message assembly).

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

## M6 — Future / unprioritized

- **MCP Tasks primitive (experimental):** when stable, replace our hand-rolled
  `forge_sessions` SQLite table with MCP Tasks for durable execution.
- **A2A `INPUT_REQUIRED` handling:** wire it through Hephaestus → CLI so a
  specialist mid-pipeline can ask the player a question instead of failing.
- **Strict tool use** (`strict: true` on tool defs): once M1 lands, turn it
  on for forge tools to guarantee schema conformance.
- **Anthropic Agent SDK:** evaluate when it stabilises; could replace some
  REPL plumbing in `hosts/cli/__main__.py`.
- **Sandbox container UID alignment** (M5 implementation choice).
- **`/usage` CLI command:** surface running token + dollar cost for the
  current REPL session so long pipelines don't turn into a billing surprise.
  Read from the provider response's `usage` block (input/output/cache tokens)
  and multiply by per-tier price constants; `/model_tier` already knows
  which tier is active. Per-session running total + a break-down per agent
  (Hephaestus vs Techne vs Kallos etc.) would let players see where the
  spend is going.
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
- **Agent-level README.md per `agents/*`:** today a contributor reading
  `agents/metis/pyproject.toml` learns nothing about what metis actually
  does, because each agent's `pyproject.toml` is a 10-line stub that
  just imports `kourai-common`. A one-page README per agent covering
  responsibility, inputs, outputs, and co-agents it routes through would
  be a real onboarding win. Template first (kallos, since its scope is
  tightest), then propagate.
- **Property-tested agent-coordination invariants:** `hypothesis` is in
  dev deps but unused. Agent systems have invariants that are hard to
  specify and easy to lose: every `HandoffMessage` round-trips through
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
