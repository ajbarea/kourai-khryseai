# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-29 · Working on: **M17 Phase 2 — `/preferences` CRUD
shipped with project_id stability fix; confidence decay is the only
queued Phase 2 item**

## Recently shipped — M17 Phase 2 item 7 (`/preferences` CLI)

**Right-to-forget for project-scoped preference facts is live.** The
player can now list every stored preference for the active scope, set
any closed-vocab kind without re-asking, forget one kind, or wipe the
whole scope with `forget --all`. Aliased as `/prefs`. The CRUD writes
through the same `kourai_common.facts` axis Metis recalls from, so
overrides take effect on the next planning prompt without a restart.

**Project_id stability fix bundled in.** The Phase 1 implementation
derived the fact axis from `[project_root: …]`, but the REPL stamps
the per-session forge worktree there — `derive_project_id(workdir)`
changes every turn, so PAUSE-resolved facts never recalled across
sessions. New `[project_id: <stable>]` forge tag carries the project-
rooted id alongside the worktree-rooted root tag. `streaming.py` now
prefers the explicit tag and falls back to deriving from project_root
for any caller that hasn't been updated. Without this fix the new
CLI would have shown an empty list for everyone.

26 new unit tests (10 facts CRUD + 13 CLI handler + 3 streaming-tag
preference). Suite at 2865 passing total.

## Earlier in the same session — M17 Phase 1 close-out

