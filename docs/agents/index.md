# The Agents

Every agent in Kourai Khryseai is an **independent HTTP server** that exposes an [A2A Agent Card](https://a2a-protocol.org). Rather than running autonomously, each agent shows its work in real-time, asks clarifying questions when decisions matter, and participates in feedback loops with you and other agents.

The system has **10 agents** organized into three tiers:

| Tier | Agents | Purpose |
|------|--------|---------|
| **Core Specialists** | Hephaestus, Metis, Techne, Dokimasia, Kallos, Mneme | Software development pipeline |
| **Companion Spirits** | Puck, Cupid | Player guidance and relationship coaching |
| **Quality Validators** | Aidos, Aletheia | Language quality and factual accuracy |

Hephaestus discovers specialists by fetching their cards at connection time, enabling runtime composition rather than hardcoded integrations. Per-agent detail — pipeline behaviors, file layouts, ports — lives in the [Agents Reference](specialists.md).

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

## @Mention Routing { #mention-routing }

Any agent responds to `@<full-name>` from any host (`@hephaestus`,
`@aidos`, `@aletheia`, …). The eight pipeline-frequent agents also
carry shorthand aliases, expanded in `agents/hephaestus/agent.py`
(`_MENTION_ALIASES`):

| Shorthand | Resolves to |
|---|---|
| `@heph` / `@hephaestus` | hephaestus |
| `@met` / `@metis` | metis |
| `@tech` / `@techne` | techne |
| `@doki` / `@dokimasia` | dokimasia |
| `@kal` / `@kallos` | kallos |
| `@mne` / `@mneme` | mneme |
| `@puck` | puck |
| `@cupid` | cupid |

Aidos and Aletheia are reachable via `@aidos` / `@aletheia` (no shorter
alias today — both are quality validators that run inside pipelines
rather than getting summoned ad-hoc).
