# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-27 · Working on:
[**M2 — Carve out `kourai-forge-mcp`**](./ROADMAP.md#m2--carve-out-kourai-forge-mcp) —
unblocked since M1 shipped 2026-04-26. M16 (observability DX uplift)
landed earlier today across PRs #47 / #48 / #49 + this PR (Mneme
`_OtelTraceFilter`, `make observe` quickstart, `docs/observability.md`,
`dev.dozzle.group` labels) — see ROADMAP `## Shipped` for the rollup.

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
- [ ] **Follow-on (queued, not in this PR):** wire executor entry
  points (the existing `parse_project_root(user_input)` site in
  Techne / Metis / Kallos / Dokimasia executors) to call
  `kourai_project_root_var.set(parsed_root)` so the contextvar is
  populated for forge-relevant calls. Today the var stays `None` and
  `_kourai_list_roots` returns an empty list — correct, just inert.

### Change 2 — `mcp_servers/forge/server.py` stdio scaffold

- [ ] New stdio-transport server using the `mcp` Python SDK.
- [ ] Tools list mirrors today's `agents.forge_tools` Python helpers:
  `read_file`, `write_file`, `edit_file`, `run_command`.
- [ ] `roots` validation in each file-touching handler — paths
  outside the declared roots get rejected with a clear error
  pointing at `notifications/roots/list_changed` for re-scoping.
- [ ] Tool annotations stay conservative — the 2025-11-25 spec
  explicitly marks annotations untrusted unless the server is
  trusted; the host's permission gate remains source of truth, not
  the server's self-described risk level.

### Change 3 — Specialist clients via `MCPToolkit`

- [ ] Techne / Kallos / Dokimasia executors swap
  `agents.forge_tools` imports for `MCPToolkit.get_client("forge")`
  calls.
- [ ] LiteLLM tool-use bindings reflect the MCP-served tool schemas
  (`tools/list` round-trips through `MCPToolkit`).
- [ ] One smoke per specialist: forge tool call lands at the server,
  the server validates the root, response surfaces back as a
  tool-result frame identical to today's local-Python-import shape.

### Change 4 — `INPUT_REQUIRED` over `elicitation`

- [ ] M13's `CONFIRM_ORDER` pause migrates from the text-tag carrier
  to the spec's `elicitation/create` request flow.
- [ ] T4 follow-up from M13 (`[forge_intent]` block on user message
  to specialists) lands as part of the elicitation payload rather
  than a separate text-tag — single channel, less drift surface.
- [ ] Player UX unchanged: same comms-window rendering, same
  `[yolo:` bypass.

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
  - Cross-link from `.claude/skill-context.md` to
    `docs/observability.md` so future agents consult the page
    before designing observability changes.
  - `scripts/watch_protocols.py kind="docker-tag"` digester for
    `amir20/dozzle`, `jaegertracing/jaeger`, `prom/prometheus` so
    future image drift surfaces automatically.
