# The Agents

Every agent in Kourai Khryseai is an **independent HTTP server** that exposes an [A2A Agent Card](https://a2a-protocol.org). Rather than running autonomously, each agent shows its work in real-time, asks clarifying questions when decisions matter, and participates in feedback loops with you and other agents.

The system has **10 agents** organized into three tiers:

| Tier | Agents | Purpose |
|------|--------|---------|
| **Core Specialists** | Hephaestus, Metis, Techne, Dokimasia, Kallos, Mneme | Software development pipeline |
| **Companion Spirits** | Puck, Cupid | Player guidance and relationship coaching |
| **Quality Validators** | Aidos, Aletheia | Language quality and factual accuracy |

Hephaestus discovers specialists by fetching their cards at connection time, enabling runtime composition rather than hardcoded integrations.

---

## 🔥 Hephaestus — Orchestrator

<img src="../assets/avatars/hephaestus_neutral.png" class="specialist-avatar" alt="Hephaestus — Master of the Forge">

**Port `10000`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/hephaestus/`](https://github.com/ajbarea/kourai_khryseai/tree/main/agents/hephaestus)

The brain of the system. Receives user requests, uses its LLM to decide which specialists to invoke and in what order, then executes the pipeline sequentially while streaming progress back to the host.

**Key behaviors:**

- **LLM-based routing** — Analyzes the user's natural language request against pipeline templates to select agents. Falls back to `mneme` if the LLM returns nothing valid.
- **Direct Agent Mentions** — If a request starts with `@<agent>`, Hephaestus bypasses LLM routing and initiates a direct 1-on-1 pipeline with that specialist. All 10 agents are @-mentionable.
- **ASK_USER & Proactive UX** — If the request is ambiguous, responds with `ASK_USER: <question>`. Provides A/B multiple-choice options to reduce cognitive load.
- **Sequential execution** — Calls each specialist via A2A `message/send` with `streaming=True`. Context accumulates from one agent to the next while intermediate status messages stream to the host.
- **Kallos-Techne feedback loop** — When both are in the pipeline and Kallos finds lint issues, automatically loops Techne (fix) → Kallos (re-check) up to `MAX_ITERATIONS` times.
- **Affinity tracking** — Updates player affinity with the responding agent after each interaction.
- **Virtue updates** — Increments `sophia` and `synergy` on successful pipeline completion.
- **Jealousy detection** — Monitors affinity gaps between agents and routes to Cupid when jealousy triggers.
- **Graceful degradation** — If a specialist is unreachable, it's skipped and the pipeline continues.

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
| `"@puck, how's it going?"` | puck (direct 1-on-1) |

**Files:**

| File | Purpose |
|---|---|
| `routing_agent.py` | LLM routing prompt, pipeline execution, Kallos-Techne loop |
| `remote_connections.py` | `RemoteAgentConnection` wrapper, `AgentInputRequired` exception |
| `agent_executor.py` | A2A bridge, emoji status messages, affinity/virtue updates, OTEL spans |
| `__main__.py` | AgentCard, server startup |

---

## Agent Discovery

Each agent exposes an **A2A Agent Card** — a JSON document at `/.well-known/agent-card.json` describing:

- Agent name, description, and version
- Skills (capabilities the agent advertises)
- Supported input/output content types
- Streaming capability
- Server URL

Hephaestus fetches these cards when connecting to specialists, enabling runtime discovery rather than hardcoded integration.

```bash title="Inspect any agent's card"
curl http://localhost:10005/.well-known/agent-card.json | python -m json.tool
```

---

## @Mention Routing

All agents support direct @-mention from any host:

| Shorthand | Resolves to | Unique? |
|-----------|-------------|---------|
| `@heph` | hephaestus | Yes |
| `@tech` | techne | Yes |
| `@kal` | kallos | Yes |
| `@met` | metis | Yes |
| `@doki` | dokimasia | Yes |
| `@mne` | mneme | Yes |
| `@puck` | puck | Yes |
| `@cup` | cupid | Yes |
| `@aid` | aidos | Yes |
| `@ale` | aletheia | Yes |
