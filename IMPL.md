# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-29 · Working on: **M17 Phase 1 — HOTL answer
persistence (project-scoped facts)**

## Why

Kourai is being extended with Federated Learning features per the
research-advisor pivot — the orchestration layer needs to start
gathering structured player data for FL training. M17's Phase 1 is the
fast structured-recall layer that closes the loop between M13's
`AgentInputRequired` (already shipped) and the `kourai_common.facts`
knowledge graph (already shipped, currently unused for HOTL pauses).
Phase 1 ships the project-scope axis so a clarifying answer in
project A is recalled by Metis in project A — and is NOT recalled when
the player switches to project B. That cross-session, cross-project
discrimination is the property worth shipping. Memoir continues to be
the FL training-data ground-truth in parallel; facts are the agent-
facing recall surface.

ROADMAP M17 (lines 350-559) carries the full design rationale, anti-
overclaim ledger, and Phase 1/2 split.

## Decisions (re-anchored from ROADMAP)

- **Reuse `facts.py`, not `player_memories`.** `kourai_common.facts`
  already implements the right shape (`<FACT>` tag extraction,
  `PlayerFact` / `KnowledgeGraphFact`, `store_facts`,
  `get_relevant_facts_for_enrichment`, `build_fact_context`). Adding a
  `project_id` axis is materially cheaper than building a parallel
  project-preference layer on `player_memories`.
- **Prompt enrichment, not pre-pause hooks.** `build_fact_context()`
  already runs at planning time; adding a `project_id` filter there
  gives every specialist project-scoped recall for free — no per-agent
  patches.
- **Phase 1 = items 1-5 only.** Items 6-9 (visible recall narrator,
  `/preferences` CLI, telemetry attributes, confidence decay) defer to
  Phase 2 once Phase 1 is in production and we know what's load-bearing.

## Scope (Phase 1)

1. **`project_id` axis on facts.** Optional `project_id: str | None`
   field on `PlayerFact` + `KnowledgeGraphFact`. Extend the `<FACT>`
   regex to parse a `project_id="..."` attribute. `store_facts()`
   persists it; `get_relevant_facts_for_enrichment()` accepts a
   `project_id` filter and prefers project-scoped facts over global at
   the same retrieval score.
2. **`derive_project_id(project_root)`** in `projects.py`. Stable
   sha256 truncated to 16 hex of the absolute, normalised path. Avoids
   leaking host-absolute paths into fact bodies, survives the player
   moving the repo on disk, gives a clean tag value for telemetry.
3. **HOTL → facts write path.** New helper
   `synthesise_fact_from_pause(player_id, project_id, preference_kind,
   player_response, source_agent)` in `hooks_interaction.py` (peer to
   `extract_memories_from_interaction`). Wired into
   `run_post_task_hooks` so it fires when the most recent task
   resolved an `INPUT_REQUIRED` AND the originating agent tagged the
   pause with a `preference_kind`. Synthesises a
   `PlayerFact(category="preference", confidence="high",
   project_id=..., body="<kind>: <answer>", source_agent=...)` and
   calls `store_facts()`.
4. **Pause-kind tagging.** Metis's `INPUT_REQUIRED` token grows a
   `preference_kind` attribute (M13 `CONFIRM_ORDER: <tier>` mirror).
   Phase 1 closed-set vocabulary: `coverage_target`, `python_version`,
   `style_rules`, `commit_style`, `test_framework`. Broaden later.
5. **Read path.** `build_fact_context()` filtered by active
   `project_id`, prefers project-scoped over global facts at the same
   retrieval score.

## Out of scope (Phase 2 — separate milestone)

- Visible recall narrator line ("📐 Metis: Using your stored coverage
  target (80%).")
- `/preferences` CRUD CLI (`/prefs`, `/memory project` aliases)
- Telemetry span attributes (`kourai.fact.recalled`,
  `kourai.fact.kinds`)
- Confidence decay (`PROJECT_FACT_DECAY_DAYS = 90`)

## Definition of done (Phase 1)

A HOTL answer in project A persists, is recalled in the same agent on
the next run for project A, AND is NOT recalled when the player
switches to project B. End-to-end test exercising the full path
(`AgentInputRequired` → `synthesise_fact_from_pause` → `store_facts` →
next-session `build_fact_context` with project filter) demonstrates
the property.

## Order of execution

1. **Item 2 first** (`derive_project_id`) — dependency-free pure
   function with a clean test surface. Ship as standalone PR.
2. **Item 1** (`project_id` axis on `PlayerFact` /
   `KnowledgeGraphFact` / `<FACT>` regex / `store_facts`) — depends on
   item 2 for the canonical id.
3. **Item 5** (read-path filter on `get_relevant_facts_for_enrichment`
   + `build_fact_context`) — extends item 1.
4. **Item 4** (Metis `INPUT_REQUIRED` `preference_kind` attribute) —
   independent of 1-3 on the agent side; can ship in parallel.
5. **Item 3** (`synthesise_fact_from_pause` post-task hook) — the
   integrator that needs items 1, 2, 4. Ship last with the end-to-end
   property test.

Each step ships as a PR with tests + `make lint` green + IMPL update.

---

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

## Up next (after Phase 1 lands)

Other queued items remain in the prior IMPL "Up next" list — pulling
them up requires explicit AJ nomination per UX/DX-default convention.

- **Live VN smoke** — `make vn` exercises both fixes from PR #66.
- **`docs/architecture/puck-first-run-tutorial.md`** — pairs with the
  M6 player-onboarding theme (committed in `2ad93c1`).
- **M17 Phase 2** — visible recall + `/preferences` + telemetry +
  decay. Defer until Phase 1 has miles on it.
- **M5 / M7 / M12 / M15 / M6 follow-ons** — see the prior IMPL or
  ROADMAP for scope.