**The HOTL → facts loop is end-to-end live for one-time-per-project
preferences.** A clarifying answer in project A persists, surfaces in
Metis's planning prompt the next session for project A, and stays
hidden when the player switches to project B. Shipped across six PRs
(#81 / #82 / #84 / #85 / #86 / #87); 48 new unit tests; ROADMAP §M17
trimmed to the Phase 2 scope only.

What changed from the original sketch — three load-bearing notes worth
remembering for Phase 2:

- **`run_post_task_hooks` had no production call sites.** Item 3's
  ROADMAP plan ("wired into `run_post_task_hooks`…") was load-bearing
  on a layer that isn't actually integrated into the agent execution
  pipeline. The pragmatic answer: call `synthesise_fact_from_pause`
  directly from `hosts/cli/streaming.py` at the top of every turn, where
  Memoir already lives. Promoting it into a unified post-task hook
  layer once that layer is wired is sibling work — flagged as a
  follow-on under M5/M6 so it doesn't get lost.
- **Metis didn't actually call `build_fact_context`.** The ROADMAP
  Phase 1 design assumed every specialist's prompt was already
  enriched through `facts.py` — true for Puck and Cupid, not for
  Metis (who goes through `get_enriched_system_prompt` →
  `build_player_context` → `retrieve_relevant_memories`, which never
  touches facts.py). PR #87 closed that gap surgically by threading
  `player_id` / `project_id` kwargs into `create_spec` /
  `create_spec_stream`. Other specialists with the same shape
  (Techne, Kallos, Dokimasia, Hephaestus) inherit the gap until
  someone needs it — flagged as a follow-on, not blocking.
- **PAUSE token cross-turn state lives in-process.** A
  `kourai_common.pause_state` dict keyed by `context_id` carries the
  preference_kind from the paused turn to the resumed turn. Agent
  restart between pause and resume drops the classification; the
  player's answer still lands in Memoir as labeled FL training data
  so the loop fails soft, not silent. Cross-process persistence
  belongs in Phase 2's confidence-decay milestone.

## Notes / open questions (carry-over from M2 + M16)

- **MCP elicitation deferred-by-design.** The MCP Python SDK gates
  capability declaration on callback presence — declaring `elicitation`
  with a stub callback violates the "host that lies" anti-pattern that
  Change 1 was specifically built to avoid. Real-caller-driven only.
  When the first forge MCP tool wants `ctx.elicit()`, the architectural
  notes from the closed [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74)
  diff capture the round-trip design (HTTP side-channel from CLI to
  specialist via new Starlette route, asyncio Future registry,
  contextvar emitter); that's the implementation reference, not a plan
  to ship now.
- **Smoke 1 deferred — environmental.** The 2026-04-28 attempt
  reached "architecture verified" but missed the live LLM-driven
  write because Haiku read `read_file(".")` as a permission lockout
  and abandoned. PR #71 fixes that at every layer the model sees
  (TOOL USE prompts in techne/kallos/dokimasia, MCP schema docstring,
  runtime error message). Re-run is queued for whenever
  `api.anthropic.com` outbound from agent containers stabilises.
- **MCP spec version pinned to 2025-11-25.** The spec drift watcher
  cron (`scripts/watch_protocols.py`) will flag any subsequent
  revision; today's wiring assumes that spec. Tool annotations being
  explicitly marked untrusted is a 2025-11-25 thing.

## Up next

UX/DX is the default between milestones. Pulling any of these up
requires explicit AJ nomination per UX/DX-default convention.

- **Live M17 Phase 1 smoke** — exercise the loop in a real `make up`
  + REPL session: ask Metis to plan something where she'd reasonably
  pause on `coverage_target`, answer, then start a new context for
  the same project and see Metis quote the answer. Pairs with the
  next interactive run; no automated CI surface.
- **M17 Phase 2** — `/preferences` CRUD now shipped (this session).
  Items 6 (visible recall), 7 (CRUD CLI), and 8 (telemetry) are all
  live. Remaining: confidence decay (`PROJECT_FACT_DECAY_DAYS = 90`
  — facts older than 90d drop one tier high → medium → low → skip;
  re-confirmation resets the timer). Open design call when pulling
  this up: lazy decay computed inside
  `get_relevant_facts_for_enrichment` vs a periodic sweep over
  `player_memories`. Lazy is simpler and player-facing-equivalent;
  default to that unless a sweep gives free observability wins.
  ~100 lines + tests.
- **`run_post_task_hooks` integration** — the layer exists and is
  fully tested but no production code calls it. Wiring it into the
  CLI streaming path (sibling of Memoir append) gives every hook
  (`track_interaction`, `extract_memories_from_interaction`,
  `score_alignment`, `detect_work_patterns`,
  `try_advance_romance`, achievement checks) a real call site.
  Pulls `synthesise_fact_from_pause` back out of `streaming.py` at
  the same time.
- **Specialist parity for fact recall.** Metis now reads
  `build_fact_context` with project scope; Techne / Kallos /
  Dokimasia / Hephaestus do not. Sibling work to PR #87 — same
  five-line pattern per agent. Defer until a real PAUSE caller in a
  non-Metis specialist surfaces.
- **M7 — a2a-sdk 1.0.x migration.** Stable shipped 2026-04-20 (1.0.2
  current). Bigger than the existing dual-shape firewall in
  `shared/src/kourai_common/a2a_utils.py` anticipated — see that
  module's docstring for the full delta. Real scope:
  - Bump pin in 3 `pyproject.toml` files; bump
    `A2A_PROTOCOL_VERSION` from `"0.3"` to `"1.0"`.
  - Refactor every `__main__.py` (10 agents + vn-bridge) from
    `A2AStarletteApplication` to `create_agent_card_routes` +
    `create_jsonrpc_routes`; `A2AStarletteApplication` is removed.
  - Replace every `Part(root=TextPart(text=...))` /
    `Part(root=FilePart(file=FileWithBytes(...)))` construction with
    the flat 1.0 shape (`Part(text=...)` / `Part(raw=bytes,
    media_type="...")`); `TextPart` / `FilePart` / `DataPart` /
    `FileWithBytes` / `FileWithUri` are all removed.
  - Rename every `TaskState.<lower>` / `Role.<lower>` reference to
    the new `TASK_STATE_<UPPER>` / `ROLE_<UPPER>` form.
  - Update `RemoteAgentConnection.send()` and `streaming.py` event
    matching from `AsyncIterator[ClientEvent | Message]` to
    `AsyncIterator[StreamResponse]` with `HasField()` checks.
  - Migrate `ClientFactory.create_client()` (sync, deprecated) to
    `await create_client()`.
  - Audit `AgentCard` construction: `url` removed at top level,
    `examples` / `input_modes` / `output_modes` moved into
    `AgentSkill.examples` / `default_input_modes` /
    `default_output_modes`; `DefaultRequestHandler(...,
    agent_card=...)` is now required.
  - Server-side compat flag `enable_v0_3_compat=True` exists for
    legacy clients but is gated behind the application-setup
    refactor; not a bypass for the migration above.
  - Reference: upstream guide at
    `a2aproject/a2a-python/blob/main/docs/migrations/v1_0/`.
  - Suggested phasing: (i) refactor application setup behind the
    compat flag while still on 0.3 wire format, (ii) flip the pin
    and version constant, (iii) walk Part construction sites, (iv)
    walk enum renames, (v) migrate bracket-tag workarounds
    (`[project_root: ...]` etc.) to `Message.metadata`, (vi) tie
    `kourai_common.pause_state` migration to M17 Phase 2.
  - Defer scheduling until M17 Phase 1 has miles on it; bundling
    SDK churn next to a fresh Phase 1 doubles triage cost on any
    pause-resume regression.
- **Live VN smoke** — `make vn` exercises both fixes from PR #66.
- **`docs/architecture/puck-first-run-tutorial.md`** — pairs with the
  M6 player-onboarding theme (committed in `2ad93c1`).
- **M5 / M12 / M15 / M6 follow-ons** — see ROADMAP for scope.
