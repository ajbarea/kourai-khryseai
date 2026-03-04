# Getting Started

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.12+ | Required by `a2a-sdk` |
| **[uv](https://docs.astral.sh/uv/)** | Latest | Fast Python packaging with workspace support |
| **Docker** | Any | For Jaeger observability (optional but recommended) |
| **API Key** | — | Anthropic API key, or use [Ollama](https://ollama.com/) for free local models |

---

## Installation

### 1. Clone and install

```bash
git clone https://github.com/ajbarea/Kourai_Khryseai.git
cd Kourai_Khryseai

# Install all workspace packages
make setup
# (equivalent to: uv sync --all-packages)
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

??? tip "Using Ollama instead (free, no API key)"

    Install [Ollama](https://ollama.com/), pull the models, and set:

    ```bash
    KOURAI_PROVIDER=local
    ```

    See [Configuration → LLM Models](configuration.md#llm-models) for the full model table.

---

## Starting the Agents

### Option A: Local (development)

```bash
# Start all 6 agents + Jaeger and verify everything is running
make up
# ✅ Hephaestus  :10000
# ✅ Metis       :10001
# ✅ Techne      :10002
# ✅ Dokimasia   :10003
# ✅ Kallos      :10004
# ✅ Mneme       :10005
```

Agents run as background processes with logs in `logs/`.

### Option B: Docker (containerized)

```bash
make docker-up       # Build images + start full stack
make docker-down     # Stop everything
```

Docker Compose profiles for fine control:

```bash
docker compose up jaeger              # Observability only
docker compose --profile agents up    # Specialists only (no orchestrator)
docker compose --profile full up      # Everything
```

---

## Your First Request

Launch the interactive CLI:

```bash
make cli
```

You'll see the Kourai Khryseai banner and a prompt:

```
╔══════════════════════════════════════════╗
║     Kourai Khryseai — Golden Maidens     ║
╚══════════════════════════════════════════╝
Type your request. Commands: :q (quit), :status (agent info)

Connecting to Hephaestus at http://localhost:10000/...
Connected to Hephaestus — Orchestrator v0.1.0
Skills: Route Development Request, Execute Development Pipeline

kourai:
```

Type a request in plain English:

```bash
# Full pipeline: plan → code → test → lint → commit messages
kourai: implement CSV export with tests

# Fix a bug
kourai: fix the null check in auth.py

# Add tests
kourai: add tests for the payment module

# Style cleanup
kourai: clean up comments in src/utils/

# Just commit messages
kourai: commit prep
```

Hephaestus automatically routes your request to the right pipeline of specialists. You'll see real-time progress with agent emojis as each step completes.

See the [CLI Reference](cli.md) for all commands and options.

### Using the GUI

For a richer, visual experience, launch the full-screen GUI:

```bash
make gui
```

This opens an anime-styled visual interface with:
- **Full-color portraits** of each agent (1280×720 JRPG aesthetic)
- **Dialogue bubbles** with real-time responses
- **Personality-matched voices** with neural speech synthesis
- **Scrollable chat history** with agent switching
- **Settings overlay** for voice customization and accessibility

The GUI speaks all agent responses through natural neural voices (Microsoft Edge TTS with real-time volume/pitch control).

#### Quick TTS Test

```bash
# Just hear what the voices sound like
python -c "
from hosts.gui.tts_engine import TTSEngine
import asyncio

async def demo():
    engine = TTSEngine(master_volume=0.8)
    for agent in ['kallos', 'metis', 'hephaestus']:
        print(f'Speaking as {agent}...')
        await engine.speak(f'Hello! I am {agent}.', agent_name=agent)
    engine.cleanup()

asyncio.run(demo())
"
```

See [GUI Reference → Text-to-Speech System](gui.md#text-to-speech-system-) for voice customization, personality profiles, and advanced audio options.

---

## Viewing Traces

Every request creates a distributed trace across all agents. Jaeger starts automatically with `make up` (or `make docker-up`).

Open the Jaeger UI at [`localhost:16686`](http://localhost:16686) and select any agent from the service dropdown to see its spans, timings, and any errors.

---

## Stopping the Agents

```bash
# Local
make down

# Docker
make docker-down
```

---

## Next Steps

- **[Agents](agents/index.md)** — Learn what each specialist does and how they work
- **[Architecture](architecture/index.md)** — Understand the system design and three-layer pattern
- **[CLI Reference](cli.md)** — All CLI commands, options, and keyboard shortcuts
- **[Configuration](configuration.md)** — Environment variables, model assignments, timeouts
