# Getting Started

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.12+** | Required by `a2a-sdk` |
| **[uv](https://docs.astral.sh/uv/)** | Fast Python packaging with workspace support |
| **Docker** | For Jaeger observability |
| **Anthropic API key** | Or use [Ollama](https://ollama.com/) for free local models |

## Installation

```bash
# Clone
git clone https://github.com/ajbarea/Kourai_Khryseai.git
cd Kourai_Khryseai

# Install all workspace packages
uv sync --all-packages

# Configure
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

## Starting the System

### Local

```bash
# Start all 6 agents + Jaeger
make up

# Check health
make status
# ✅ hephaestus :10000
# ✅ metis      :10001
# ✅ techne     :10002
# ✅ dokimasia  :10003
# ✅ kallos     :10004
# ✅ mneme      :10005
```

### Docker

```bash
make docker-build    # Build all images
make docker-up       # Start full stack
make docker-logs     # Tail logs
make docker-down     # Stop
```

Docker Compose profiles for fine control:

```bash
docker compose up jaeger              # Observability only
docker compose --profile agents up    # Specialists only
docker compose --profile full up      # Everything
```

## Usage

Talk to Hephaestus through the CLI. He decides which specialists to invoke:

```bash
# Full pipeline: plan → code → test → lint → commit messages
kourai "implement CSV export with tests"

# Fix a bug
kourai "fix the null check in auth.py"

# Add tests
kourai "add tests for the payment module"

# Style cleanup
kourai "clean up comments in src/utils/"

# Just commit messages
kourai "commit prep"
```

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

**Communication flow:**

- **You ↔ Hephaestus** — A2A `message/stream` (SSE) for real-time progress
- **Hephaestus ↔ Specialists** — A2A `message/send` (synchronous)
- **Agents ↔ Tools** — MCP servers via stdio (filesystem, git, shell)
- **Kallos ↔ Techne** — iterative lint-fix loop, max 3 iterations
- **All agents → Jaeger** — OpenTelemetry with W3C Trace Context

### Three-Layer Agent Pattern

Every agent follows the same internal structure:

| Layer | File | Purpose |
|-------|------|---------|
| Domain logic | `agent.py` | Pure business logic. No A2A types. Async generators. |
| A2A bridge | `agent_executor.py` | Translates between A2A protocol and domain logic. OTEL spans. |
| Server entry | `__main__.py` | Agent Card definition + uvicorn server + health check. |

### Agent Discovery

Each agent exposes an [A2A Agent Card](https://a2a-protocol.org) at `/.well-known/agent.json` — a JSON file describing its name, skills, supported content types, and capabilities. Hephaestus discovers specialists by fetching their cards at startup.

## LLM Models

Agents use [LiteLLM](https://docs.litellm.ai/) for model-agnostic LLM calls:

| Agent | Cloud (default) | Local (free) |
|-------|----------------|--------------|
| Hephaestus | Claude Sonnet 4.6 | llama3.3:70b |
| Metis | Claude Opus 4.6 | llama3.3:70b |
| Techne | Claude Sonnet 4.6 | llama3.3:70b |
| Dokimasia | Claude Sonnet 4.6 | qwen2.5-coder:32b |
| Kallos | Claude Haiku 4.5 | llama3.3:8b |
| Mneme | Claude Haiku 4.5 | llama3.3:8b |

Switch to local models:

```bash
# In .env
KOURAI_USE_LOCAL_MODELS=true
```

## Observability

Every A2A call creates an OpenTelemetry trace span. Open **Jaeger** at [`localhost:16686`](http://localhost:16686) to see:

- Full request flow across all agents as a single trace
- Per-agent LLM call latency
- Error locations — which agent failed and at which span
- Trace context propagation across agent boundaries

```bash
make jaeger    # Start Jaeger standalone
```

## Development

```bash
make setup      # Install deps
make test       # Run test suite
make lint       # Run ruff
make clean      # Remove __pycache__, .pytest_cache
make status     # Check agent health
make docs       # Serve docs locally
make help       # Show all commands
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for Claude models |
| `KOURAI_LOG_LEVEL` | `INFO` | Logging level |
| `KOURAI_MAX_ITERATIONS` | `3` | Max Kallos ↔ Techne loop iterations |
| `KOURAI_STREAM_ENABLED` | `true` | SSE streaming for progress |
| `KOURAI_USE_LOCAL_MODELS` | `false` | Use Ollama instead of Claude |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Jaeger OTLP endpoint |

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
├── docs/                    # This documentation site
├── docker-compose.yml       # Full-stack orchestration
├── Makefile                 # Developer commands
└── pyproject.toml           # uv workspace root
```
