# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **Agent-level READMEs (M6 list item)**

---

## Plan-of-record

End state: a contributor reading `agents/<name>/pyproject.toml` (a
10-line stub that just imports `kourai-common`) can now also read
`agents/<name>/README.md` and learn what the agent actually does:
responsibility, A2A surface, tools, pipeline neighbors, key files,
smoke recipe, persona notes.

Per ROADMAP guidance: template-from-Kallos (smallest scope), then
propagate. Doing all 6 main pipeline agents in this PR; the 4
companion / spirit agents (Puck, Cupid, Aidos, Aletheia) can come
later when their roles in M-tier work crystallise.

### Step 1 — Kallos template ✅ 2026-04-26

- [x] `agents/kallos/README.md`: the template. Sections: header
      (Greek epithet + role), Responsibility, A2A surface (port,
      skill ID, streaming, INPUT_REQUIRED, project root, attachments),
      Output artifact, Tools, Pipeline neighbors, Key files,
      Smoke recipe, Persona notes.

### Step 2 — Propagate to the other 5 main agents ✅ 2026-04-26

- [x] `agents/hephaestus/README.md` — orchestrator role,
      `ROUTING_PROMPT` + `HEPH_HANDOFFS` callout, the Kallos↔Techne
      fix-loop reference.
- [x] `agents/metis/README.md` — planner, `chat_stream` not
      `chat_with_tools`, Context7 doc lookup.
- [x] `agents/techne/README.md` — coder, the agentic tool-use
      loop, the `tool_calls` log in the `code_changes` artifact.
- [x] `agents/dokimasia/README.md` — three-mode executor (write
      tests / run tests / E2E), pytest fix loop.
- [x] `agents/mneme/README.md` — scribe, `[Git Diff]` auto-collect,
      HOTL PR-creation flow.

### Step 3 — Live smoke (queued for next interactive session)

- [ ] Open each README in the GitHub UI — confirm no broken
      anchors, port numbers match `AGENT_PORTS` in `config.py`,
      smoke recipes copy-paste cleanly.
- [ ] If any contributor walks the docs after this lands, ask them
      whether the templates surface the right detail or feel
      bureaucratic.

---

## Notes / open questions

- **Why skip Puck / Cupid / Aidos / Aletheia?** Their executors
  exist but the M-tier work that exercises them (M6 ElevenLabs
  voice work, gossip/romance content polish) is still in flight —
  writing READMEs now risks documenting an in-flight design and
  having to rewrite them. Add them when the M6 entries crystallise.

- **`personality_baseline` reference in every README.** Each main
  agent's README ends with a Persona section that points at the
  `personality_baseline` block in `agent.py::SYSTEM_PROMPT`. There's
  no separate `persona/` module today — the tier-adaptive copy lives
  inside the prompt itself. If we ever extract that into its own
  module (per a hypothetical persona-refactor PR), update these
  references in one sweep.

- **Port numbers.** Each README quotes the agent's port (`10000` for
  Hephaestus, `10001` for Metis, etc.) from `AGENT_PORTS` in
  `shared/src/kourai_common/config.py`. When the port table changes
  (rare), grep for the port and update the matching READMEs.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line
  bump, also wants Round 6 smoke.
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  needs live docker testing.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped, needs live
  A2A smoke.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor on
  the board.
- **Companion / spirit READMEs** (Puck, Cupid, Aidos, Aletheia) —
  when M6 work crystallises.
