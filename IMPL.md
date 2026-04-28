# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-28 · Working on:
[**M2 — Carve out `kourai-forge-mcp`**](./ROADMAP.md#m2--carve-out-kourai-forge-mcp) —
Changes 1 / 2 / 3 done; Change 4 lands in this session as the
elicitation client capability + INPUT_REQUIRED bridge (PR pending). Today's session shipped two side-quests from the
`plans/2026-04-28-live-smoke-handoff.md` queue: PR #65 bumped
`prom/prometheus` v3.10.0 → v3.11.3 (security + OTLP fixes, both
scrape targets healthy post-bump, full CI green, **merged**), PR #66
fixes two Ren'Py 8.5 screen bugs that were blocking the codex path
(`key "return"` → `K_RETURN` in `forge_input` + bare-identifier
nested text-sub in the codex notification toast). Smoke 1 (live A2A pipeline through Hephaestus →
Techne) deferred — `api.anthropic.com` outbound from the agent
containers is timing out at ~60% on the WSL2 docker bridge today,
purely environmental (host-side `curl` is fine; container-side
~3-of-5 attempts time out). Picks back up next session when the network
flake clears, or on a different machine.

---

## Plan-of-record

End state: a real `kourai-forge-mcp` MCP server in `mcp_servers/forge/`
exposing the M1 forge tools (`read_file` / `write_file` / `edit_file` /
`run_command`) over stdio. Specialists (Techne, Kallos, Dokimasia)
become MCP clients via the existing `MCPToolkit`. A fourth specialist
or a third-party host (Claude Code, Cursor, IDE plugins) can adopt the
same forge without re-importing Python helpers — the wire format does
the work.

Workstreams ordered by **design-time-cost-of-deferral**, not strict
dependency. Init-handshake declarations (Change 1) are the load-bearing
piece — retrofitting `roots` / `elicitation` / `sampling` after the
server is scaffolded is significantly more painful than declaring them
upfront.

### Change 1 — Declare `roots` capability with project-root scope (design-time gate) ✅ 2026-04-27

**Why first.** MCP's `initialize` request is where a host advertises
which client capabilities it speaks. The MCP Python SDK 1.27.0 (which
we're pinned to) gates capability declaration on **callback presence**:
when `ClientSession.initialize()` runs, it declares `roots` /
`elicitation` / `sampling` only when the corresponding callback is
non-default (verified by reading
`mcp/client/session.py:148-188`). Default callbacks return
`ErrorData(INVALID_REQUEST, "...not supported")` — the worst case.

So the right approach is "declare what we actually implement, leave
the rest off". `roots` lands now (real callback, real backing data —
the player's `project_root`). `elicitation` lands with Change 4 (when
INPUT_REQUIRED routes through it). `sampling` lands when the first
caller appears (no callers exist today). Splitting like this avoids
the "host that lies about its capabilities" trap that an
all-three-with-stubs approach would create.

- [x] New `build_client_session(read, write) -> ClientSession`
  factory in `shared/src/kourai_common/mcp_client.py` — wraps
  `ClientSession` construction with kourai's standard client-side
  callbacks. Properly typed via `MemoryObjectReceiveStream` /
  `MemoryObjectSendStream` (TYPE_CHECKING-imported) so ty stays at
  `Found 0 diagnostics`.
- [x] New `kourai_project_root_var: ContextVar[Path | None]` (default
  `None`) so the `list_roots_callback` reads the active project root
  without threading it through every call signature. Wiring the
  executor side is the follow-on commit; this PR establishes the
  contextvar + factory.
- [x] `_kourai_list_roots(context)` callback returns
  `ListRootsResult(roots=[Root(uri=FileUrl(root.as_uri()),
  name="project_root")])` when the contextvar is set,
  `ListRootsResult(roots=[])` when unset (honest "we have no roots
  right now" rather than the SDK default's "we don't support
  roots"). `RootsCapability(listChanged=True)` declared automatically
  by the SDK because the callback is non-default.
- [x] `client_info=Implementation(name="kourai-khryseai",
  version="0.1.0")` so server-side observability sees a real client
  name instead of the SDK default `"mcp"`.
- [x] Refactored the three existing async functions in
  `mcp_client.py` (`query_context7`, `create_memory_entities`,
  `search_memory_nodes`) to construct sessions through the factory.
  Today's call sites don't operate on files, so declaring roots
  changes nothing for them — but preempts the "host that lies" issue
  when kourai-forge-mcp lands in Change 2.
- [x] 5 unit tests in `tests/unit/test_mcp_client.py`:
  - `TestBuildClientSession::test_factory_wires_kourai_list_roots_callback`
    — verifies `session._list_roots_callback is _kourai_list_roots`
    AND `is not _default_list_roots_callback` (the predicate the SDK
    uses to decide whether to declare the capability).
  - `TestBuildClientSession::test_factory_does_not_supply_elicitation_or_sampling_callbacks`
    — verifies elicitation + sampling stay at SDK defaults so those
    capabilities are NOT declared (no lying about supporting them).
  - `TestBuildClientSession::test_factory_supplies_kourai_client_info`
    — verifies override of SDK default `Implementation(name="mcp", ...)`.
  - `TestKouraiListRoots::test_returns_empty_list_when_contextvar_unset`.
  - `TestKouraiListRoots::test_returns_single_root_when_contextvar_set`
    (tmp_path fixture, full URI roundtrip via `Path.as_uri()`).
- [x] All 31 tests in `test_mcp_client.py` green; full unit suite
  `2679 passed`. `make lint` ends `Found 0 diagnostics`.
- [x] **Follow-on (shipped 2026-04-27):** wired executor entry points
  (the existing `parse_project_root(user_input)` site in Techne /
  Metis / Kallos / Dokimasia executors) to call
  `kourai_project_root_var.set(parsed_root)` immediately after the
  parse — contextvar now populated for any MCP call further down the
  stack. 4 regression tests in `tests/unit/test_executors.py::TestExecutorsSetKouraiProjectRootVar`
  patch the first downstream async call after the set with a capture
  fixture, then assert `kourai_project_root_var.get() == tmp_path`.
  Hephaestus uses `extract_project_root` (different function — the
  host-side parse) and stays untouched; specialist agents are where
  forge tools land, so they're the right wiring point.

### Change 2 — `mcp_servers/forge/server.py` stdio scaffold ✅ 2026-04-27

- [x] New `mcp_servers/forge/` workspace package
  (`kourai-mcp-forge`, version 0.1.0) using `FastMCP("kourai-forge")`
  over stdio — same pattern as the existing `mcp_servers/shell/`
  but depends on `kourai-common` for the forge tool handlers.
- [x] Tools mirror `kourai_common.forge_tools` exactly: `read_file`,
  `write_file`, `edit_file`, `delete_file`. NOT `run_command` —
  shell concerns stay in the shell MCP server; the forge server is
  files-only.
- [x] Each tool resolves the player's project root from
  `ctx.session.list_roots()` via the new `_resolve_project_root`
  helper, then delegates to the existing
  `kourai_common.forge_tools` async handler with `project_root=`
  injected. Path safety / `validate_file_path` / `PathViolation`
  is single-sourced — the MCP layer is purely protocol wiring.
- [x] No roots declared / empty list / list_roots raises → tool
  short-circuits with a clear ERROR string pointing the contributor
  at `kourai_project_root_var` so the unset-contextvar diagnosis is
  legible. Multiple roots → first wins with a log warning.
- [x] No tool annotations beyond name + description — the
  2025-11-25 spec explicitly marks tool annotations untrusted
  unless the server is trusted, and the host's permission gate
  remains source of truth.
- [x] 13 unit tests in `tests/unit/test_forge_mcp.py`:
  - registration: `mcp.list_tools()` returns exactly the 4 expected
    names;
  - `_resolve_project_root` happy / empty / error / multi-root paths;
  - end-to-end per tool against `tmp_path`-scoped Context (write
    creates file, edit replaces unique match + rejects ambiguous,
    delete removes + no-op-when-absent, read returns line-numbered
    contents, write rejects path-escape).
- [x] `mcp_client.py` module docstring updated with the new server
  in the "MCP Servers in Kourai Khryseai" list.
- [ ] **Live verification (deferred to Change 3):** specialist
  containers connect to `kourai-mcp-forge` via stdio, declare
  `[project_root: ...]` mid-pipeline, and watch a forge tool call
  flow end-to-end. Today's tests cover the wiring; Change 3 closes
  the loop.

### Change 3 — Specialist clients via the MCP bridge

Split into incremental sub-PRs to keep blast radius small. 3a establishes
the bridge layer (purely additive, no caller changes); 3b/3c/3d migrate
one specialist each with a green-CI gate between, so a regression in any
one specialist surfaces in isolation.

#### Change 3a — `mcp_bridge` module + live forge subprocess roundtrip ✅ 2026-04-27

- [x] New `shared/src/kourai_common/mcp_bridge.py` with
  `mcp_tool_bridge(server_params)` async context manager: launches the
  MCP server via stdio, opens a kourai client session (declares
  `roots`), fetches `tools/list`, and yields an `MCPToolBridge` whose
  `tools` are OpenAI-shaped schema dicts and whose `tool_handlers`
  proxy each call through `session.call_tool`.
- [x] `forge_tool_bridge()` convenience: launches
  `uv run --no-active kourai-mcp-forge` for the standard kourai case.
- [x] `mcp_tool_to_openai_schema(tool)` converts MCP `Tool` (name +
  description + inputSchema) to LiteLLM-compatible
  `{"type": "function", "function": {...}}`.
- [x] Handler factory wraps `session.call_tool` and surfaces server
  errors verbatim if they're already prefixed with `ERROR:` (forge
  server's convention), wraps unprefixed errors with `ERROR: ` so
  the existing `chat_with_tools` error path keeps working.
- [x] **Live integration tests** in
  `tests/unit/test_mcp_bridge.py::TestForgeBridgeLive`: launch the
  actual `kourai-mcp-forge` subprocess via `uv run`, set
  `kourai_project_root_var` to a `tmp_path`, write a file via the
  `write_file` MCP tool, read it back via `read_file`, verify the
  file landed in the right place AND the path-escape attempt
  (`../escape.py`) gets rejected with an ERROR. End-to-end stack
  validation: kourai declares `roots`, server asks `roots/list`,
  kourai responds with the contextvar, server validates the path,
  result flows back through the bridge.
- [x] 11 unit tests total in `test_mcp_bridge.py`; all 2717 unit
  tests pass; `make lint` ends `Found 0 diagnostics`.
- [ ] Purely additive: no specialist callers wired yet — both code
  paths coexist on main until 3b/3c/3d.

#### Change 3b/c/d — Migrate Techne / Kallos / Dokimasia to the MCP bridge ✅ 2026-04-27

Combined into a single PR after web research (April 2026 MCP best
practice) confirmed that STDIO sessions are inherently stateful — one
`forge_tool_bridge()` `async with` block holds the subprocess for the
entire `chat_with_tools` lifetime (typically 10+ tool calls across a
multi-iteration LLM loop), so the subprocess startup amortizes across
all tool calls in that loop. The original "subprocess-per-tool-call"
perf concern dissolved once that landed.

- [x] `agents/techne/agent.py::apply_code_changes` swaps
  `tools=FORGE_TOOL_SCHEMAS, tool_handlers=FORGE_TOOL_HANDLERS,
  handler_context={"project_root": project_root}` for
  `tools=bridge.tools, tool_handlers=bridge.tool_handlers` inside
  an `async with forge_tool_bridge() as bridge:` block. Same shape
  applied to `agents/kallos/agent.py::apply_lint_fixes` and
  `agents/dokimasia/agent.py::apply_test_fixes`.
- [x] Each migrated function defensively sets
  `kourai_project_root_var` from its `project_root` parameter
  before opening the bridge, so a standalone caller (test / direct
  invocation) gets correct scoping even if no executor populated
  the contextvar from `[project_root: ...]`.
- [x] `handler_context` removed entirely — the MCP server reads
  `project_root` via `roots/list` (Change 1's `_kourai_list_roots`
  reads the contextvar). Single-source: project_root flows through
  one channel, not two.
- [x] Test mocks updated — 4 `TestApplyCodeChanges` tests in
  `test_techne.py` rewritten to also patch `forge_tool_bridge` with
  a stub yielding `MCPToolBridge(tools=[], tool_handlers={})`;
  4 `TestApply{Lint,Test}FixesForwardsCallback` tests in
  `test_tool_call_streaming.py` similarly. New `test_techne.py::
  TestApplyCodeChanges::test_sets_kourai_project_root_var_for_forge_subprocess`
  regression-guards the defensive contextvar set.
- [x] All tests in `test_techne.py`, `test_tool_call_streaming.py`,
  `test_executors.py`, `test_mcp_bridge.py` (incl. live forge
  subprocess roundtrip) green; full unit suite `2735 passed`;
  `make lint` ends `Found 0 diagnostics`.
- [x] **Cleanup (shipped 2026-04-27 in #60):** static
  `FORGE_TOOL_SCHEMAS` / `FORGE_TOOL_HANDLERS` exports +
  `TestSchemaShape` deleted. Stale references in `mcp_bridge.py` /
  `forge_tools.py` / `agents/techne/agent{,_executor}.py` /
  `tests/unit/test_techne.py` / `tests/unit/test_forge_tools.py`
  docstrings + comments cleaned up in a follow-on deslop pass.
- [ ] **Live verification (deferred):** specialist container connects
  to `kourai-mcp-forge` via stdio, declares
  `[project_root: ...]` mid-pipeline, and watches a forge tool
  call flow end-to-end. Today's tests cover the wiring; live
  smoke covers the full A2A → executor → contextvar → bridge →
  subprocess → roots/list → forge tool roundtrip path under
  real LLM tool calls.

### Change 4 — Elicitation client capability + INPUT_REQUIRED bridge

**Reframed 2026-04-28.** The original "migrate CONFIRM_ORDER to
`elicitation/create`" framing was a category mismatch — Hephaestus
is an A2A endpoint and `INPUT_REQUIRED` is the correct A2A primitive
for its pre-pipeline gate. MCP `elicitation/create` is for
**server-to-client** asks during a tool call, so its right home is
the forge MCP server (and future ones) wanting to ask the player
mid-execution. CONFIRM_ORDER stays on A2A; this change builds the
infrastructure for MCP-server-side elicitations to round-trip through
kourai's existing INPUT_REQUIRED rendering layer.

**Architecture (revised mid-design 2026-04-28).** First sketch routed
the answer through Hephaestus and a fresh A2A task back to the
specialist, but A2A's `INPUT_REQUIRED` is final-by-default and breaks
the streaming relay — Hephaestus would disconnect from the original
specialist task before the work completed, orphaning the artifact.

The cleaner model: emit the elicitation as a normal streaming
`working_status` (NOT `INPUT_REQUIRED`), let Hephaestus relay it
unchanged, have the CLI render an inline prompt without ending the
A2A task, and send the answer **directly to the specialist** via a
new HTTP endpoint. The specialist's HTTP server is already running
under uvicorn — adding one Starlette route for elicitation responses
is cheap, and it sidesteps the stranded-task problem entirely
because the original `execute()` never gives up its connection.

```
forge tool calls ctx.elicit("confirm delete?")
  ↓ MCP elicitation/create
specialist's _kourai_elicitation_callback
  ↓ creates Future, registers in module-level dict by elicitation_id
  ↓ emits streaming working_status: "[ELICIT:{id}:techne] confirm delete?"
  ↓ awaits Future (5min timeout)
Hephaestus's existing stream-relay forwards the working_status
  ↓ no special handling — passes through as a normal status update
CLI receives the streaming event, parses [ELICIT:{id}:techne],
  ↓ renders inline yes/no prompt while still subscribed to the stream
  ↓ player answers
CLI POSTs to {specialist_url}/internal/elicitation/{id}
  with body {"action": "accept" | "decline" | "cancel"}
  ↓ Specialist URL resolved via get_agent_url("techne")
specialist's Starlette route resolves _PENDING_ELICITATIONS[{id}]
  ↓ no new A2A task, no Hephaestus involvement on resume
The original (still-running) execute()'s Future resolves
  ↓ callback returns ElicitResult to MCP server
forge tool proceeds with the (now-confirmed) action
  ↓ work continues, artifact streams back through Hephaestus to CLI
```

**Why this works where the first sketch didn't.** A2A has no
mid-handler pause primitive — once `execute()` enters, it must run to
completion or return. Sending `INPUT_REQUIRED final=True` mid-task
ends Hephaestus's connection to the specialist, so any work after the
elicitation never reaches the player. The HTTP-side-channel pattern
keeps the specialist's `execute()` running (just blocked on the
Future), the streaming connection stays open, and the answer arrives
out-of-band via a different request handler on the same uvicorn
instance.

**Workstreams (this PR).**

- [x] `shared/src/kourai_common/elicitation.py` — module-level
  `_PENDING_ELICITATIONS` registry, `_kourai_elicitation_callback`,
  `resolve_elicitation` API, `kourai_elicitation_emitter_var` +
  `kourai_elicitation_specialist_var` ContextVars,
  `attach_elicitation_route` Starlette helper, marker codec.
- [x] `shared/src/kourai_common/mcp_client.py` — wires the callback
  into `build_client_session()`; section comment updated.
- [x] `tests/unit/test_mcp_client.py` — flipped: elicitation IS
  supplied; sampling test split out separately.
- [x] `tests/unit/test_elicitation.py` — 33 tests covering marker
  codec, registry lifecycle, callback paths (URL/schema/empty),
  timeout cleanup, two-pending concurrency, HTTP route 204/400/404
  paths, and an end-to-end round-trip exercising callback +
  `attach_elicitation_route` together.
- [x] Specialist executors (techne / kallos / dokimasia) — set
  the two contextvars before the LLM loop; emitter wraps
  `send_working_status` so the elicitation marker rides the same
  streaming pipe Hephaestus is already consuming.
- [x] Specialist `__main__.py` (techne / kallos / dokimasia) —
  call `attach_elicitation_route(app)` after `server.build()` so
  the CLI's POST to `/internal/elicitation/{id}` resolves the
  pending Future. Returns 204 hit / 404 stale / 400 malformed.
- [x] `hosts/cli/streaming.py` — detect `[ELICIT:{id}:{agent}]` in
  streaming `working_status` text (any prefix tolerated; the marker
  is found via `text.find("[ELICIT:")`). Render inline yes/no with
  `[y/n/cancel]`, POST the answer to
  `{get_agent_url(agent)}/internal/elicitation/{id}`. Stream stays
  open the whole time, so the eventual artifact still reaches the
  player.
- [x] **No changes to Hephaestus.** Its existing relay
  (`agent_executor.py:277-282`) forwards specialist `working_status`
  unchanged, which is exactly what we need.

**Out of scope (deferred to a follow-on PR).**

- No forge MCP server tool currently calls `ctx.elicit()`. The
  bridge is fully landed but unused in production until the first
  caller arrives — a natural candidate is `delete_file` confirming
  destructive deletes against an uncommitted-changes guard, or a
  future deploy MCP server confirming a release. The end-to-end
  test in `test_elicitation.py::TestEndToEnd` proves the round-trip
  works without needing a live forge subprocess.

**Out of scope (later PRs).**

- No forge MCP server tools currently call `ctx.elicit()`. Wiring the
  first real caller (e.g., `delete_file` confirming destructive
  deletes against uncommitted changes) is a follow-on PR. The bridge
  in this PR is end-to-end testable via a synthetic caller in
  `tests/unit/test_elicitation.py`.
- M13's `CONFIRM_ORDER` stays on A2A; not migrated.
- Form-schema mode (`requestedSchema` with structured input fields)
  is supported by the SDK but the CLI bridge in this PR handles only
  plain-text-confirm elicitations. URL-mode is decline-only.

---

## Notes / open questions

- **Why stdio, not streamable-HTTP?** MCP's 2026 roadmap prioritises
  streamable-HTTP scalability, but stdio is the simpler default and the
  only transport every existing MCP host speaks today (Claude Code,
  Cursor, IDE plugins). Move to streamable-HTTP when we want a single
  forge server shared across multiple host machines — not a dev-loop
  need.

- **Why declare capabilities incrementally rather than all at init?**
  The MCP Python SDK gates capability declaration on callback presence
  (`ClientSession.initialize()` only declares `roots` / `elicitation`
  / `sampling` when the corresponding callback is non-default — see
  `mcp/client/session.py:148-188`). The default callbacks return
  `ErrorData(INVALID_REQUEST, "...not supported")`, so an
  all-three-with-stubs approach would technically declare the
  capability but lie about supporting it. Better to declare each
  capability exactly when its real implementation lands: `roots` now
  (Change 1), `elicitation` with Change 4 (INPUT_REQUIRED routing),
  `sampling` when the first caller exists. Cost of wrong-direction is
  asymmetric — a host that under-declares loses some server features;
  a host that over-declares produces protocol errors when servers try
  to use the capability.

- **MCP spec version pinned to 2025-11-25.** The spec drift watcher
  cron (`scripts/watch_protocols.py`) will flag any subsequent
  revision; M2 scope assumes today's spec. Tool annotations being
  explicitly marked untrusted is a 2025-11-25 thing — predates would
  be unsafe to assume.

- **Order vs. dependency.** Change 1 is the design-time gate; Change 2
  follows directly. Change 3 needs Change 2 done. Change 4 is
  independent of 3 once 2 is up — could ship in parallel.

---

## Up next (queued, not yet active)

- **Plan Mode toggle (Cline-style)** — persistent planning mode.
- **Background memory consolidation (Mneme "autoDream")** — pairs
  with the just-shipped `/compact`.
- **Custom-agent-via-markdown registration (OpenCode-style)** —
  long-term direction; wait until M2 lands.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt).
- **M15** (forge logging architecture) — operational hygiene; pairs
  naturally with M16's just-shipped trace-ID change since both touch
  `setup_logging`.
- **M5** (UID alignment for forge worktrees) — would let us drop
  the `safe.directory '*'` workaround from #42.
- **M7** (a2a-sdk 1.0.x migration) — the watcher's a2a-sdk-pypi
  entry will fire when 1.0.x stabilises and we should flip the
  pin. The `Message.metadata` migration item is queued under M7's
  scope as a follow-on once the SDK pin flips.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
- **M17** (HOTL answer persistence — project-scoped facts).
- **M16 follow-ons:**
  - Live trace-ID-in-Dozzle smoke (Change 1 unit-tested but worth
    eyeballing in a real `make up` + smoked pipeline).
