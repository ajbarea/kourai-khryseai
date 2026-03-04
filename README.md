<div align="center">

# 🏛️ Κοῦραι Χρύσεαι

### **Kourai Khryseai** — *The Golden Maidens*

*Autonomous AI agents forged by Hephaestus to code at alarming speeds.*

[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v0.4-4285F4?style=flat-square&logo=google&logoColor=white)](https://a2a-protocol.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![codecov](https://codecov.io/gh/ajbarea/Kourai_Khryseai/graph/badge.svg?token=bNiUvETLLU)](https://codecov.io/gh/ajbarea/Kourai_Khryseai)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

**One command. A team of specialists. Ship faster.**

```
$ kourai "implement CSV export with tests"
```

</div>

---

## What is this?

Kourai Khryseai is a multi-agent development system where six AI specialists collaborate through the [A2A (Agent-to-Agent) protocol](https://a2a-protocol.org) to handle the full software development lifecycle — from planning to code to tests to linting to commit messages.

You describe what you want. They build it.

```
🔥 Hephaestus: Routing to Metis (planning)...
📐 Metis: Spec complete — 12 implementation steps
🔥 Hephaestus: Routing to Techne (coding)...
⚙️ Techne: Writing changes to 3 files...
🔥 Hephaestus: Routing to Dokimasia (testing)...
🧪 Dokimasia: 8/8 tests passed ✅
🔥 Hephaestus: Routing to Kallos (style)...
✨ Kallos: ruff ✅ · mypy ✅ · zero warnings
🔥 Hephaestus: Routing to Mneme (commits)...
📜 Mneme: Generated 2 commit groups

feat(parser): add CSV export support
- Added parse_csv() function with streaming reader
- Integrated with existing data pipeline
Files: src/utils/parser.py, src/api/endpoints.py

test(parser): add CSV export test suite
- Added 8 unit tests covering edge cases
- Verified streaming behavior with large files
Files: tests/unit/test_parser.py
```

---

## The Agents

<table>
<tr>
<td width="80" align="center">🔥</td>
<td><strong>Hephaestus</strong> — <em>Orchestrator</em><br/>
Receives your request, decides which specialists to invoke and in what order. Manages the full pipeline, relays progress in real-time via SSE.</td>
<td><code>:10000</code></td>
</tr>
<tr>
<td align="center">📐</td>
<td><strong>Metis</strong> — <em>Planner</em><br/>
Transforms rough ideas into detailed implementation specs with file lists, acceptance criteria, edge cases, and testing notes.</td>
<td><code>:10001</code></td>
</tr>
<tr>
<td align="center">⚙️</td>
<td><strong>Techne</strong> — <em>Coder</em><br/>
Implements code from specs. Reads existing code first, understands patterns, edits files. Prefers editing over creating.</td>
<td><code>:10002</code></td>
</tr>
<tr>
<td align="center">🧪</td>
<td><strong>Dokimasia</strong> — <em>Tester</em><br/>
Writes pytest suites (unit → integration → performance). Targets 80%+ coverage. Runs <code>make test</code> and reports structured results.</td>
<td><code>:10003</code></td>
</tr>
<tr>
<td align="center">✨</td>
<td><strong>Kallos</strong> — <em>Stylist</em><br/>
Runs <code>make lint</code>, cleans comments and docstrings, enforces style guides. Hands off to Techne for logic fixes, max 3 iterations.</td>
<td><code>:10004</code></td>
</tr>
<tr>
<td align="center">📜</td>
<td><strong>Mneme</strong> — <em>Scribe</em><br/>
Generates grouped commit messages from <code>git diff</code> in conventional-commit format. Never commits — that's your job.</td>
<td><code>:10005</code></td>
</tr>
</table>

> **Naming:** In Greek mythology, Hephaestus forged the Κοῦραι Χρύσεαι — golden women-shaped automatons — to serve as attendants in his divine workshop. Each specialist is named after a Greek concept matching their role: Metis (wisdom), Techne (craft), Dokimasia (scrutiny), Kallos (beauty), Mneme (memory).

---

## Architecture

```
                         YOU (CLI)
                            │
                            │ A2A · SSE
                            ▼
                    🔥 HEPHAESTUS
                      Orchestrator
                        :10000
                     ┌────┼────┐
            A2A      │    │    │      A2A
         ┌───────────┤    │    ├───────────┐
         │           │    │    │           │
    📐 METIS    ⚙️ TECHNE 🧪 DOKIMASIA  ✨ KALLOS  📜 MNEME
     :10001      :10002    :10003      :10004     :10005
         │           │    │    │           │
         └───────────┴────┴────┴───────────┘
                         │
                    MCP Servers
                  (fs · git · sh)
                         │
                    Jaeger (OTEL)
                      :16686
```

**How it works:**

- Each agent is an independent HTTP server exposing an [A2A Agent Card](https://a2a-protocol.org)
- Hephaestus uses an LLM to route requests to the right pipeline of specialists
- Agents talk to each other via A2A `message/send` (synchronous) and `message/stream` (SSE)
- Agents access the filesystem, git, and shell through [MCP](https://modelcontextprotocol.io/) tool servers
- Every A2A call creates an OpenTelemetry trace span — viewable in Jaeger

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker** — for Jaeger (observability)
- **Anthropic API key** — or [Ollama](https://ollama.com/) for free local models

### Setup

```bash
# Clone
git clone https://github.com/ajbarea/Kourai_Khryseai.git
cd Kourai_Khryseai

# Install
uv sync --all-packages

# Configure
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# Start (launches all 6 agents + Jaeger)
make up
```

### Use

```bash
# Full pipeline: plan → code → test → lint → commit messages
kourai "implement CSV export with tests"

# Quick tasks
kourai "fix the null check in auth.py"
kourai "add tests for the payment module"
kourai "clean up comments in src/utils/"
kourai "commit prep"
```

### Verify

```bash
# Check agent health
make status

# ✅ hephaestus :10000
# ✅ metis      :10001
# ✅ techne     :10002
# ✅ dokimasia  :10003
# ✅ kallos     :10004
# ✅ mneme      :10005

# View traces
open http://localhost:16686    # Jaeger UI
```

---

## Pipelines

Hephaestus automatically selects the right pipeline based on your request:

| You say | Pipeline | Agents invoked |
|---------|----------|---------------|
| *"implement feature X"* | Full | Metis → Techne → Dokimasia → Kallos → Mneme |
| *"fix bug in X"* | Fix | Techne → Dokimasia → Kallos → Mneme |
| *"add tests for X"* | Test | Dokimasia → Kallos → Mneme |
| *"clean up X"* | Style | Kallos → Mneme |
| *"commit prep"* | Scribe | Mneme |
| *"plan feature X"* | Plan | Metis |

When Kallos finds lint errors that require code changes, it hands off to Techne, who fixes them, and Kallos re-checks — up to 3 iterations before reporting remaining issues.

---

## Running with Docker

Every agent can run as an isolated Docker container:

```bash
# Start the full stack (builds + all agents + Jaeger)
make docker-up

# Stop
make docker-down
```

Docker Compose profiles give you fine control:

```bash
docker compose up jaeger              # Observability only
docker compose --profile agents up    # Specialists only
docker compose --profile full up      # Everything
```

---

## LLM Models

Agents use [LiteLLM](https://docs.litellm.ai/) for model-agnostic LLM calls. Default assignments:

| Agent | Cloud (default) | Local (free) |
|-------|----------------|--------------|
| Hephaestus | Claude Sonnet 4.6 | llama3.3:70b |
| Metis | Claude Opus 4.6 | llama3.3:70b |
| Techne | Claude Sonnet 4.6 | llama3.3:70b |
| Dokimasia | Claude Sonnet 4.6 | qwen2.5-coder:32b |
| Kallos | Claude Haiku 4.5 | llama3.3:8b |
| Mneme | Claude Haiku 4.5 | llama3.3:8b |

Switch to local models for free development:

```bash
# In .env
KOURAI_PROVIDER=local
```

---

## Project Structure

```
kourai_khryseai/
├── agents/
│   ├── hephaestus/          # 🔥 Orchestrator
│   ├── metis/               # 📐 Planner
│   ├── techne/              # ⚙️ Coder
│   ├── dokimasia/           # 🧪 Tester
│   ├── kallos/              # ✨ Stylist
│   └── mneme/               # 📜 Scribe
├── shared/                  # kourai_common — config, LLM, tracing, retry
├── hosts/cli/               # CLI client
├── mcp_servers/             # MCP tool servers (filesystem, git, shell)
├── docker/                  # Dockerfiles (multi-stage, generic per agent)
├── infra/terraform/         # IaC for optional cloud deployment
├── tests/                   # Unit + integration tests
├── docs/                    # Project documentation (Zensical)
├── docker-compose.yml       # Full-stack orchestration
├── Makefile                 # Developer commands
└── pyproject.toml           # uv workspace root
```

Each agent follows the **three-layer pattern:**

| Layer | File | Purpose |
|-------|------|---------|
| Domain logic | `agent.py` | Pure business logic. No A2A types. Async generators. |
| A2A bridge | `agent_executor.py` | Translates between A2A protocol and domain logic. OTEL spans. |
| Server entry | `__main__.py` | Agent Card + uvicorn + health check. |

---

## Observability

Every agent is instrumented with [OpenTelemetry](https://opentelemetry.io/). Open **Jaeger** at [`localhost:16686`](http://localhost:16686) to see:

- Full request flow across all agents as a single trace
- Per-agent LLM call latency
- Error locations — which agent failed and at which span
- Trace context propagation via W3C headers in A2A message metadata

---

## Development

```bash
make setup      # Install deps
make test       # Run test suite
make lint       # Run ruff
make clean      # Remove __pycache__, .pytest_cache
make status     # Check all agent health endpoints
make docs       # Serve documentation locally
make help       # Show all available commands
```

---

## Tech Stack

| | Technology |
|--|-----------|
| **Protocol** | [A2A v0.4](https://a2a-protocol.org) — agent-to-agent communication |
| **Server** | [Starlette](https://www.starlette.io/) via `a2a-sdk` |
| **LLM** | [LiteLLM](https://docs.litellm.ai/) — Claude, Gemini, Ollama through one interface |
| **Tools** | [MCP](https://modelcontextprotocol.io/) — filesystem, git, shell access |
| **Package Manager** | [uv](https://docs.astral.sh/uv/) — fast Python packaging with workspace support |
| **Observability** | [OpenTelemetry](https://opentelemetry.io/) → [Jaeger](https://www.jaegertracing.io/) |
| **Containers** | Docker + Docker Compose (optional Terraform for cloud) |
| **Python** | 3.12+ with modern type hints |

---

## Documentation

Full project documentation is available at the [Kourai Khryseai docs site](https://ajbarea.github.io/Kourai_Khryseai/), built with [Zensical](https://zensical.dev).

```bash
make docs    # Serve docs locally
```

---

## Coverage

<div align="center">

[![codecov sunburst](https://codecov.io/gh/ajbarea/Kourai_Khryseai/graphs/sunburst.svg?token=bNiUvETLLU)](https://codecov.io/gh/ajbarea/Kourai_Khryseai)

</div>

---

## License

[MIT](LICENSE)

---

<div align="center">
<sub>Built by <a href="https://github.com/ajbarea">AJ Barea</a> · Forged in the workshop of Hephaestus</sub>
</div>
