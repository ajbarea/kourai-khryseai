# Infrastructure

## 🔍 Observability

### Distributed Tracing

Every A2A call creates an OpenTelemetry span. W3C Trace Context headers are propagated via A2A message `metadata`, allowing Jaeger to stitch traces across all ten agents into a single view.

**Span naming convention:**

| Span | Source |
|---|---|
| `hephaestus.route` | Pipeline determination |
| `hephaestus.pipeline.step.{agent}` | Each specialist call |
| `hephaestus.pipeline.fix_loop` | Kallos-Techne iterations |
| `a2a.connect.{agent}` | Agent card fetch |
| `a2a.send.{agent}` | Message send |
| `{agent}.execute` | Agent-specific execution |
| `{agent}.generate` | LLM call |

### What You See in Jaeger

Open [`localhost:16686`](http://localhost:16686) and select any service:

- **Full request flow** — One trace spanning all agents in the pipeline
- **Per-agent latency** — How long each specialist took (LLM call time dominates)
- **Error locations** — Which agent failed and at which operation
- **Fix loop iterations** — How many Kallos-Techne rounds were needed

### 📊 Service Performance Monitoring (SPM)

Jaeger generates RED metrics (Rate, Error, Duration) from traces and stores them in Prometheus. This enables the "Monitor" tab in the Jaeger UI for high-level service health visualization.

- **RED Metrics** — Instant visibility into request volume, error percentages, and latency percentiles (P50, P95, P99).
- **Metric Exploration** — Use the Prometheus UI at [`localhost:9090`](http://localhost:9090) for raw PromQL queries and custom dashboarding.
- **Span-to-Metrics** — Jaeger's internal collector generates these metrics in real-time as traces arrive via OTLP.

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
    v1.0 RC has breaking changes: Part type unification, enum case changes, method renames, well-known URL rename. Pinned at `a2a-sdk>=0.3.0,<1.0` until v1.0 stabilizes. Current stable: `0.3.24` (Feb 2026).

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
