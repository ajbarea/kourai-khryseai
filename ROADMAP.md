# Kourai Khryseai — Roadmap

A public, living plan for where the forge is heading. Items here are either
**planned** (full detail) or **shipped** (one-liner with date). Whatever we're
*currently working on* lives in [IMPL.md](./IMPL.md) — when it lands, the
matching milestone here collapses to a single line under "Shipped".

Last reviewed: 2026-04-20 (M1 code shipped, awaiting Round 6 live smoke)

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
- `MCPToolkit` in `shared/src/kourai_common/mcp_client.py` upgraded from
  the current stub-returning placeholder to a real client (the SDK is
  already pinned at `mcp>=1.26.0`).
- Specialists invoke MCP via the toolkit; LiteLLM tool-use bindings reflect
  the MCP-served schemas.

References: [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture).
Current MCP spec version: **2025-06-18**.

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
- **Kokoro-only cutover (or intentional dual-provider lock-in):** the
  `edge-tts` dep in `hosts/gui` and `agents/hephaestus` carries a comment
  "remove once Kokoro is stable" that has been on the plan long enough to
  bake. Either commit to Kokoro (drop edge-tts, accept that Kokoro-only
  failures surface as silent crashes rather than fallback audio) or
  rewrite the comment to "intentional fallback — do not remove." Stale
  aspirational cleanups accumulate entropy; decide either way.
- **aiohttp override periodic re-verification:** `[tool.uv]
  override-dependencies = ["aiohttp>=3.13.4"]` was added for a CVE in a
  litellm transitive. Undocumented overrides fossilize; the
  `pyproject.toml` comment now explains the verification recipe, but
  someone has to actually run it. Add a quarterly calendar ping (or a CI
  job) that removes the override, runs `uv lock`, and reports whether
  the upstream pin has moved.
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

---

## Shipped

One-liner per item, newest first. Detail moves out of this file when work lands.

- 2026-04-20 — `/project` REPL flow + forge-session worktrees end-to-end (Round 1 happy path + Round 2 discard, both smoked against live Hephaestus)
- 2026-04-20 — `parse_and_apply_fixes` regex tolerates markdown-bold-wrapped headers and translates host paths to container paths
- 2026-04-20 — `ForgeSession.accept()` auto-commits uncommitted pipeline writes before fast-forward merge
- 2026-04-20 — Zero-arg `/project accept` and `/project discard` resolve the latest active session
- 2026-04-20 — `pytest -p no:cacheprovider` in Dokimasia eliminates the zombie `.pytest_cache` dir source (M5 stop-gap)
