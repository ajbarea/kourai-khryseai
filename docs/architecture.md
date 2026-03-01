# Architecture

## 🗺️ System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOU (CLI REPL)                            │
│                                                                 │
│  $ make cli                                                     │
│  kourai: add CSV export to the dashboard                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ A2A message/stream (SSE)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   🔥 HEPHAESTUS (Orchestrator)                  │
│                        Port 10000                               │
│                                                                 │
│  LLM routing → sequential pipeline → context accumulation       │
│  Kallos↔Techne feedback loop (max 3 iterations)                │
└────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │          │
     │ A2A      │ A2A      │ A2A      │ A2A      │ A2A
     │ blocking │ blocking │ blocking │ blocking │ blocking
     ▼          ▼          ▼          ▼          ▼
┌─────────┐┌─────────┐┌──────────┐┌─────────┐┌─────────┐
│ 📐      ││ ⚙️      ││ 🧪       ││ ✨      ││ 📜      │
│ METIS   ││ TECHNE  ││DOKIMASIA ││ KALLOS  ││ MNEME   │
│ Planner ││ Coder   ││ Tester   ││ Stylist ││ Scribe  │
│ :10001  ││ :10002  ││ :10003   ││ :10004  ││ :10005  │
└─────────┘└─────────┘└──────────┘└─────────┘└─────────┘
                           │
                  ┌────────┴────────┐
                  │  Jaeger (OTEL)  │
                  │  :16686 (UI)    │
                  │  :4318 (OTLP)   │
                  └─────────────────┘
```

---

## 🔗 Communication Patterns

### User ↔ Hephaestus: Streaming (SSE)

The CLI connects to Hephaestus using A2A `message/stream` with Server-Sent Events. This means you see real-time progress as each agent reports status — not a single response after everything finishes.

```python
# CLI sends a streaming request
request = SendStreamingMessageRequest(
    id=str(uuid4()),
    params=MessageSendParams(
        message=Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=user_text))],
            context_id=context_id,
        ),
        configuration=MessageSendConfiguration(
            accepted_output_modes=["text"],
        ),
    ),
)

async for result in client.send_message_streaming(request):
    # TaskStatusUpdateEvent → progress messages
    # TaskArtifactUpdateEvent → final output
    ...
```

### Hephaestus ↔ Specialists: Synchronous

Hephaestus calls specialists using A2A `message/send` with `blocking=True`. This makes each call synchronous — Hephaestus waits for one specialist to complete before calling the next.

```python
# RemoteAgentConnection.send() — simplified
request = SendMessageRequest(
    id=message_id,
    params=MessageSendParams(
        message=Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=user_text))],
            context_id=context_id,
            metadata=get_trace_context(),  # W3C trace headers
        ),
        configuration=MessageSendConfiguration(blocking=True),
    ),
)
response = await client.send_message(request)
```

### Input Required: Clarification Loop

When a specialist needs user input, it raises `AgentInputRequired`. Hephaestus catches this and yields an `INPUT_REQUIRED:` status. The CLI detects this state and prompts the user for follow-up, then resends to continue the pipeline.

---

## 🏗️ Three-Layer Agent Pattern

Every agent follows the same internal structure. No exceptions.

| Layer | File | Responsibility |
|---|---|---|
| **Domain logic** | `agent.py` | Pure business logic. No A2A types. Async functions and generators. Testable in isolation. |
| **A2A bridge** | `agent_executor.py` | Subclasses `AgentExecutor` from `a2a-sdk`. Translates between A2A events and domain logic. Creates OTEL spans. |
| **Server entry** | `__main__.py` | Defines the `AgentCard`, creates the `A2AStarletteApplication`, starts uvicorn. |

**Why this matters:**

- `agent.py` never imports `a2a.*` — you can test all business logic with simple function calls and mocked LLM responses
- `agent_executor.py` is the only file that touches A2A types — protocol changes are contained to one layer
- `__main__.py` owns configuration — if you need to change ports, skills, or card metadata, it's all in one place

### Example: Mneme's Three Layers

```python
# agent.py — pure logic, no A2A
async def generate_commit_messages(git_output: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": git_output},
    ]
    return await chat("mneme", messages)

# agent_executor.py — A2A bridge
class MnemeAgentExecutor(AgentExecutor):
    async def execute(self, context, event_queue):
        user_input = self._extract_text(context)
        task_updater = TaskUpdater(event_queue)
        await task_updater.new_task()
        await task_updater.update_status("working", "Generating commit messages...")
        result = await generate_commit_messages(user_input)
        await task_updater.add_artifact([Part(root=TextPart(text=result))])
        await task_updater.complete()

