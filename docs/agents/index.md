# The Agents

Every agent in Kourai Khryseai is an independent HTTP server that exposes an [A2A Agent Card](https://a2a-protocol.org) at `/.well-known/agent.json`. Hephaestus discovers specialists by fetching their cards at connection time.

---

## 🔥 Hephaestus — Orchestrator

**Port `10000`** · Claude Sonnet 4.6 · [`agents/hephaestus/`](https://github.com/ajbarea/Kourai_Khryseai/tree/main/agents/hephaestus)

The brain of the system. Receives user requests, uses its LLM to decide which specialists to invoke and in what order, then executes the pipeline sequentially while streaming progress back to the CLI.

**Key behaviors:**

- **LLM-based routing** — Analyzes the user's natural language request against pipeline templates to select agents. Falls back to `mneme` if the LLM returns nothing valid.
- **ASK_USER** — If the request is ambiguous, responds with `ASK_USER: <question>` instead of guessing.
- **Sequential execution** — Calls each specialist via A2A `message/send` with `blocking=True`. Accumulated context passes from one agent to the next.
- **Kallos-Techne feedback loop** — When both are in the pipeline and Kallos finds lint issues, automatically loops Techne (fix) → Kallos (re-check) up to `MAX_ITERATIONS` times.
- **Graceful degradation** — If a specialist is unreachable, it's skipped and the pipeline continues with remaining agents.

**Pipeline templates:**

| Request pattern | Agents selected |
|---|---|
| `"implement X"` | metis → techne → dokimasia → kallos → mneme |
| `"fix bug X"` | techne → dokimasia → kallos → mneme |
| `"add tests for X"` | dokimasia → kallos → mneme |
| `"clean up X"` | kallos → mneme |
| `"commit prep"` | mneme |
| `"plan X"` | metis |
| `"lint/format X"` | kallos |

**Files:**

| File | Purpose |
|---|---|
| `routing_agent.py` | LLM routing prompt, pipeline execution, Kallos-Techne loop |
| `remote_connections.py` | `RemoteAgentConnection` wrapper, `AgentInputRequired` exception |
| `agent_executor.py` | A2A bridge, emoji status messages, OTEL spans |
| `__main__.py` | AgentCard, server startup |

---

## Agent Discovery

Each agent exposes an **A2A Agent Card** — a JSON document at `/.well-known/agent.json` describing:

- Agent name, description, and version
- Skills (capabilities the agent advertises)
- Supported input/output content types
- Streaming capability
- Server URL

Hephaestus fetches these cards when connecting to specialists, enabling runtime discovery rather than hardcoded integration.

```bash
# Inspect any agent's card
curl http://localhost:10005/.well-known/agent.json | python -m json.tool
```
