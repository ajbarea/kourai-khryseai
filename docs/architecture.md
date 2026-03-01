# Architecture

## :material-sitemap: System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOU (CLI / UI)                           │
│                                                                 │
│  $ kourai "add CSV export to the dashboard"                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ A2A (message/stream — SSE)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   🔥 HEPHAESTUS (Orchestrator)                  │
│                        Port 10000                               │
│                                                                 │
│  Receives user requests, decides routing, manages pipelines.    │
│  Uses LLM to determine which specialist(s) to invoke and in    │
│  what order. Maintains conversation context across turns.       │
└────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │          │
     │ A2A      │ A2A      │ A2A      │ A2A      │ A2A
     ▼          ▼          ▼          ▼          ▼
┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
│ 📐      ││ ⚙️      ││ 🧪      ││ ✨      ││ 📜      │
│ METIS   ││ TECHNE  ││DOKIMASIA││ KALLOS  ││ MNEME   │
│ Planner ││ Coder   ││ Tester  ││ Stylist ││ Scribe  │
│ :10001  ││ :10002  ││ :10003  ││ :10004  ││ :10005  │
└─────────┘└─────────┘└─────────┘└─────────┘└─────────┘
     │          │          │          │          │
     └──────────┴──────────┴──────────┴──────────┘
                       │
              ┌────────┴────────┐
              │  MCP Servers    │
              │  (fs, git, sh)  │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  Jaeger (OTEL)  │
              │  :16686 (UI)    │
              │  :4318 (OTLP)   │
              └─────────────────┘
```

**Communication:**

- **User ↔ Hephaestus:** A2A `message/stream` (SSE) for real-time progress
- **Hephaestus ↔ Specialists:** A2A `message/send` (synchronous, `blocking=True`)
- **Handoffs:** Kallos ↔ Techne iterative loop (lint fail → fix → re-lint, max 3)
- **Observability:** All agents → Jaeger via OpenTelemetry (W3C Trace Context)

---

## :material-scale-balance: Key Decisions

### Why `a2a-sdk` directly, not AgentStack

AgentStack (IBM/BeeAI) requires Kubernetes via Lima VM. Windows support is second-class (needs WSL2). Frequent breaking changes — the healthcare example pins to a specific old version. 1,007 stars vs 50K+ for AutoGen.

**Decision:** `a2a-sdk` + Starlette + uvicorn. No K8s overhead for 6 Python web servers. No WSL2 dependency on Windows. Still fully A2A-compliant.

### Why A2A v0.4.0, not v1.0

v1.0 RC has major breaking changes: Part types unified, enums changed to SCREAMING_SNAKE_CASE, method names changed, well-known URL renamed, OAuth flows removed.

**Decision:** Pin `a2a-sdk>=0.3.0,<1.0`. Migrate to v1.0 when stable.

### Why LiteLLM

Model-agnostic: Claude for production, Ollama for free local dev. One interface, swap with an env var (`KOURAI_USE_LOCAL_MODELS=true`).

### Why Docker + Terraform

Each agent is an independent HTTP server. Docker gives reproducible builds, process isolation, one-command startup (`make docker-up`). Terraform uses `kreuzwerker/docker` provider locally — trivially swappable to AWS ECS, GCP Cloud Run, or K8s later.

`KOURAI_AGENT_HOST=true` switches agent URL resolution from `localhost` to Docker service names.

### Why three-layer agent pattern

Every agent follows: `agent.py` (pure logic) → `agent_executor.py` (A2A bridge) → `__main__.py` (AgentCard + server). Logic stays testable without A2A. The executor handles protocol translation and tracing. The entry point owns config and startup.

---

## :material-link-variant: References

### A2A Protocol

- [A2A Protocol Spec (v0.4.0)](https://a2a-protocol.org/latest)
- [A2A GitHub](https://github.com/a2aproject/A2A)
- [A2A Python Samples](https://github.com/a2aproject/a2a-samples)
- [A2A SDK (PyPI)](https://pypi.org/project/a2a-sdk/)
- [A2A Purchasing Concierge Codelab](https://codelabs.developers.google.com/intro-a2a-purchasing-concierge)

### Industry Context

- [Google Blog: A2A — A New Era of Agent Interoperability](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [IBM: What Is Agent2Agent Protocol](https://www.ibm.com/think/topics/agent2agent-protocol)
- [AWS: Inter-Agent Communication on A2A](https://aws.amazon.com/blogs/opensource/open-protocols-for-agent-interoperability-part-4-inter-agent-communication-on-a2a/)
- [Linux Foundation A2A Project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)

### Stack

- [LiteLLM Docs](https://docs.litellm.ai/)
- [Ollama](https://ollama.com/)
- [MCP Spec](https://modelcontextprotocol.io/)
- [FastMCP (Python)](https://github.com/jlowin/fastmcp)
- [uv](https://docs.astral.sh/uv/)

### Infrastructure (Evaluated, Not Adopted)

- [BeeAI Framework](https://framework.beeai.dev/) — `RequirementAgent` useful standalone
- [AgentStack](https://agentstack.beeai.dev/) — Too heavy for local (requires K8s/Lima VM)
- [AutoGen/AG2](https://github.com/microsoft/autogen) — Alternative with native A2A, 50K+ stars
