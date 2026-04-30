# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-04-29 (M17 Phase 2 fully shipped — `/preferences` CRUD CLI + project_id stability fix (#93), confidence decay (#94); 2026-04-29 live smoke against `make up` uncovered an architectural overhaul that supersedes "between milestones" UX/DX work: **M13 CONFIRM_ORDER prompt-loss regression** — Hephaestus drops the original development request when relaying to a specialist after the player's confirmation, so Metis received only `"light it"` / `"y"` as her spec body; pipeline cascaded on garbage and reported `✨ Forged in 333.6s` / `commit_count: 0` with no soft-fail signal across two end-to-end runs (sessions `bd1e413a` and `0dbafe91`); /yolo verified to only tag messages with `[yolo: on]` rather than bypass the gate, so the regression is independent of the yolo path. Beyond M13, the smoke surfaced 23+ findings clustering around two architectural gaps: unstructured streaming (every text update parsed as either narrow status box or wide artifact render with no metadata to distinguish dialogue, status, code, or spec — manifests as truncation, FACT-tag leakage, TTS reading 905-char Mneme dialogue including markdown asterisks aloud, TTS gating turning 60-90s of pipeline work into 333s of wall-clock) and audio playback architecture (pygame.mixer documented as not reliably resampling, so 24kHz mono Kokoro output through 44.1kHz stereo mixer renders as ~3.7× speed "VHS rewind" — BytesIO header-parsing patch verified ineffective by AJ; pygame buffer 512→2048 bumped to fix WSL2+LLM-load underrun crackling, verified gone). New milestones M18 (structured streaming with content-kind metadata in `Message.metadata`, builds on M7) and M19 (audio backend separation for TTS via miniaudio or sounddevice, independent of M7/M18) added below. M7 status elevated to critical-path: no longer "deferred until M17 Phase 1 has miles" — it's the foundation for M13 fix AND M18. Quick wins shipped in working tree without architectural commitment: `[HH:MM:SS]` dim prefix in every comms-window header for per-step timing visibility (`hosts/cli/rendering.py`), full TTS text logged at INFO via `text=%r` in `hosts/gui/tts_engine.py`, pygame buffer bump documented in `shared/src/kourai_common/audio.py` with the WSL2-trade-off comment so future PRs don't shrink it back. New memory `feedback_no_workarounds.md` captures the pre-release perfection stance: "April-2026 best practice no matter the cost; never frame as 'cheapest fix'; web-search before any implementation proposal." All the rest from the 2026-04-27 reviewed line still applies — see Shipped, revised M2/M7, and the M6 "Surfaced from external research" subsection)

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

## M7 — A2A v1.0 migration

> Status: **critical-path** (elevated 2026-04-29) · Bigger-than-the-firewall-
> claimed (see 2026-04-26 finding) · Pyproject pinned to `<1.0` until M7
> lands properly · **Foundation for M13 regression fix and M18 structured
> streaming**

