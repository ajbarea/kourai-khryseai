# Infrastructure

## 🔍 Observability

The agent stack ships a three-pane observability triad — **Jaeger** for traces, **Prometheus** for metrics, **Dozzle** for live container logs. One command opens all three:

```bash
make observe
```

Each log line emitted inside a span context carries the active trace ID, so a slow span found in Jaeger is grep-findable in Dozzle without any code change between observation and search.

The full mental model, triage runbook, and current coverage gaps live on the dedicated **[Observability](../observability.md)** page.

---

## 🐳 Infrastructure

### Docker

A single generic `Dockerfile` at `docker/agent.Dockerfile` builds any agent via the `AGENT_NAME` build arg:

```bash title="Build a single agent"
docker build --build-arg AGENT_NAME=mneme -f docker/agent.Dockerfile -t kourai-mneme .
```

Multi-stage build: builder installs deps with `uv`, runtime copies only the venv. Each container has a health check against `/.well-known/agent-card.json`.

### Docker Compose

`docker-compose.yml` defines all ten agents + infrastructure. `docker compose up` brings everything up — agents resolve each other via Docker service names (e.g., `http://hephaestus:10000`).

---

## 🔑 Key Design Decisions

??? question "Why `a2a-sdk` directly, not AgentStack?"
    [AgentStack](https://agentstack.beeai.dev/) requires Kubernetes via Lima VM. Windows support needs WSL2. Frequent breaking changes. Decision: `a2a-sdk` + Starlette + uvicorn gives full A2A compliance without K8s overhead.

??? question "Why A2A 0.3.x, not 1.0?"
    v1.0 has breaking changes: Part type unification, enum case changes, method renames, well-known URL rename. Pinned at `a2a-sdk[http-server]>=0.3.25,<1.0` (shared) until the M7 cutover lands. The 1.0.x migration is bigger than the dual-shape inspection firewall the codebase carries today.

??? question "Why LiteLLM?"
    Model-agnostic interface. Claude for production, Ollama for free local dev. Swap with one env var: `KOURAI_PROVIDER=local`.

??? question "Why sequential pipelines, not parallel?"
    Agents build on each other's output — Techne needs Metis's spec, Dokimasia needs Techne's code, Kallos needs the files written. Parallelism doesn't help when there's a data dependency chain. The Kallos-Techne loop is the one place where iteration (not parallelism) adds value.

---

## 📚 References

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
- [Starlette](https://www.starlette.io/)
- [uv](https://docs.astral.sh/uv/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Jaeger](https://www.jaegertracing.io/)
- [Prometheus](https://prometheus.io/)
