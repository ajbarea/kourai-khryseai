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

### Change 1 — Init-handshake client capabilities (design-time gate)

**Why first.** MCP's `initialize` request is where a host advertises
which client capabilities it speaks (`roots`, `elicitation`,
`sampling`). The declaration shapes every server-side decision: a
server that knows the host has `roots` won't reinvent path validation;
a server that knows the host has `elicitation` won't bake confirmation
prompts into tool descriptions; a server that knows the host has
`sampling` can offload LLM calls back to the host instead of bundling
LiteLLM. Get this wrong and we either over-build (re-implementing what
the host already does) or under-build (papering over missing
primitives with text-tag hacks).

- [ ] **`roots`** declared in the host. Player's `project_root`
  becomes the sole declared root; the server's file-touching tools
  validate against the root list rather than re-implementing
  `validate_file_path`. Includes
  `notifications/roots/list_changed` so a `/project switch`
  mid-session re-scopes the server cleanly.
- [ ] **`elicitation`** declared. Spec-blessed analog of M13's
  homegrown `CONFIRM_ORDER` pause primitive. Once Change 4 lands,
  `INPUT_REQUIRED` flows through elicitation rather than the
  text-tag carrier — same UX, standard wire format, future
  MCP-aware hosts get the gate for free.
- [ ] **`sampling`** declared. Server-initiated LLM call back
  through the host. Useful if a future skill (e.g., a synth-test
  generator) wants to ask Hephaestus to classify intent without
  bundling its own LiteLLM client. Pairs with the existing YOLO
  toggle: `[yolo: on]` → auto-approve sampling; otherwise prompt
  per the spec's MUST-explicit-consent rule.
- [ ] Host-side capability advertisement wired into `MCPToolkit`'s
  init path. Verified via mock `initialize` request: response
  payload carries all three keys with shapes matching spec
  2025-11-25.

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

- **Why declare capabilities at init even if some won't be exercised
  immediately?** `roots` is used from day one. `elicitation` lands with
  Change 4. `sampling` may not have a caller for weeks. But the
  declaration is cheap and the cost of NOT declaring is that future
  servers see a host that lies about its capabilities — worse than
  papering over a missing capability. Declare what we actually
  support; leave the rest off.

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
