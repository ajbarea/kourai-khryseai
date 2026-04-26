# Hephaestus — Forge Master / Orchestrator

> Greek Ἥφαιστος, the smith god. Routes player requests through the
> specialist pipeline, narrates handoffs in-character, and maintains
> the **Forge Transcript** — the shared dialogue history every
> downstream agent reads.

## Responsibility

Hephaestus is the only agent the host hosts (CLI, GUI, VN) speak to
directly. He uses an LLM to decide which specialists to invoke and
in what order, then orchestrates them as a "forge party" where each
agent sees the prior transcript before contributing. He also
serves as the in-character narrator between handoffs and runs the
Kallos↔Techne fix loop when lint catches Techne's code.

## A2A surface

| Field | Value |
|---|---|
| Port | `10000` |
| Skill ID | `forge_master` |
| Streaming | Yes — re-streams every specialist's `working_status` events |
| `INPUT_REQUIRED` | Yes — propagates from any specialist that asks for input |
| Project root | Optional (parsed from `[project_root: …]` if present; otherwise the Kourai source tree) |
| Relationship tiers | Optional `[relationship_tiers: name=score,…]` block from VN host |

**Output artifact** — the LAST specialist's artifact is forwarded
to the player. Hephaestus doesn't add an artifact of his own.

## Tools

Hephaestus does NOT drive `chat_with_tools`. His routing turn uses
`chat()` only — output is a comma-separated agent list, a `CHAT:`
response, or `ASK_USER:`. The actual file operations happen inside
the specialist agents he calls.

## Pipeline neighbors

- **Routes from:** All player-facing hosts (CLI, GUI, VN bridge).
- **Routes to:** Any of `metis`, `techne`, `dokimasia`, `kallos`,
  `mneme`, plus companion spirits `puck` and `cupid`.
- **Templates:** `"implement X"` → metis → techne → dokimasia →
  kallos → mneme. `"fix bug X"` skips planning. `"clean up X"` is
  kallos-only. See `ROUTING_PROMPT` in `agent.py` for the full table.

## Key files

- `agent.py` — `ROUTING_PROMPT`, `HEPH_HANDOFFS` (in-character
  narration lines), `determine_pipeline()` (LLM routing call),
  `execute_pipeline()` (the orchestration loop), the Kallos↔Techne
  fix-loop, GitHub repo search.
- `agent_executor.py` — A2A bridge. Drives `execute_pipeline` and
  forwards every yielded `(agent_name, status, output)` tuple as
  a `TaskStatusUpdateEvent` so hosts can re-render in real time.
- `remote_connections.py` — Per-specialist `RemoteAgentConnection`
  wrapper that consumes the SSE stream and yields
  `("status"|"result", text)` tuples to `execute_pipeline`.
- `__main__.py` — server entrypoint and AgentCard registration.

## Smoke recipe

```bash
make up
make cli
> implement a CSV exporter for the events module
```

**What to expect.** Hephaestus narrates the routing decision
(`"Metis! Draw up the plans. And no improvising."`), then streams
each specialist's `working_status` events as they fire. The final
artifact is whatever the last agent in the pipeline produced
(usually Mneme's commit message group).

## Persona notes

Hephaestus is gruff, protective, and proud of the maidens he built.
His warmth scales with player affinity — at low tiers he's terse
and task-focused; at high tiers he cracks forge metaphors and
shows fatherly pride in the maidens' work. The persona enrichment
is appended to `ROUTING_PROMPT` per call by
`build_player_context(profile, "hephaestus", top_k_memories=4)`.
