# Configuration

All configuration is managed through environment variables in `.env` (or exported in your shell). Copy `.env.example` to get started:

```bash
cp .env.example .env
```

---

## Environment Variables

### Required

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key. Required when using Claude models (the default). |

### Agent Behavior

| Variable | Default | Description |
|---|---|---|
| `KOURAI_LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `KOURAI_MAX_ITERATIONS` | `3` | Max Kallos ↔ Techne feedback loop iterations before giving up |
| `KOURAI_STREAM_ENABLED` | `true` | Enable SSE streaming for real-time progress |
| `KOURAI_USE_LOCAL_MODELS` | `false` | Use Ollama models instead of Claude (free, no API key) |

### Infrastructure

| Variable | Default | Description |
|---|---|---|
| `KOURAI_AGENT_HOST` | `false` | Set to `true` in Docker — switches URL resolution from `localhost:PORT` to Docker service names |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Jaeger OTLP HTTP endpoint |
| `ENVIRONMENT` | `development` | Environment tag for traces |
| `SERVICE_VERSION` | `0.1.0` | Version tag for traces |

### Optional: Multi-Provider LLM

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (for GPT models via LiteLLM) |
| `GOOGLE_API_KEY` | Google API key (for Gemini models via LiteLLM) |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |

---

## LLM Models

Agents are assigned models in `shared/src/kourai_common/config.py`. The right model for the right job — Opus for complex planning, Sonnet for code generation, Haiku for fast lightweight tasks.

### Cloud Models (default)

| Agent | Model | Why |
|---|---|---|
| 🔥 Hephaestus | Claude Sonnet 4.6 | Routing decisions need to be fast and accurate |
| 📐 Metis | Claude Opus 4.6 | Planning quality determines everything downstream |
| ⚙️ Techne | Claude Sonnet 4.6 | Code generation needs strong reasoning |
| 🧪 Dokimasia | Claude Sonnet 4.6 | Test generation needs code understanding |
| ✨ Kallos | Claude Haiku 4.5 | Mostly subprocess work; LLM only for comment analysis |
| 📜 Mneme | Claude Haiku 4.5 | Commit messages are structured and formulaic |

### Local Models (free)

Set `KOURAI_USE_LOCAL_MODELS=true` to use these via [Ollama](https://ollama.com/):

| Agent | Model | VRAM |
|---|---|---|
| 🔥 Hephaestus | llama3.3:70b | ~40GB |
| 📐 Metis | llama3.3:70b | ~40GB |
| ⚙️ Techne | llama3.3:70b | ~40GB |
| 🧪 Dokimasia | qwen2.5-coder:32b | ~20GB |
| ✨ Kallos | llama3.3:8b | ~5GB |
| 📜 Mneme | llama3.3:8b | ~5GB |

---

## Agent Ports

Each agent runs on a fixed port:

| Agent | Port | Health check |
|---|---|---|
| Hephaestus | `10000` | `http://localhost:10000/.well-known/agent.json` |
| Metis | `10001` | `http://localhost:10001/.well-known/agent.json` |
| Techne | `10002` | `http://localhost:10002/.well-known/agent.json` |
| Dokimasia | `10003` | `http://localhost:10003/.well-known/agent.json` |
| Kallos | `10004` | `http://localhost:10004/.well-known/agent.json` |
| Mneme | `10005` | `http://localhost:10005/.well-known/agent.json` |

---

## Timeouts

Per-agent timeouts are defined in `shared/src/kourai_common/config.py`:

| Operation | Timeout | Notes |
|---|---|---|
| Agent card fetch | 5s | Initial connection to discover agent capabilities |
| Mneme | 30s | Lightweight commit message generation |
| Kallos | 60s | Linting is fast; comment analysis takes longer |
| Techne | 120s | Code generation with large context |
| Dokimasia | 120s | Test generation and execution |
| Metis | 120s | Spec generation with project context |
| Full pipeline | 600s | End-to-end timeout for the CLI |

---

## Docker Networking

When running in containers, `KOURAI_AGENT_HOST=true` is set automatically by Docker Compose. This changes how agents find each other:

| Mode | URL format | Example |
|---|---|---|
| Local (`false`) | `http://localhost:{port}/` | `http://localhost:10002/` |
| Docker (`true`) | `http://{service_name}:{port}/` | `http://techne:10002/` |

Agents use Docker's internal DNS to resolve service names within the `kourai` bridge network.

---

## Makefile Commands

| Command | Description |
|---|---|
| `make setup` | Install all dependencies (`uv sync --all-packages`) |
| `make cli` | Launch the interactive CLI client |
| `make up` | Start all agents locally + Jaeger |
| `make down` | Stop all local agents |
| `make status` | Health check all agent endpoints |
| `make jaeger` | Start Jaeger standalone |
| `make test` | Run linters + full test suite |
| `make lint` | Run ruff + mypy |
| `make coverage` | Run tests with coverage reporting |
| `make clean` | Remove `__pycache__`, `.pytest_cache`, build artifacts |
| `make docs` | Serve documentation locally (Zensical) |
| `make upgrade` | Update all dependencies to latest versions |
| `make docker-build` | Build all agent Docker images |
| `make docker-up` | Start all agents in Docker |
| `make docker-down` | Stop all Docker containers |
| `make docker-status` | Show Docker container status |
| `make docker-logs` | Tail logs from all containers |
| `make help` | Show all available commands |