# __main__.py — server config
card = AgentCard(
    name="Mneme",
    description="Generates commit messages from git diff output",
    version="0.1.0",
    skills=[AgentSkill(name="generate_commit_messages", ...)],
    ...
)
app = A2AStarletteApplication(agent_card=card, agent_executor=MnemeAgentExecutor)
```

---

## 📦 Shared Library: `kourai-common`

All agents depend on a shared workspace member at `shared/src/kourai_common/` with four modules:

### `config.py` — Agent Configuration

Centralized model assignments, ports, timeouts, and environment variable handling.

```python
from kourai_common.config import get_model, get_agent_url, MAX_ITERATIONS

get_model("metis")       # → "anthropic/claude-opus-4-6"
get_agent_url("techne")  # → "http://localhost:10002/" (or Docker service name)
```

`KOURAI_AGENT_HOST=true` switches URL resolution from `localhost:PORT` to `servicename:PORT` for Docker networking.

### `llm.py` — Model-Agnostic LLM Interface

Wraps [LiteLLM](https://docs.litellm.ai/) for async-compatible calls with per-agent timeout enforcement.

```python
from kourai_common.llm import chat, chat_stream

# Synchronous response
result = await chat("mneme", messages, temperature=0.3, max_tokens=4096)

# Streaming response
async for chunk in chat_stream("techne", messages):
    yield chunk
```

### `tracing.py` — OpenTelemetry Integration

Sets up distributed tracing with Jaeger as the backend.

```python
from kourai_common.tracing import setup_tracing, create_span, get_trace_context

# Call once at startup
setup_tracing("mneme", otlp_endpoint)

# Create spans around operations
with create_span("mneme.generate", {"input_length": str(len(text))}):
    result = await generate_commit_messages(text)

# Propagate trace context across agent boundaries
metadata = get_trace_context()  # → W3C traceparent/tracestate headers
```

### `retry.py` — Exponential Backoff

Decorator for transient failure recovery on network calls.

```python
from kourai_common.retry import with_retry

@with_retry(max_attempts=3, base_delay=1.0,
            retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException))
async def send(self, text, context_id):
    ...
```

---

## 🔍 Observability

### Distributed Tracing

Every A2A call creates an OpenTelemetry span. W3C Trace Context headers are propagated via A2A message `metadata`, allowing Jaeger to stitch traces across all six agents into a single view.

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

---

## 🐳 Infrastructure

### Docker

A single generic `Dockerfile` at `docker/agent.Dockerfile` builds any agent via the `AGENT_NAME` build arg:

```bash
docker build --build-arg AGENT_NAME=mneme -f docker/agent.Dockerfile -t kourai-mneme .
```

Multi-stage build: builder installs deps with `uv`, runtime copies only the venv. Each container has a health check against `/.well-known/agent.json`.

### Docker Compose

`docker-compose.yml` defines all agents + Jaeger with profiles:

- **No profile** — Jaeger only
- **`agents`** — All five specialists
- **`full`** — Specialists + Hephaestus (depends on all others)

Environment variable `KOURAI_AGENT_HOST=true` is set automatically in Docker, switching URL resolution to service names.

### Terraform

`infra/terraform/main.tf` uses the `kreuzwerker/docker` provider for local container management. Designed to be swappable — replace the Docker provider with AWS ECS, GCP Cloud Run, or Kubernetes when you're ready for production.

---

## 🔑 Key Design Decisions

### Why `a2a-sdk` directly, not AgentStack

[AgentStack](https://agentstack.beeai.dev/) requires Kubernetes via Lima VM. Windows support needs WSL2. Frequent breaking changes. Decision: `a2a-sdk` + Starlette + uvicorn gives full A2A compliance without K8s overhead.

### Why A2A v0.4, not v1.0

v1.0 RC has breaking changes: Part type unification, enum case changes, method renames, well-known URL rename. Pinned at `a2a-sdk>=0.3.0,<1.0` until v1.0 stabilizes.

### Why LiteLLM

Model-agnostic interface. Claude for production, Ollama for free local dev. Swap with one env var: `KOURAI_USE_LOCAL_MODELS=true`.

### Why sequential pipelines, not parallel

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