The 2026-04-29 live smoke proved that bracket-tag workarounds
(`[project_id: ...]`, `[yolo: on]`) cannot reliably propagate
load-bearing context across A2A boundaries. Hephaestus's CONFIRM_ORDER
resume handoff dropped the original development request when relaying
to Metis (M13 regression — Metis received only `"light it"` as her
spec body). The right fix is not another text-tag patch; it's
`Message.metadata` on the v1.0 wire. The original deferral ("until
M17 Phase 1 has miles") is superseded by AJ's pre-release perfection
stance — Phase 1 shipped, the bracket-tag pattern is actively
breaking, and M18 (below) cannot land cleanly without v1.0's metadata
channel.

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

**Six-phase execution plan.** Each phase is a separate landable commit
on `main`; CI must stay green between commits and live `make up` smoke
(driven via tmux + `docker logs`, not human paste) is required after
Phase 3 (pin flip) and again after Phase 6 (cleanup). Phases 1-2 stay
on `a2a-sdk<1.0`; Phase 3 is the big-bang pin flip; Phases 4-6 land on
top of 1.0. The shared `kourai_common.messaging` and
`kourai_common.agent_cards` helpers absorb the wire-format switch so
the per-call-site diff in Phase 3 collapses to roughly the helpers
themselves rather than every executor.

1. **Phase 1 — Centralize Part / Message construction (still on 0.3).**
   Add `kourai_common.messaging.text_part(text)`,
   `file_part_from_bytes(b64, media_type, filename=None)`,
   `data_part(data)`, and `user_message(text, role=...)` helpers that
   emit the 0.3 shape today. Convert every `Part(root=TextPart(...))`,
   `Part(root=FilePart(file=FileWithBytes(...)))`, and
   `Message(role=..., parts=[...], kind=...)` call site across
   `agents/`, `hosts/`, `shared/`, `tests/` to call the helpers. New
   helpers gain dedicated unit tests; existing tests stay green
   without modification. **Done when:** ripgrep finds zero
   `Part(root=` outside `messaging.py` and `make validate` is green.

2. **Phase 2 — Centralize server build + Part inspection (still on
   0.3).** Add `kourai_common.server.build_a2a_app(card, executor,
   task_store)` that wraps `A2AStarletteApplication` (today) — every
   agent's `__main__.py` calls the helper instead of constructing
   directly, collapsing ~10 near-identical boilerplate copies. Move
   `_is_file_part` / `_get_file_bytes` from `a2a_utils.py` into
   `messaging.py` as `is_file_part(part)` and `get_file_bytes(part)
   -> (b64, media_type)`, dropping the speculative forward-compat
   hatches (they predicted the wrong v1.0 shape per the 2026-04-29
   discovery). AgentCard build already centralized in
   `agent_cards.build_card()` from M7 prep work. **Done when:** every
   agent `__main__.py` is one builder call, `a2a_utils.py` has no
   firewall code, `make validate` green.

3. **Phase 3 — Pin flip + helper-implementation flip (the big bang).**
   Bump pin to `>=1.0,<2.0` in `shared/pyproject.toml`,
   `hosts/cli/pyproject.toml`, `hosts/gui/pyproject.toml`. Flip
   helper implementations: `text_part(text)` → `Part(text=text)`,
   `file_part_from_bytes(...)` → `Part(raw=..., media_type=...,
   filename=...)`, `user_message(...)` → `new_text_message(text,
   role=Role.ROLE_USER)`. Flip `agent_cards.build_card()` to
   `supported_interfaces=[AgentInterface(url=..., protocol_binding=
   "JSONRPC", protocol_version="1.0"), AgentInterface(url=...,
   protocol_binding="JSONRPC", protocol_version="0.3")]` — the v0.3
   fallback is the transitional safety net for clients that haven't
   migrated in Phase 4 yet. Flip `kourai_common.server.build_a2a_app`
   to `create_agent_card_routes` + `create_jsonrpc_routes(...,
   enable_v0_3_compat=True)`. Update `messaging.send_*_status` to
   `new_text_status_update_event` + `TaskState.TASK_STATE_*`. Add
   `agent_card=card` to every `DefaultRequestHandler(...)` (now
   required). Bump `A2A_PROTOCOL_VERSION` in `a2a_utils.py` to
   `"1.0"`. **Done when:** `make validate` green; live `make up`
   smoke shows a `/yolo` fizzbuzz request flowing through the forge
   (server speaks 1.0, clients still speak 0.3 via the compat flag).

4. **Phase 4 — Client-side migration.** Migrate
   `agents/hephaestus/remote_connections.py` (Hephaestus's
   load-bearing client to every specialist) from
   `ClientFactory.create_client()` (sync) to `await
   create_client(url_or_card)`. Migrate `hosts/cli/{__main__,events,
   headless,streaming}.py`, `hosts/gui/client.py`, `agents/vn_bridge.py`
   — same flip. Streaming consumption: `AsyncIterator[ClientEvent
   | Message]` → `AsyncIterator[StreamResponse]` with
   `chunk.HasField('artifact_update' | 'status_update' | 'task' |
   'message')`. Sweep enums: `TaskState.working` →
   `TaskState.TASK_STATE_WORKING`, `Role.user` → `Role.ROLE_USER`
   everywhere; drop `Message(kind=...)`. Update mocks in
   `tests/unit/test_remote_connections.py`, `test_cli.py`,
   `test_gui_attachment_send_path.py`. **Done when:** every client
   speaks 1.0 natively and `make up` smoke is clean without
   exercising the compat flag.

5. **Phase 5 — text-tags → Message.metadata.** Replace
   `[project_root: ...]`, `[yolo: on]`, `[auto_approve_reads: on]`,
   `[relationship_tiers: ...]`, `[project_id: ...]` text-prefix
   construction in `hosts/cli/__main__.py` (and any other call sites)
   with structured `Message.metadata = {"project_root": ...,
   "yolo": ..., ...}` on the outbound Message. Replace
   `parse_project_root()` regex in `kourai_common.a2a_utils` with
   `message.metadata.get("project_root")`. Replace text-tag readers
   in `agents/hephaestus/agent.py`. Drop the `_PROJECT_ROOT_PATTERNS`
   regex and the prepend/strip logic in `hosts/cli/streaming.py`.
   Update `synthesise_fact_from_pause` callers to read `project_id`
   from metadata. Update tests. **Done when:** `grep -rnE
   '\[project_root:|\[yolo:|\[auto_approve_reads:|\[relationship_tiers:|\[project_id:' --include='*.py'`
   returns zero construction sites; readers all pull from
   `metadata`. Unblocks the M13 fix (which uses
   `Message.metadata.original_request` for the resume dispatch).

6. **Phase 6 — Drop compat flag + retire forward-compat hatches.**
   Remove `enable_v0_3_compat=True` from
   `kourai_common.server.build_a2a_app`. Remove the v0.3 fallback
   `AgentInterface` from `agent_cards.build_card()`. Update
   doc-comments in `a2a_utils.py` and `a2a_events.py` — the
   dual-shape firewall is gone. Audit test mocks for 0.3-shape
   leftovers (`tests/unit/test_a2a_utils.py`, `test_executors.py`,
   `test_metis_*.py`, `test_remote_connections.py`,
   `test_gui_attachment_send_path.py`). **Done when:** `make
   validate` green; live `make up` end-to-end smoke shows the
   fizzbuzz pipeline with M17 PAUSE-on-coverage_target running to
   completion; v0.3 SDK imports absent from `uv.lock`.

**Phase status.** Plan drafted 2026-04-29. Phase 1 shipped 2026-04-29
(`kourai_common.messaging` now exposes `text_part` / `file_part_from_b64`
/ `data_part` / `user_message`; every executor + host call site uses
the helpers; 8 new unit tests). Phase 2 shipped 2026-04-29
(`kourai_common.server.build_a2a_app` collapses 10 agent
`__main__` boilerplate copies; `is_file_part` / `get_file_bytes`
moved into `messaging`; `a2a_utils.py` is firewall-free; 6 new unit
tests; 2852 tests pass green). Phase 3 shipped 2026-04-29
(pin bumped to `>=1.0,<2.0` across `shared/`, `hosts/cli/`,
`hosts/gui/` pyproject.toml; messaging helpers flipped to
`Part(text=)` / `Part(raw=, media_type=, filename=)` /
`Part(data=ParseDict(...))`; `agent_cards.build_card` uses
`supported_interfaces` with v0.3 fallback; `server.build_a2a_app`
uses `create_agent_card_routes` + `create_jsonrpc_routes` with
`enable_v0_3_compat=True`; clients flipped from
`ClientFactory.connect` to `await create_client`; enums swept to
`TaskState.TASK_STATE_*` / `Role.ROLE_USER`; `ServerError` wrappers
dropped — `raise UnsupportedOperationError()` directly; 2853 tests
pass green). Phase 4 was absorbed into Phase 3 because the Python
API change forced both server and client migrations together —
``ClientFactory.connect`` is gone and the streaming consumption no
longer wraps Parts in ``.root``. Phase 5 shipped 2026-04-30 (every
text-tag construction site replaced by ``Message.metadata`` keys;
``determine_pipeline`` / ``execute_pipeline`` / ``_iter_agent_events``
/ ``RemoteAgentConnection.send`` / ``send_and_stream`` all take a
``metadata`` kwarg and propagate it across input_required follow-ups;
Hephaestus's four ``extract_*_tag`` regex extractors deleted; new
``a2a_utils.get_message_metadata`` and ``project_root_from_context``
helpers replace ``parse_project_root``; ``A2A_PROTOCOL_VERSION``
header bumped to ``"1.0"``; 2833 tests pass green). Phase 6 shipped
2026-04-30 (``enable_v0_3_compat=True`` removed from
``server.build_a2a_app``; transitional v0.3 ``AgentInterface``
fallback removed from ``agent_cards.build_card`` and
``agents_manifest.fallback_card_for``; 2833 tests still green; lint
clean). M7 fully shipped.

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

## M17 — HOTL answer persistence (project-scoped facts)

> Status: **Phase 1 shipped (2026-04-29)** · Phase 2 planned · Builds
> on: M13 (CONFIRM_ORDER) · Memoir foundation · `kourai_common.facts`
> knowledge graph · Distinct from M6 autoDream

When Metis pauses on a clarifying question — *"what's your test coverage
target?"*, *"does this project use type hints?"*, *"preferred logging
backend?"* — the player's answer sticks. Phase 1 closes the loop between
`AgentInputRequired` and the `kourai_common.facts` knowledge graph: a
project-scope axis + a `PAUSE: <kind> "<question>"` runtime control token
+ cross-turn stash + write-on-resolve in the CLI streaming layer + Metis-
side recall via `build_fact_context`. Per the Phase 1 DOD, a HOTL answer
in project A is recalled in project A's next session and NOT recalled
when the player switches to project B.

### Why `facts.py` and not `player_memories` (architecture pivot from initial draft)

Initial scoping assumed M17's write path would extend the `player_memories`
SQLite table used by the gossip / affinity / personality stack. A code
audit revealed `kourai_common.facts` already had the right shape:
`<FACT category="preference" confidence="high">…</FACT>` extraction,
`PlayerFact` / `KnowledgeGraphFact` dataclasses, `store_facts()` writes,
`get_relevant_facts_for_enrichment()` reads, `build_fact_context()` prompt
injection — full lifecycle. Adding a `project_id` axis was materially
cheaper than building a parallel project-preference layer on top of
`player_memories`, and it inherited the existing knowledge-graph
machinery (relationships, confidence decay, prompt enrichment) for free.

### Anchors in current 2026 best practice

[Mem0](https://github.com/mem0ai/mem0) and Letta (the production
evolution of MemGPT) have converged on a four-scope memory model:
`user_id` × `agent_id` × `session_id` × **`project_id`-as-metadata**,
with metadata-filtered retrieval at lookup time. Mem0 v1.0.3 (Jan 2026)
formalised project-level configuration — inclusion / exclusion prompts,
custom categories, targeted searches scoped by project metadata. M17
adopts the *project_id-as-metadata-attribute* pattern (rather than the
original draft's `project_root`-as-column), aligning with the industry
direction without taking on the full mem0 / Letta stack as a dependency.
Reference points worth tracking — the right framing is "use the
convergent vocabulary so a future migration to mem0 / Letta is
incremental rather than a rewrite."

### Phase 1 — what shipped (2026-04-29)

Six PRs across one session. The mechanism end-to-end:

1. `derive_project_id(project_root)` — stable sha256-of-canonical-path
   id (16 hex). Survives the player moving the repo on disk, doesn't
   leak host-absolute paths into fact bodies. (#81)
2. `project_id` axis on `PlayerFact` / `KnowledgeGraphFact` /
   `player_memories` SQLite. `<FACT>` regex parses the attribute;
   `add_player_memory` and `store_facts` persist it. (#82)
3. `synthesise_fact_from_pause(player_id, project_id, preference_kind,
   player_response, source_agent)` helper + Phase 1 property test. (#84)
4. Read-side filter on `get_player_memories(project_id=...)` and
   `build_fact_context(project_id=...)` — single-query SQL with a
   `CASE WHEN project_id = ? THEN 1 ELSE 0 END DESC` ranking boost so
   project-tagged facts beat global at equal importance / recency. (#85)
5. Metis `PAUSE: <kind> "<question>"` runtime token mirroring
   M13's CONFIRM_ORDER shape, with the closed Phase 1 vocabulary
   `coverage_target` / `python_version` / `style_rules` /
   `commit_style` / `test_framework`. New `kourai_common.pause_state`
   + `kourai_common.pause_tag` modules; CLI streaming layer pops the
   stash and calls `synthesise_fact_from_pause` at the top of every
   turn. (#86)
6. Metis-side recall — `create_spec` / `create_spec_stream` thread
   `player_id` / `project_id` to `build_fact_context`; PLAYER CONTEXT
   leads the user-message context block so Metis sees prior PAUSE-
   resolved preferences before docs / project / file context. (#87)

Three calls that diverged from the original sketch:

- **`run_post_task_hooks` had no production call sites.** The ROADMAP
  plan ("wired into `run_post_task_hooks`…") was load-bearing on a
  layer never integrated into the agent execution pipeline. The
  pragmatic answer: call `synthesise_fact_from_pause` directly from
  `hosts/cli/streaming.py` where Memoir already lives. Promoting the
  call back into a unified post-task hook layer is queued as a
  follow-on under M5/M6.
- **Metis didn't actually call `build_fact_context`.** ROADMAP §M17
  assumed every specialist's prompt was enriched through `facts.py`
  (true for Puck and Cupid). Metis went through
  `get_enriched_system_prompt` → `build_player_context` →
  `retrieve_relevant_memories`, which never touches facts.py. PR #87
  closed the gap surgically. Other specialists (Techne / Kallos /
  Dokimasia / Hephaestus) inherit the same disconnect; sibling work
  when a non-Metis PAUSE caller surfaces.
- **Cross-turn state lives in-process.** A
  `kourai_common.pause_state` dict keyed by `context_id` carries
  `(preference_kind, source_agent)` from pause to resume. Restart
  drops the classification; the answer still lands in Memoir as
  labeled FL training data so the loop fails soft. Cross-process
  persistence belongs in Phase 2's confidence-decay milestone.

### Phase 2 — fully shipped 2026-04-29

All four items landed in one session. M17 closed end-to-end: HOTL
write path, project-scoped recall, visible narrator, telemetry span
attributes, CRUD CLI with right-to-forget, and lazy confidence decay
on a 90-day window.

- **Visible recall (player UX) — shipped 2026-04-29.** Metis's
  executor calls `_format_recall_narration(player_id, project_id)`
  before streaming the spec. When project-scoped preference facts
  exist for the active project (closed-vocab gate matches the
  PAUSE-write side), Metis emits `📐 Using your stored
  coverage_target (80%).` (one fact) or
  `📐 Using your stored project preferences: coverage_target
  (80%), python_version (3.13).` (many) as a `working_status`
  event, picked up by the existing `_maidenify_status` rendering on
  every host. Free-form `<FACT>` observations (skills, identity)
  don't pollute the status stream — only PAUSE-resolved
  preferences narrate. Closes the "silent recall feels like
  agents are guessing" trust gap that originally motivated this
  item.
- **`/preferences` CRUD CLI — shipped 2026-04-29.** Slash command
  modeled on `/permissions`, aliased as `/prefs`. Bare command
  lists every preference fact for the active scope (project +
  global), grouped with a `*` marker on project rows;
  `set <kind> <value>` upserts (forgets-then-writes the same
  scope+kind so the listing stays single-row-per-kind);
  `forget <kind>` removes; `forget --all` clears the whole active
  scope without touching global. The closed vocab is enforced on
  the write path (same `VALID_PREFERENCE_KINDS` gate as the PAUSE
  synthesiser); the forget path tolerates retired kinds so
  right-to-forget outlives vocab churn. Three new public primitives
  in `kourai_common.facts`: `list_preference_facts`,
  `forget_preference_fact`, `set_preference_fact`. Aligns with the
  GDPR/CCPA-aligned forgetting patterns Mem0 / Letta / Supermemory
  converged on for 2026.
- **Project_id stability fix — shipped 2026-04-29 (bundled with
  CRUD).** Phase 1's PAUSE-write path derived the fact axis from
  `[project_root: <forge_session.workdir>]`, but the REPL creates
  a uuid'd worktree per turn — `derive_project_id(workdir)` was
  unstable across sessions, so facts written in turn N never
  recalled in turn N+1. Fix: REPL now also emits
  `[project_id: <stable>]` from `derive_project_id(project.path)`,
  and `streaming.py:_project_id_from_forge_tags` prefers the
  explicit tag over deriving from project_root. Specialists keep
  reading `[project_root:]` for git ops on the worktree; only the
  fact synthesiser reads the new tag. Without this fix the
  `/preferences` listing would have shown empty for everyone.
- **Telemetry — shipped 2026-04-29.** Metis's outer `metis.execute`
  span now carries `kourai.fact.recalled` (`bool`, always set) and
  `kourai.fact.kinds` (`list[str]`, set only when there's something
  to share). Cross-pane linkage is automatic per M16's trace-ID
  injection — researchers grep Dozzle for `fact.recalled=true` and
  pivot into Jaeger via the trace ID stamped on every span-bound log
  line. The narrator and the span attributes derive from the same
  parsed list (`_recalled_preferences`) so the player view and the
  researcher view can never disagree about whether a recall fired.
- **Confidence decay — shipped 2026-04-29.** `PROJECT_FACT_DECAY_DAYS
  = 90` lives in `kourai_common.facts`. `_decayed_confidence` walks a
  4-rung ladder (`skip → low → medium → high`) and drops one rung per
  decay window of `created_at` age. `list_preference_facts` returns a
  `decayed_confidence` field alongside the original so /preferences
  can surface decay state without rewriting the stored row;
  `get_relevant_facts_for_enrichment` filters out preference facts
  that have decayed past the floor so Metis stops planning around an
  old answer. `last_accessed` deliberately does NOT reset the timer
  — passive recall during a session would otherwise hold a stale
  preference alive forever; only player-driven re-confirmation
  (`/preferences set` or PAUSE answer) writes a fresh
  `created_at`. `synthesise_fact_from_pause` now forget-then-writes
  (matching `set_preference_fact`) so re-PAUSE on the same scope+kind
  no longer stacks rows in `player_memories`.

### Live smoke 2026-04-29 — readout still blocked on M13

Two end-to-end runs (sessions `bd1e413a` and `0dbafe91`) intended to
exercise the M17 happy path — fizzbuzz prompt → Metis PAUSE on
`coverage_target` → player answer → narrator quotes the resolved
preference back → `fact.recalled=true` lands on the `metis.execute`
span via the M16 trace-ID-in-Dozzle pivot — **never reached the
PAUSE step.** Hephaestus drops the original prompt across the
CONFIRM_ORDER → resume → route handoff (M13 regression — see
ROADMAP §M7 elevation rationale and IMPL.md critical-path section).
Metis received only the player's confirmation token (`"light it"`,
`"y"`) as her spec body, generated questions-as-prose as her
response, declared `Spec complete`, and the rest of the pipeline
cascaded through Techne / Dokimasia / Kallos / Mneme on garbage —
333.6 seconds of wall-clock for zero output. /yolo verified to only
add the `[yolo: on]` text-tag rather than bypass the gate, so the
regression is independent of the yolo path and survives both routes.

**The M17 code path itself is correct.** 2876 unit tests pass; the
PAUSE token vocabulary, `synthesise_fact_from_pause` dedup, decay
ladder, recall narrator, telemetry attributes, `/preferences` CRUD
CLI, and project_id stability fix are all verified at the unit
level. The blocker is upstream — Metis simply needs to receive a
real planning prompt for any of M17 to fire end-to-end.

The smoke also surfaced an architectural cluster — comms-window
truncation, FACT-tag leakage, TTS reading 905-character Mneme
dialogue including markdown asterisks aloud, TTS gating turning
60-90s of work into 333s wall-clock — all sharing the same root
cause in unstructured streaming. **Captured as M18 below**, builds
on M7. Audio playback architecture (pygame.mixer documented as not
reliably resampling, so 24kHz mono Kokoro through 44.1kHz stereo
mixer plays as ~3.7× speed "VHS rewind") **captured as M19 below**,
independent of M7/M18.

Re-run plan once M7 + M13 fix lands: same fizzbuzz prompt against a
fresh `make up`, watch PAUSE on coverage_target, answer in next
turn, watch the `📐` recall narrator emit "Recalling that you set
coverage_target to …", verify `fact.recalled=true` on the span,
exercise `/preferences` browse + set + forget, restart REPL to
verify cross-session recall, manual SQL backdate of `created_at` to
verify decay tier transitions in the listing.

### Out of scope — defer to follow-on milestones

- *Memoir → facts batch synthesis.* autoDream territory below — the
  end-of-day sweep that consolidates transcripts into prose markers
  could ALSO scan recent Memoir entries for un-tagged-but-extractable
  preferences ("the player chose chunked I/O three times this week —
  promote to a project-scoped fact"). Keep that work in autoDream's
  scope.
- *Specialist parity for fact recall.* Metis now reads
  `build_fact_context` with project scope; Techne / Kallos /
  Dokimasia / Hephaestus do not. Sibling to PR #87 — same five-line
  pattern per agent. Defer until a real PAUSE caller in a non-Metis
  specialist surfaces.
- *Cross-project preference inference* (*"you usually use ruff at 88
  cols — apply to this new project?"*). Federation / sharing
  question; lives in M6 alongside the federated-forge work.
- *GUI / VN renderers for `/preferences`.* CLI-first per existing
  pattern; lifts in a separate milestone once the CLI surface
  stabilises.

### Honest external-artifact claim language

Defensible *now* that Phase 1 has landed:

> *"Kourai captures HOTL responses as project-scoped entries in the
> `kourai_common.facts` knowledge-graph layer. Project-scoped facts
> are injected into Metis's planning prompt, so she recalls the
> player's stated preferences (e.g. test-coverage target, Python
> version, style rules, commit-message convention, test framework)
> on subsequent sessions for the same project without re-asking, and
> stays scoped — preferences for project A are NOT surfaced when the
> player switches to project B. Scoping aligns with the four-scope
> memory model formalised by Mem0 / Letta in 2026."*

---

## M18 — Structured streaming with content-kind metadata

> Status: Phase 1 in flight on `feat/m18-content-kind-metadata`
> (contract + hephaestus pilot + host coexistence). Subsequent phases:
> per-specialist migration, SSML in dialogue bodies, `KIND_CODE` /
> `KIND_SPEC` distinct render paths. · Surfaced 2026-04-29 live
> smoke · Builds on M7 (depends on `Message.metadata` channel) ·
> Resolves clustered UX findings: comms-window truncation, FACT-tag
> leakage into status stream, TTS reading entire markdown bodies
> aloud, TTS-gated pipeline visual cadence

### Phase 1 — kind contract + hephaestus pilot (in flight)

`shared/src/kourai_common/messaging.py` ships the discriminator —
`KIND_DIALOGUE` / `KIND_STATUS` / `KIND_CODE` / `KIND_SPEC` constants,
a `ContentKind` Literal, `set_content_kind` / `get_content_kind` /
`kind_message`, and an optional `kind=` kwarg on every TaskUpdater
helper (`send_working_status`, `send_input_required`,
`send_completed`). The metadata key is the URI-namespaced extension
identifier `https://kourai.khryseai/ext/streaming/v1` — A2A 1.0 spec
form (top-level key is the extension URI, value is a nested object
with the extension's fields). Today the only field is `content_kind`;
sibling fields (priority, subkind, ssml_version) live under the same
URI without colliding with other extensions on the same Message.

Hephaestus migrates first as the pilot — `Analyzing request...` and
`Pipeline: foo -> bar` tag as `KIND_STATUS`; CONFIRM_ORDER read-back,
ASK_USER prompt, CHAT response, INPUT_REQUIRED forward, and the Metis
parallel-discussion emit tag as `KIND_DIALOGUE`. Forwarded specialist
statuses stay untagged so the legacy emoji-prefix path in
`_maidenify_status` still routes them; that branch retires when every
specialist opts in.

Host-side, `hosts/cli/streaming.py` reads kind off
`event.status.message` and gates TTS on the predicate
`kind is None or kind == KIND_DIALOGUE`. Untagged emissions (legacy)
keep the v0.x always-speak behavior; status / code / spec render
visually only and don't gate the next event on narration completion.

### Why

The 2026-04-29 smoke surfaced a cluster of seemingly-unrelated UX
bugs that all trace to the same root cause: **kourai's agent ↔ host
streaming carries text without a content-kind discriminator.** Every
status update goes through one path, gets truncated to a narrow
comms-window box, gets read aloud verbatim by TTS, and gates the
next event on its narration completion. The 905-character Mneme
"forge is empty" dialogue was read aloud including markdown asterisks
and backticks and held the next pipeline event for 25 seconds.
Pipelines that should take 60-90 seconds of model + tool work end up
at 333 seconds of wall-clock because every box waits for its
voiceover.

The convergent 2026 best practice across A2A spec, SSML, Anthropic
content blocks, and structured-streaming patterns in LangChain /
LangGraph / OpenCode is **typed content with explicit metadata,
parsed at protocol level rather than via prose conventions**. Kourai
already runs on A2A — we just aren't using its native metadata
channel for routing.

### Scope

**1. Content-kind taxonomy in `Message.metadata`.** Define a
single source of truth in `kourai_common.streaming` (new module):

| `kourai.content_kind` | Render path | TTS-eligible | Gate next event |
|---|---|---|---|
| `dialogue` | comms-window italic | yes (post-SSML) | yes |
| `status` | comms-window plain | no | no (fire-and-forget) |
| `code` | comms-window monospace | no | no |
| `spec` | wide markdown render | no | no |

Each agent's `agent_executor.py` tags every emitted event with the
appropriate kind in `Message.metadata.kourai.content_kind`. Host's
`hosts/cli/streaming.py` (and the GUI peer) routes by metadata, not
by parsing text or first-emoji-prefix detection. **Every existing
text-parsing branch in `_maidenify_status` retires.**

**2. SSML inside dialogue bodies.** Each `dialogue` Part text body
is an SSML document — `<speak>...<break time="200ms"/>...
<emphasis>...</emphasis>...</speak>`. Standard W3C markup, supported
declaratively by every major TTS provider (Google, Azure, Amazon,
ElevenLabs). Kokoro doesn't natively consume SSML; we strip-then-
synthesize as a transitional layer. ElevenLabs migration on M6
unblocks full SSML downstream.

**3. Visual rendering decoupled from TTS pacing.** Once content-kind
drives routing, status events fire-and-render immediately with no
TTS gate. Dialogue events block on TTS as appropriate. Host streaming
loop changes from "always await tts.speak before next event" to
"await iff this event is `dialogue`."

### Out of scope (defer to follow-on)

- **GUI renderer parity.** CLI-first; GUI lifts after CLI stabilises.
- **VN bridge dialogue extraction.** The Ren'Py side already has a
  separate dialogue protocol; coordinating both is M19-adjacent work.
- **Per-agent persona-aware SSML** (e.g. Hephaestus's gruff prosody
  vs Kallos's lilting cadence). Lift after the structural plumbing
  is in.

### Why now

Pre-release perfection stance (memory: `feedback_no_workarounds`).
The cluster of TTS / truncation / cadence findings cannot be fixed
in isolation without embedding a parsing-layer workaround that M7
will then need to delete. M7 → M18 in sequence is the cheapest
total-cost path even though M18 is large.

---

## M19 — Audio backend separation for TTS

> Status: shipped 2026-04-29 (Phases 1+2+3 all landed) · See Shipped
> section for the consolidated entry. Detail block intentionally
> retired per the per-project IMPL/ROADMAP convention.

---

## M20 — Audio-text synchronization across CLI / GUI / VN

> Status: planned · Surfaced 2026-04-29 (post-rebuild CLI session) ·
> Depends on M19 (RealtimeTTS provides word-level timing callbacks
> for Kokoro English voices) and M18 (content-kind metadata routes
> dialogue-only to the synced reveal path) · Player- and developer-
> experience improvement spanning all three player surfaces

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

**1. Pre-warm Kokoro at startup, per language code.** Eliminates
the 10-14s first-speak cold-start. `VOICE_ROSTER` enumerates every
agent's voice + lang_code at TTSEngine init time — load each
unique lang_code in a fire-and-forget background task before the
greeting fires. Trades startup latency (deterministic, ~10s
window where the player sees a "Tuning the forge…" progress
indicator) for a smooth first-utterance.

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

### Resolved (2026-04-22)

- **aiohttp override — no recurring-process needed.** The override for
  `aiohttp>=3.13.4` (CVE fix for a litellm transitive) now has an
  inline comment in `pyproject.toml` with the verification recipe
  (remove line, `uv lock`, check `uv pip audit`). Running the recipe
  on a schedule is over-engineering for a single override; revisit in
  ~6 months or whenever litellm's dep chain is next touched. If kourai
  ever grows more overrides, consider switching to Renovate's
  vulnerability alerts for the whole class.


### Surfaced 2026-04-27 during M16 live-smoke session

- ✅ **CLI audio volume parity** — shipped: `CLISettings` grew
  `music_volume / ambient_volume / voice_volume / sfx_volume` floats
  defaulting to the GUI's slider values (0.65 / 0.50 / 1.0 / 0.85);
  `/settings` menu shows volumes inline and adds a `[v]` sub-flow that
  prompts for each volume (Enter keeps current; decimals 0.0-1.0 or
  percent 0-100 accepted). `_apply_audio_settings` calls
  `audio.set_*_volume(settings.*_volume)` before any `play_*` so newly
  started streams come up at the chosen level.

- ✅ **Background-music toggle OFF skips to next track** — shipped:
  `AudioManager` grew `_playlist_shutdown: threading.Event` +
  `_playlist_thread` tracker; the daemon loop uses
  `Event.wait(timeout=1.0)` so it exits within ~1s of a stop signal.
  `play_playlist` is now idempotent (no-op if a thread is already
  alive); new `stop_playlist()` method joins the daemon with a
  timeout. `_apply_audio_settings` calls `stop_playlist()` BEFORE
  `stop_music(fade_ms=300)` on `music_enabled=False` — daemon stops
  before the fade completes so it can't audibly resurrect on track 2.

- **VN Codex broken (`hosts/vn/kourai_vn/game/codex_data.rpy`,
  `screens_codex.rpy`).** Symptom and reproduction TBD; needs a
  debugging session next time the VN host (`make vn`) is exercised.

---

## Shipped

One-liner per item, newest first. Detail moves out of this file when work lands.

- 2026-04-29 — **M19 audio backend separation for TTS** shipped end-to-end across all three phases. Phase 1 (CLI flip + `RealtimeTTSEngine` ABI-mirroring `TTSEngine` + 26 unit tests, commit `34f3d07`); audioop-lts hot-fix for Py3.13 (commit `e6e9cee`); Phase 2 (GUI flip + delete `hosts/gui/tts_engine.py`, -1092 LOC, commit `3ce88c0`); Phase 3 (vn_bridge migration via new `RealtimeTTSEngine.synthesize_to_wav(text, agent_name=…) -> bytes` driving `TextToAudioStream.play(muted=True, on_audio_chunk=collector)` — RealtimeTTS's documented bytes-only path — then wrapping the int16 PCM in one canonical WAV header sized from `KokoroEngine.get_stream_info()` returning `(paInt16, 1, 24000)`). pygame.mixer is out of the TTS path on every host; native 24 kHz mono Kokoro flows through PyAudio with no resample step, so the "VHS rewind" failure mode is gone by construction. Music + ambient + SFX stay on pygame.mixer at 44100 stereo; the two systems now share only the `/settings` volume slider abstraction. `kourai_common/tts_kokoro.py` + `tts_edge.py` deleted; `tts_backend.py` trimmed to `TTSVoiceConfig` + `AGENT_VOICE_MAP` + `get_voice_for_agent` (the `TTSBackend` ABC retired with its implementations). `agents/hephaestus/pyproject.toml` flipped from `edge-tts` to `RealtimeTTS[kokoro]` + `audioop-lts` so the vn_bridge container — which builds with `PACKAGE_NAME=hephaestus` — gets the right runtime deps; `hosts/gui/pyproject.toml` dropped the transitional `kokoro` / `soundfile` / `edge-tts` declarations (`RealtimeTTS[kokoro]` pulls them transitively where still needed). `docker/host.Dockerfile` got the matching system deps for cli/gui/vn_bridge (build-essential + portaudio19-dev in builder, libportaudio2 in runtime — closes the gap CI's `ed4d560` filled for Actions runners but Docker images never had). Real-Kokoro smoke produced 102 KB / 2.13 s WAV output for a five-word sentence with correct headers. The M6 ElevenLabs migration is now a one-line engine change inside `RealtimeTTSEngine.__init__`. Word-timing primitive (`on_word=` callback in `__init__`) in place for M20. 2838 unit tests green; lint + ty clean
- 2026-04-29 — **M17 Phase 2 confidence decay** shipped (closes Phase 2 end-to-end). `PROJECT_FACT_DECAY_DAYS = 90` constant + `_decayed_confidence` ladder helper (`skip ← low ← medium ← high`) + `_age_days` + `_is_preference_decayed_to_skip` filter in `kourai_common.facts`. Lazy compute on `created_at` (NOT `last_accessed` — passive recall during a session must not reset the decay timer); only player-driven re-confirmation writes a fresh `created_at`. `list_preference_facts` returns a `decayed_confidence` field alongside the original `confidence` so the CLI can surface decay state without rewriting the stored row; `get_relevant_facts_for_enrichment` filters out preference facts that have decayed to `skip` so Metis stops planning around old answers. `synthesise_fact_from_pause` now forget-then-writes (matching `set_preference_fact`) so re-PAUSE on the same scope+kind no longer stacks rows — the listing stays single-row-per-(scope, kind) and re-confirmation correctly resets the timer. 11 new unit tests (5 ladder helper + 3 listing integration + 2 recall filter + 1 PAUSE dedup property); 2876 unit tests overall green; lint + ty clean. Mirrors mem0's "memory depth" concept without the embedding-vector dependency. Closes ROADMAP §M17 Phase 2 item 9 — M17 is now fully shipped end-to-end
- 2026-04-29 — **M17 Phase 2 `/preferences` CRUD CLI + project_id stability fix** shipped. New slash command (aliased `/prefs`) lets the player browse, override, and forget closed-vocab preference facts for the active scope: bare `/preferences` lists project + global rows with a `*` marker on project rows; `set <kind> <value>` upserts (forgets-then-writes the same scope+kind so the listing stays single-row-per-kind); `forget <kind>` removes one; `forget --all` clears the whole active scope without touching global. Closed vocab enforced on `set` (same `VALID_PREFERENCE_KINDS` gate as the PAUSE synthesiser); `forget` tolerates retired kinds so right-to-forget outlives vocab churn. Three new public primitives in `kourai_common.facts` (`list_preference_facts`, `forget_preference_fact`, `set_preference_fact`) backed by the existing `player_memories` SQLite axis and `delete_player_memory`. Bundled the project_id stability fix because the feature would have surfaced empty without it: Phase 1's PAUSE-write path stamped facts with `derive_project_id([project_root: <forge_session.workdir>])`, but the REPL creates a uuid'd worktree per turn, so the id changed every session and recall never fired across sessions. Fix: new `[project_id: <derive_project_id(project.path)>]` forge tag emitted alongside `[project_root: …]`; `streaming.py:_project_id_from_forge_tags` prefers the explicit tag and falls back to deriving from project_root. Specialists keep reading project_root for git ops; only the fact synthesiser reads the new tag. 26 new unit tests (10 facts CRUD + 13 CLI handler + 3 streaming-tag preference); 2865 unit tests overall green; lint + ty clean. Aligns with the GDPR/CCPA-aligned forgetting patterns Mem0 / Letta / Supermemory converged on for 2026 — every fact removable by the player, no operator gate. Closes ROADMAP §M17 Phase 2 item 7
- 2026-04-29 — **M17 Phase 2 telemetry attributes** shipped. Metis's
  outer `metis.execute` OTel span now carries `kourai.fact.recalled`
  (bool, always set) and `kourai.fact.kinds` (list[str], set only on
  recall) so a researcher grepping Dozzle for `fact.recalled=true`
  can pivot into Jaeger via the trace ID stamped on every span-bound
  log line — the M16 trace-ID-in-logs pipeline pays off for the FL
  research direction here. Plumbing-side refactor of
  `_format_recall_narration` into three composable helpers
  (`_recalled_preferences` / `_format_recall_line` / wrapper) so the
  player view (visible narrator) and the researcher view (span
  attrs) derive from a single parsed list and can never disagree
  about whether a recall fired. 3 new unit tests in
  `TestExecutorSetsTelemetryAttributes` (recalled-true with kinds,
  recalled-false no kinds, recalled-false no project tag); 2839
  unit tests overall green; lint clean. Closes ROADMAP §M17 item 8
- 2026-04-29 — **M17 Phase 2 visible recall narrator** shipped.
  Metis's executor adds `_format_recall_narration(player_id,
  project_id)` that pops project-scoped preference facts via
  `get_relevant_facts_for_enrichment` and emits a `working_status`
  before streaming the spec — `📐 Using your stored coverage_target
  (80%).` for one fact, or a comma-joined summary for many. Closed-
  vocab gate matches the PAUSE write-side (`VALID_PREFERENCE_KINDS`
  from `hooks_interaction.py`) so free-form `<FACT>` observations
  (skills, identity) don't narrate; only PAUSE-resolved preferences
  do. The narration picks up the existing `_maidenify_status`
  rendering on every host (CLI / GUI / VN-bridge), no host-side
  changes required. 12 new unit tests in
  `tests/unit/test_metis_recall_narrator.py` (3 executor-integration
  + 9 pure-helper); 2836 unit tests overall green; lint clean.
  Closes the "silent recall feels like agents are guessing" trust
  gap that motivated ROADMAP §M17 item 6
- 2026-04-29 — **M17 Phase 1 shipped end-to-end** (six PRs in one session: #81 / #82 / #84 / #85 / #86 / #87). The HOTL → facts loop is live for one-time-per-project preferences: a clarifying answer in project A persists, surfaces in Metis's planning prompt the next session for project A, and stays hidden when the player switches to project B. Mechanism: `derive_project_id(project_root)` (sha256-of-canonical-path, 16 hex) + `project_id` axis on `PlayerFact` / `KnowledgeGraphFact` / `player_memories` SQLite + single-query SQL filter with `CASE WHEN project_id = ? THEN 1 ELSE 0 END DESC` ranking boost (project beats global at equal importance / recency) + `synthesise_fact_from_pause` helper + `kourai_common.pause_state` in-process stash + `kourai_common.pause_tag` parser for the new `PAUSE: <kind> "<question>"` runtime control token (mirrors M13's CONFIRM_ORDER shape; closed Phase 1 vocab `coverage_target` / `python_version` / `style_rules` / `commit_style` / `test_framework`) + Metis system-prompt addition + Metis executor pause path + CLI streaming layer pop-and-synthesise at the top of every turn + Metis `create_spec_stream` threading `player_id` / `project_id` to `build_fact_context` so PLAYER CONTEXT leads the user-message context block. Three calls that diverged from the original sketch: `run_post_task_hooks` had no production call sites so write-on-resolve calls `synthesise_fact_from_pause` directly from `streaming.py` where Memoir already lives (promote-back-to-hook layer queued as a follow-on under M5/M6); Metis didn't actually call `build_fact_context` despite the ROADMAP's "every specialist's prompt is enriched the same way" claim (only Puck and Cupid did — fixed surgically for Metis in PR #87, parity for Techne / Kallos / Dokimasia / Hephaestus deferred until a non-Metis PAUSE caller surfaces); cross-turn state lives in-process so agent restart between pause and resume drops the classification (Memoir still captures the answer as labeled FL training data, fail-soft). 48 new unit tests including `tests/unit/test_metis_fact_recall.py::TestM17Phase1RecallProperty::test_metis_recalls_project_a_fact_only_in_project_a` exercising the production recall path through Metis's prompt construction. The honest external-artifact claim ("Kourai captures HOTL responses as project-scoped entries… Metis recalls preferences without re-asking and stays scoped per project") is now defensible. Phase 2 (visible recall narrator + `/preferences` CLI + telemetry attributes + confidence decay) deferred until Phase 1 has miles
- 2026-04-28 — `chore(deslop)` drop PyGithub helpers without callers (#80, sibling of PR #72): three more "import a library that isn't a declared dependency, fall through ImportError on every code path, never get called anyway" helpers — same dead-twice-over pattern as PR #72's `github_search_code` and `introspect_database`. PyGithub has never been in `pyproject.toml` or `uv.lock`, so every `from github import Github` falls into the ImportError branch and returns `[]` (or the "PyGithub not installed" error dict). Deleted: `agents/hephaestus/agent.py::github_search_repositories` (zero callers anywhere), `agents/metis/agent.py::github_search_issues` + its `tests/unit/test_metis.py::TestGithubSearchIssues` class (3 cases — no-token, ImportError, mocked-results — testing a function nothing called in production; the happy-path test patched `sys.modules` to inject a fake `github` module that didn't reflect any real install state, locking in a wrong shape against any future rewire), `agents/mneme/agent.py::github_create_pull_request_impl` (the "actually create a PR on GitHub" function that nothing called — `create_github_pr` returns a HOTL choice JSON which the executor parses and discards, then decorates the artifact with a "GitHub PR Ready" header without ever wiring back to `_impl`; was anticipatory infra without a caller, PR #74's pattern). `create_github_pr`'s docstring updated to be honest about the unwired state — the previous hint at `_impl()` was misleading. Documentation drift fixes bundled: `docs/configuration.md`'s `GITHUB_PERSONAL_ACCESS_TOKEN` block claimed the token was "Used by Mneme (PR generation), Techne (code search), Metis, and Hephaestus" — after PR #72 + this PR, only Mneme still touches the token (and even then only to flag PR-readiness, not to create the PR), so the doc was reduced to the truth; `shared/src/kourai_common/mcp_client.py` module docstring listed "GitHub: Issue/PR/repo operations (direct PyGithub)" and "Playwright: Frontend E2E testing (direct subprocess)" — neither is real, both removed; `pyproject.toml` `tool.ty.analysis.replace-imports-with-any` `"github.**"` entry dropped (no remaining `from github import` lines anywhere); `tests/unit/test_metis.py` `from unittest.mock import` line drops the now-unused `MagicMock`. What stays in Mneme: `parse_commits_for_pr` and `create_github_pr` are both still called by `agents/mneme/agent_executor.py` — those build the PR-ready metadata + choice-event JSON the executor decorates the artifact with. The actual PR creation step from there remains unwired; that's a separate "finish the HOTL flow" piece of work, not deslop. 285-line deletion. 2736 unit tests pass (was 2739 — exactly the 3 deleted `TestGithubSearchIssues` cases, no other regressions); lint green
- 2026-04-28 — `chore(deslop)` remove broken Playwright e2e flow from Dokimasia (#79): `run_playwright` was a stub returning empty `PytestRunResult()` since 2026-03-31 commit `27b7190` (\"feat(agents): implement accessibility snapshots and pluggable TTS streaming\") replaced the function body with `# ... (rest of the function)\nreturn PytestRunResult()` while adding `get_accessibility_snapshot` next to it. ~4 weeks of dead code, undetected because the e2e detection only fires on specific keywords. Player-facing impact: when input matched `is_e2e_request` (`\"e2e\"` / `\"playwright\"` / `\"frontend test\"` / `\"browser test\"` / `\"ui test\"`), Dokimasia generated Playwright spec.ts via real LLM call, then \"ran\" them via the stub which returned `PytestRunResult(passed=0, failed=0, ...)`, then rendered `🎭 Playwright E2E Test Results\n\nPytestRunResult(...)` to the player — silent fail reading as \"0 tests, all clean\". Compounding: `get_accessibility_snapshot` calls `page.accessibility.snapshot()` which Playwright **removed** after 3 years of deprecation (microsoft/playwright#16159; replacement is `expect(locator).to_match_aria_snapshot()`); bare `# type: ignore` (no error code) was hiding this; helper had zero callers anyway — dead twice over, same pattern PR #72 cleaned up for `github_search_code` / `introspect_database`. Two-commit cleanup: (1) deletes `run_playwright` + `get_accessibility_snapshot` + `generate_playwright_tests` (only the e2e branch called it) + the entire `is_e2e_request` branch in `agent_executor.py`; (2) drops `playwright>=1.40` from `agents/dokimasia/pyproject.toml` (and 3 packages from `uv.lock` — playwright + greenlet + pyee), removes the 44-line dokimasia-only Chromium install block from `docker/host.Dockerfile` (~30 system libs: chromium itself, GTK, X11, ALSA, fonts), removes `PLAYWRIGHT_BROWSERS_PATH` + `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD` from `docker-compose.yml`, drops the `playwright` + `dbhub` phantom MCP toolkit registrations in `mcp_client.py::_initialize_default_registry` (neither MCP server has ever existed in `mcp_servers/` — directory is `forge` + `shell` only) plus dokimasia's `assign_servers` line dropping the dead `playwright` reference, updates four docs (`agents/dokimasia/README.md` three-modes → two-modes + e2e_test_results artifact removed, `ECOSYSTEM.md` drops the `playwright>=1.40` rationale paragraph, `README.md` Stack list drops \"Browser Context — Accessibility-Tree Snapshots for token-efficient E2E reasoning\", `.github/copilot-instructions.md` drops Chromium-install line and obsolete \"`playwright` and `dbhub` registered but disabled\" note). 168 lines net removed. Honest beats theatrical: if a player wants Playwright tests, the default branch generates them via `generate_tests_stream` and the artifact contains the spec.ts code with no claim of running it; player runs `npx playwright test` themselves. Web-search via Playwright release notes + GitHub issues confirmed `page.accessibility.snapshot()` is gone post-deprecation, so the function couldn't have been unstubbed without rewriting against the new ARIA-snapshot assertion API anyway. 2739 unit tests pass; lint green; container size win for the dokimasia agent
- 2026-04-28 — ty re-raise after `pytest.skip` in `_safe_edge_synthesize` (#78): caught by `aj-ci-audit` scanning the latest green main run for buried warnings — `make lint` had reported `rc=0` for a ty `invalid-return-type` diagnostic because ty exits 0 on warnings; only the `Found N diagnostics` line surfaces them. Root cause: pytest exposes `skip` as a callable class instance (`skip: _Skip = _Skip()`) whose `__call__` is `-> NoReturn`, but ty doesn't propagate the `NoReturn` annotation through the callable-class export pattern, so ty treats `pytest.skip(...)` as a normal call that could return → function may fall off the end → implicit `None` mismatches the declared `-> bytes`. Fix: explicit bare `raise` after the `pytest.skip(...)` call in PR #76's `_safe_edge_synthesize` helper. Unreachable at runtime (skip already raised `Skipped`), satisfies ty's flow analysis, and re-raises the in-flight network exception if `pytest.skip` somehow did return — semantically correct under both readings. 4-line one-file change. Closes the loophole that let a ty regression slip past three "make lint green" checks today; future reads check the diagnostic count, not just the rc
- 2026-04-28 — `chore(deslop)` trim signature-restate docstrings + stale task-context comments (#77): targeted second pass after #72's unused-helper deletion. Five `aj-deslop` Explore subagents fanned out across `agents/` / `hosts/cli/` / `hosts/gui/` / `shared/src/` / `scripts/`+`mcp_servers/` with the canonical hate-words grep seed list — 38 candidate findings, this PR shipped the 19 clear-wins + task-context-rot subset (kept the ~8 borderline cases where the subagent misclassified pricing audit trails, LLM-facing prompt templates, user-facing CLI help text, and quoted dialogue). 18 edits across 7 files; zero behavior change. Pure signature-restate docstrings deleted from `hosts/gui/pipeline_status_gui_integration.py` (9 sibling `update_*` / `notify_*` / `set_*` methods) and `hosts/gui/gui_components_integration.py` (7 `get_*` accessor docstrings — function names already convey intent). Marketing-word trims on `hosts/gui/performance_profiler.py:144` and `hosts/gui/loading_screen.py:3`. Task-context rot trimmed from `hosts/cli/__main__.py` (`/compact` and `/permissions` slash-command docstrings carrying stale "surveyed 2026-04-26 (see ROADMAP M6 ... → tier-1 priority)" breadcrumbs that belong in PR descriptions, not source) and `hosts/cli/settings.py` (volume-defaults audit trail dated 2026-04-27). `agents/hephaestus/agent.py::auto_approve_reads` had its "Tier-2 lift from the 2026-04-26 OSS-CC research sweep" comment trimmed entirely since the surrounding paragraph already explains the gate semantics. IMPL.md side-cleanup: two M16 follow-on entries removed from "Up next" that were already done (`docker-tag` digester + `docs/observability.md` cross-link both verified-present in repo). 130 focused tests pass; lint green
- 2026-04-28 — Skip TTS integration tests on third-party network outage (#76): Edge-TTS reaches Microsoft's Bing speech WebSocket (`wss://speech.platform.bing.com/...`) for synthesis; CI's egress to that endpoint flakes occasionally. Concrete recent example: PR #71's first run failed on `test_different_backends_same_voice_config` for exactly this reason — environmental, not a kourai bug, but it forced a full integration-suite rerun and burns a CI slot for every unlucky PR. New `_safe_edge_synthesize(backend, text, voice)` helper catches the seven network-class exceptions (`aiohttp.ClientConnectionError` / `ClientConnectorError` / `ClientPayloadError` / `ClientResponseError` / `ClientSSLError` / `ServerDisconnectedError` + `asyncio.TimeoutError`) and hands the test a `pytest.skip(...)` with a reason that explicitly names the endpoint and exception. Real backend bugs (assertion errors, import errors, malformed audio) still surface unchanged — only the network-class exceptions trigger the skip; `_skip_or_fail_unavailable`'s CI-fails-on-missing-dep semantic stays intact for missing-dep regressions. Applied at all four Edge-TTS synth call sites (`test_edge_tts_voice_mapping_for_agents`, `test_edge_tts_multiple_voices`, `test_backend_fallback_to_edge_tts`, `test_different_backends_same_voice_config`); Kokoro tests are unchanged since `hexgrad/Kokoro-82M` runs locally with no third-party network dependency. Web-search sanity-check (pytest docs "skip and xfail" + "Flaky tests" explanation) confirmed catch-and-skip is the canonical pattern for unreliable external services rather than blanket `@pytest.mark.flaky` (which would also mask real regressions). Live verification deferred to next time Microsoft drops a connection mid-test (hard to force deterministically); passes as a no-op on a green network
- 2026-04-28 — **M2 effectively closed — Changes 1/2/3 shipped, Change 4 deferred-by-design** (1465 lines net touched today across four PRs, then a fifth opened + closed for Change 4). The forge MCP carve-out is live: `kourai-mcp-forge` stdio server in `mcp_servers/forge/`, three specialists (Techne / Kallos / Dokimasia) routed through the `forge_tool_bridge` async context manager via `MCPToolkit`; client declares `roots` in the initialize handshake via `_kourai_list_roots` reading `kourai_project_root_var`. Change 4 (MCP `elicitation` client capability + INPUT_REQUIRED bridge) was attempted as PR #74 — 1165-line implementation closed unmerged after the original "elicitation = spec-blessed analog of M13's `CONFIRM_ORDER`" framing turned out to be a category mismatch on closer inspection: `CONFIRM_ORDER` is an A2A pre-pipeline gate (correct primitive: A2A `INPUT_REQUIRED`), not a mid-MCP-tool-call request, so MCP elicitation isn't its right home. No forge MCP tool currently calls `ctx.elicit()` either, so building the bridge today would have been anticipatory infrastructure with no caller — flagged off-mission per AJ's CLAUDE.md rule "don't design for hypothetical future requirements." When a real MCP-server-side elicitation caller appears (natural candidate: `delete_file` confirming destructive deletes against uncommitted changes), the round-trip design from PR #74's diff is the implementation reference: HTTP side-channel from CLI to specialist via new Starlette route, asyncio Future registry, contextvar emitter; specialist's `execute()` stays running blocked on the Future, streaming connection to Hephaestus stays open, eventual artifact reaches the player normally
- 2026-04-28 — Audio test isolation cleared (#75): `pytest tests/unit/` on plain main produced 3 spurious failures (`test_play_ambient_with_path` / `test_play_ambient_generative` / `test_cleanup`) every full-suite run while passing in isolation. Bisected to `tests/unit/test_audio_env.py::test_audio_module_import_triggers_sdl_configure` — a regression guard that calls `importlib.reload(audio)` to verify SDL-backend wiring. The reload swaps `kourai_common.audio.AudioManager` for a fresh class object, but `tests/unit/test_gui_audio_tts_engine.py`'s top-level `from kourai_common.audio import AudioManager` had pinned the *pre-reload* class in the file's module namespace. After reload, `mock_audio_mixer` fixture reset the live class's `_instance` while test bodies instantiated the stale class, whose `_initialized = True` made `__init__` early-return without firing the freshly-mocked `pygame.mixer.Channel` / `Sound`. Fix: bind `AudioManager` lazily — `from kourai_common import audio` at the top + `audio.AudioManager(...)` at every call site (25 sites + 4 stale inline imports removed). Module-attribute lookup happens at call time, so the live class is always used. Full unit suite now `2739 passed` (was `3 failed, 2736 passed`); developer DX win since every `make test` / `pytest tests/unit/` locally now produces a clean run instead of 3 spurious failures, and CI burns fewer rerun cycles when something unrelated touches files. Web-search sanity-check (advancedpython.dev "Finding test isolation issues with PyTest", Mindful Chase "fixture leaks / flaky tests / CI performance") confirmed the lazy-bind pattern is the canonical fix for `importlib.reload` + sibling-file import pollution
- 2026-04-28 — ty `Found 0 diagnostics` baseline restored (#73): a single regressed warning at `tests/unit/test_techne.py:175:60` had crept in since the 2026-04-27 cleanup that first cleared the baseline (#46). ty's hint pointed straight at the fix — `dict[str, Callable[..., Awaitable[str]]]` is invariant in its value type, so `dict[str, MagicMock]` literals get rejected even when MagicMock is structurally callable. `MCPToolBridge.tool_handlers` is read-only after construction (every call site is `bridge.tool_handlers[name]` / `.get(name)` / `.keys()`; nothing mutates), so `Mapping` (covariant in value type) is the structurally correct annotation per ty's own suggestion. Three changes: `MCPToolBridge.tool_handlers` flipped to `Mapping[str, Callable[..., Awaitable[str]]]` in `shared/src/kourai_common/mcp_bridge.py`; `chat_with_tools`'s `tool_handlers` parameter matched in `shared/src/kourai_common/llm.py` so the bridge's now-`Mapping`-typed field still passes; `tests/unit/test_techne.py` swapped `MagicMock()` for a real `async def _marker_handler(_args: dict) -> str` stub (the test never invokes it; it's just yielded into the bridge as a marker). 154 tests pass across techne / kallos / dokimasia / mcp_bridge / llm / executors. The "any new ty warning is visibly the cause" property restored
- 2026-04-28 — `chore(deslop)` drop unused scaffolds (#72): 195 lines removed across three never-called helpers — `agents/techne/agent.py::github_search_code` (imports `from github import Github` inside a try-block guarded by `ImportError`; PyGithub isn't a declared dependency anywhere in `pyproject.toml` or `uv.lock`, so it falls through to `[]` on every code path AND has zero callers — dead twice over), `agents/techne/agent.py::introspect_database` and `agents/dokimasia/agent.py::introspect_database` (both return hardcoded `{"error": "DBHub MCP integration pending"}` dicts, no DBHub MCP server exists in `mcp_servers/`, comment "Deploy Memory + DBHub MCP sidecars in docker-compose.yml" describes infra that doesn't exist). Verified zero references via `grep -rn` across `*.py` / `*.md` / `*.toml` — only the definitions themselves matched. Pure deslop pass; fewer LOC for future readers to skim past. `make lint` green, full unit suite green
- 2026-04-28 — Block "explore directory first" failure mode for file-op specialists (#71): the 2026-04-28 architectural smoke verified PR #64's W3C trace context propagation through the MCP forge subprocess end-to-end (CLI → Hephaestus → CONFIRM_ORDER prompt ≤3s → "yes" → Techne MCP bridge launches with 4 tools → `forge.read_file` nests under `techne.tool_loop` under `techne.execute` as one continuous trace), but exposed a Techne system-prompt bug: Haiku-on-cheap-tier reliably tries `read_file(".")` to "explore the project structure" before writing, hits the forge server's directory-rejection guard (the load-bearing one PR #67 kept), reads it as a permission lockout, and abandons the task with "I'm hitting permission walls on this forge." Even an explicit "use write_file to create hello.py" prompt didn't override it. Five paired tightenings address the failure mode at every layer the model sees: (1) `agents/techne/agent.py` TOOL USE block rewritten to state explicitly there is no directory-listing tool, forbid `.`/`src/`/folder paths to `read_file`, and give two action paths (write_file directly for new files; read_file on a SPECIFIC existing file before edit_file); (2) `agents/kallos/agent.py` same framing, smaller diff; (3) `agents/dokimasia/agent.py` `apply_test_fixes` inline addendum notes the failing files are already provided so reads should only confirm exact text before edit_file; (4) `mcp_servers/forge/src/kourai_mcp_forge/server.py` `read_file` schema docstring leads with "specific file, never `.` or a directory" + "Skip this entirely when creating a new file; call write_file directly" so the rule shows at tool-discovery time via `await session.list_tools()`, not just on failure; (5) `shared/src/kourai_common/forge_tools.py` runtime directory-rejection error drops the misleading "list the directory contents yourself" hint (impossible — there is no listing tool) and redirects to write_file-direct for new files or a specific path for reads. 118 focused tests pass across techne / kallos / dokimasia / executors / forge_tools / forge_mcp; pre-existing TTS network flake on the integration suite cleared on rerun, no test regressions. Smoke 1 re-run queued for whenever `api.anthropic.com` outbound from agent containers stabilises
- 2026-04-27 — **M2 Change 3b/c/d shipped — three specialists routed through the MCP bridge** (Techne / Kallos / Dokimasia). Combined into one PR after April 2026 MCP best-practice research confirmed STDIO sessions are inherently stateful: one `forge_tool_bridge()` `async with` block holds the subprocess for the entire `chat_with_tools` lifetime (typically 10+ tool calls across the LLM loop), so subprocess startup amortizes across all calls and the original "per-tool-call subprocess" perf concern dissolved. Each migrated function (`apply_code_changes`, `apply_lint_fixes`, `apply_test_fixes`) replaces `tools=FORGE_TOOL_SCHEMAS, tool_handlers=FORGE_TOOL_HANDLERS, handler_context={"project_root": ...}` with `tools=bridge.tools, tool_handlers=bridge.tool_handlers` inside a `forge_tool_bridge()` block; defensively sets `kourai_project_root_var` from its `project_root` parameter so standalone callers (tests / direct invocation) still get correct roots scoping; `handler_context` removed entirely (single-source via roots/list). Test mocks updated to patch `forge_tool_bridge` alongside `chat_with_tools` so the test path doesn't launch the real subprocess. New regression test asserts the defensive contextvar set. Static `FORGE_TOOL_SCHEMAS` / `FORGE_TOOL_HANDLERS` exports are now unused outside `test_forge_tools.py::TestSchemaShape` — deletion left for a small follow-up PR. Player-side transparency win: forge tool calls now emit per-tool OTel spans (`forge.read_file` / `forge.write_file` / `forge.edit_file` / `forge.delete_file` from #57) inside the subprocess, so `make observe` users see proper per-tool granularity in Jaeger instead of one opaque chat-with-tools span. Full unit suite `2735 passed`; `make lint` ends `Found 0 diagnostics`. Live verification (specialist container hits forge subprocess end-to-end with real LLM tool calls) deferred to next interactive `make up` session
- 2026-04-27 — Two coupled CLI audio bugs fixed (M6 surfaced 2026-04-27 follow-on). (1) CLI volume parity: `CLISettings` grew `music_volume / ambient_volume / voice_volume / sfx_volume` floats mirroring the GUI's slider defaults (0.65 / 0.50 / 1.0 / 0.85); `/settings` shows volumes inline with each toggle and adds a `[v]` sub-flow that prompts for each volume (Enter keeps current; accepts decimals 0.0-1.0 or percent 0-100). `_apply_audio_settings` applies volumes before `play_*` so newly-started streams come up at the chosen level. (2) Music-toggle-OFF skips-to-next-track: `AudioManager` grew `_playlist_shutdown: threading.Event` checked between polling ticks via `Event.wait(timeout=1.0)` (responsive to stop signals within ~1s); `play_playlist` is now idempotent (no-op if a thread is already alive — fixes the prior bug where every `_apply_audio_settings` re-run spawned another daemon racing with the first); new `stop_playlist()` method joins the daemon with a timeout; `_apply_audio_settings` calls `stop_playlist()` BEFORE `stop_music(fade_ms=300)` on `music_enabled=False` so the daemon can't see "not playing" and resurrect the playlist on track 2 the moment the fade completes. 15 new tests across `test_gui_audio_tts_engine.py::TestPlaylistLifecycle` (4 — idempotency, stop signal latency, no-op when not running, restart after stop), `test_cli.py::TestCLISettingsVolumes` (5 — defaults match GUI, clamping, persistence, key validation), `TestAdjustVolumesFlow` (4 — Enter-keeps, decimal input, percent normalization, invalid-input skip), `TestApplyAudioSettingsMusicOff` (2 — call-order regression guard, volumes-before-play). Player-facing bug AJ hit during M16 smoke — the only available relief from too-loud ambient was flipping it OFF entirely, and toggling Music OFF audibly resurrected on track 2
- 2026-04-27 — **M16 fully shipped — observability DX uplift end-to-end** (this PR + #47/#48/#49 across three sessions; the stack now runs `jaegertracing/jaeger:2.17.0` + `prom/prometheus:v3.11.3-distroless` with the `spanmetrics` connector emitting RED metrics on `:8889`). Eight pieces, one trajectory: (1) Mneme `_OtelTraceFilter` in `shared/src/kourai_common/log.py` reads `trace.get_current_span()` directly via the `opentelemetry-api` we already depend on — **did NOT** end up using `opentelemetry-instrumentation-logging`, whose record factory only injects `otelTraceID` / `otelSpanID` when `set_logging_format=True` (verified by reading the source — both the attribute injection and the `basicConfig` call are gated on the same flag), which would clash with `log.py`'s explicit handler setup. (2) `_TraceAwareFormatter` switches between two format strings per-record so non-traced lines (startup chatter, pre-request setup) skip the `[trace=...]` block entirely instead of padding 32 zeros — when present the trace ID renders as full 32-char hex (`[trace=750edeb816c2fa5eab9b2261945b1c10]`, copy-paste-grep-able from Jaeger). Both console + `RotatingFileHandler` carry the filter so trace IDs land in Dozzle live tail AND `logs/<agent>.log` archive. (3) `make observe` quickstart wired through `Makefile` + `shared/src/kourai_common/dev_cli.py` + new `scripts/observe.py` — cross-platform browser dispatch with explicit WSL2 handling (`webbrowser` falls back to `gio` which can't open `http://` without a real GNOME session, so we bypass to `wslview` from `wslu` when present, otherwise drop to `cmd.exe /c start` via WSL interop at `/mnt/c/Windows/System32/cmd.exe`). (4) `docs/observability.md` onboarding page wired into the Zensical nav under Architecture → Observability — mental-model table (trace=flow, metric=aggregate, log=narrative), `make observe` quickstart, cross-tool linking explainer covering the trace-ID-in-logs plumbing, four-pattern triage runbook ("agent looks stuck", "request finished but felt slow", "errors visible somewhere unclear which agent", "OOM / kept restarting"), container-groups table mapping the four `dev.dozzle.group` buckets, "what's currently populated, and what's not" honesty section flagging Prometheus as sparsely-populated today (so contributors don't go hunting for Monitor-tab data that isn't there yet), span naming convention table. (5) `dev.dozzle.group` labels added across `docker-compose.yml` (agents / observability / mcp / infra) so Dozzle's group rendering matches the docs page. (6) `docs/architecture/infrastructure.md` slimmed to a brief intro + link, fixing the **SPM overpromise** that page carried (it claimed the Monitor tab was populated; the audit showed it isn't, and that mismatch would have burned a new contributor). (7) Jaeger v1.60 → v2.17.0 migration via OTel-Collector–shape `docker/jaeger-config.yaml` (#48); env-var collapse (`COLLECTOR_OTLP_ENABLED`, `METRICS_STORAGE_TYPE`, `PROMETHEUS_SERVER_URL`, `PROMETHEUS_QUERY_SUPPORT_SPAN_UNIT`, `SPAN_STORAGE_TYPE`) into a single config file built on the OTel Collector framework. (8) `spanmetrics` connector + Prometheus `v3.11.3-distroless` + agent RED scrape (#49) — web-searching current best practice while bumping pins caught two details that would have shipped unnoticed: `dimensions_cache_size` is deprecated post-Jaeger-v2.16 in favor of the `dimensions_cache.max_size` shape, and the spanmetrics 60s default `metrics_flush_interval` is the post-deprecation default that wants explicit acknowledgment. Dozzle pin verified `v10.5.0` exactly current (released 2026-04-26 21:13 UTC; no bump). 4 new unit tests in `tests/unit/test_logging.py::TestOtelTraceInjection` (bare format outside span, trace ID rendered inside span, filter populates `otelTraceID` from active context, both handlers carry the filter); ruff format + ruff check + ty all green. M16 follow-ons queued separately in IMPL.md: live trace-ID-in-Dozzle smoke (unit-tested but worth eyeballing in a real `make up` + smoked pipeline), `.claude/skill-context.md` cross-link to `docs/observability.md`, `scripts/watch_protocols.py` `kind="docker-tag"` digester for `amir20/dozzle` / `jaegertracing/jaeger` / `prom/prometheus` so future image drift surfaces automatically. M16 detail block removed from above; this is the canonical record
- 2026-04-26 — **M1 fully shipped — Round 6 live smoke validated end-to-end** (accept path 6a + discard path 6b, both clean). Provider tool-use loop replaces the `parse_and_apply_fixes` regex parser everywhere it ran. Validation: 22 `'type': 'tool_use'` frames in techne container logs (with `toolu_*` IDs proving real provider blocks); 11 `'type': 'tool_result'` frames closing the loop; **zero `parse_and_apply_fixes` hits** across all 6 agent containers (`techne`, `hephaestus`, `metis`, `dokimasia`, `kallos`, `mneme`). Wall-clock: 244.8s on 6a, 418.6s on 6b — both under the 462s v2 baseline; the provider tool-use loop is faster than the regex parser AND cleaner. Bonus emergent behavior: Aidos's slop-detection now actively *teaches* commit-message hygiene with `<FACT category="skill" confidence="medium">` markers tracking the player's improvement across runs (e.g., flagging "comprehensive" as repeated slop after the first run). M1 detail block removed from above; this is the canonical record
- 2026-04-26 — `/clear` ANSI escape mangled by `prompt_toolkit.patch_stdout` (printed `?[2J?[1;1H` literally instead of clearing the viewport). Fix: new `hosts/cli/rendering._clear_screen()` helper writes the standard cursor-home + erase-screen sequence (`\x1b[H\x1b[2J`, matching Ubuntu's `clear`) directly to `_raw_out` (the pre-`patch_stdout` stream) — same pattern `_echo()` already uses to bypass the proxy. `hosts/cli/__main__.py` calls the new helper instead of `click.clear()`; click import retained for the rest of the CLI. Caught in AJ's REPL during M1 Round 6 smoke
- 2026-04-27 — Real-time per-container log dashboard via dozzle (this PR): added `amir20/dozzle:v10.5.0` as a compose service (read-only docker socket mount, localhost-bound on `127.0.0.1:8888`, filtered to the `kourai-khryseai` compose project via `DOZZLE_FILTER`). Direct response to AJ's "can we make a tiny frontend that shows the agent logs in real time" question earlier in the day — confirmed dozzle is still the right pick over Loki+Grafana (heavier, production-grade) and Logdy (general-purpose pipe viewer) for our shape (single dev box, ~14 containers, want a single browser tab). Pairs with the existing observability layer: Jaeger (per-trace flow, http://localhost:16686) + Prometheus (rates/durations, http://localhost:9090) + dozzle (per-agent live tail, http://localhost:8888) — three panes that together cover "where did this request go," "how often / how slow," and "what is *this* agent saying right now." Verified live: HTTP 200 from the UI, dozzle logs `Connected to Docker` + `Accepting connections on :8080`, container filter scopes correctly to the project's 14 containers
- 2026-04-27 — ty warning baseline cleared (#46): 20 pre-existing ty warnings → 0 in a single bulk-cleanup PR. Picked from a four-option triage produced by `aj-ci-audit` on PR #45's CI logs (options were: bulk PR, per-area split, accept-baseline, defer). Per-file: 5 mock None-narrowing warnings in `test_tool_call_streaming.py` (assert-not-None before .kwargs / before invoking captured callback), 2 isinstance narrowings in `test_confirmation_protocol.py` (mirror the existing pattern), 4 Optional-field assertions in `test_memoir_schema.py`, 2 in `test_audio_env.py` (refactored to monkeypatch.setattr), 1 in `test_hephaestus_confirmation.py` (intentional frozen-mutation test, switched to `# ty: ignore[invalid-assignment]`), 1 cast in `agents/hephaestus/confirmation.py:66` (replaced ineffective `# type: ignore[arg-type]` — ty uses different syntax than mypy), 1 Queue type drift in `hosts/gui/subsystem_loader.py` (real architectural find: M11 attachment send-path's 3-tuple shape; could have surfaced as runtime AttributeError), 1 ty:ignore in `shared/src/kourai_common/llm.py:215` (dict narrowing through generics), 3 explicit-kwargs refactors in `hosts/cli/__main__.py:875` (replacing loose `dict[str, object]` unpacking with named `Memoir | None` / `str | None` locals). Process discovery: ty's ignore-comment syntax is `# ty: ignore[<rule>]`, not mypy's `# type: ignore[<rule>]` — distinct. All 2675 unit tests pass; `make lint` ends with `Found 0 diagnostics` for the first time. Now any PR that adds a ty warning is visibly the cause rather than buried in the baseline
- 2026-04-27 — Skill-context migration from personal memory (#45): audited my per-user memory accumulator (`~/.claude/projects/-home-ajbar-ajsoftworks/memory/MEMORY.md`) against the question "would a future contributor / fresh agent benefit from knowing this?" 8 per-repo facts moved to `kourai-khryseai/.claude/skill-context.md` (working_docs / ci_pipeline / design_north_stars / renpy sections — covering the demo-vs-interactive Make targets, `make lint` pre-push gate, ruff format/check separation, Ren'Py 8.5.x version pin, design ethos, etc.); 5 cross-project rules moved to `~/.claude/CLAUDE.md` (working docs convention covering COMMITS.md temporary + ROADMAP/IMPL committable, paper-grade default, no time estimates, "you decide" autonomy, concise external comms, tmux+script CLI-driving pattern). Personal MEMORY.md pruned 17 → 5 entries (78% reduction). Wins: future Claude in this repo auto-picks up the rules via skill injection (no dependency on my memory accumulator); subagents (Plan / Explore / code-reviewer) get the same context when invoked; human contributors can read `.claude/skill-context.md` to onboard themselves
- 2026-04-27 — Spec drift watcher cron (#44): new weekly GitHub Actions cron `.github/workflows/spec-watch.yml` invokes `scripts/watch_protocols.py` to check 7 canonical URLs (MCP 2025-11-25 spec page, MCP blog, A2A latest spec, A2A + MCP repo release atom feeds, PyPI `a2a-sdk`/`mcp`) and opens a `protocol-watch`-tagged GitHub issue on any digest drift. Per-source digest functions (`html` full-content hash, `feed` entry-title hash, `pypi` version string) keep the diff signal-rich rather than a noisy bytewise compare. State persists between cron runs via `actions/cache`; transient HTTP failures carry the prior baseline forward so a bad week doesn't wipe state. Local dry-run via `python scripts/watch_protocols.py --dry-run`. 29 unit tests in `tests/unit/test_watch_protocols.py` covering digest stability, diff detection, fetch-failure handling, state roundtrip, dry-run path, and watch-list contract (no duplicate keys, every kind has a digester, every URL is https, every watch has a non-empty note). Direct response to the 2026-04-27 finding that A2A v1.0's `Message.metadata` channel landed months ago without us noticing — turning "track latest aggressively" from ad-hoc nudge-driven into a triageable inbox item
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
