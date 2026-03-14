# Getting Started

Kourai Khryseai works as a **real-time conversation** with six AI specialists. You describe what you need, they ask clarifying questions, show their work as they build it, and iterate based on your feedback. Two paths to the same system:

- **CLI** — Fast, scriptable, terminal-based
- **GUI** — Rich visual experience with agent profiles and voices

Both are equally capable. Pick whichever fits your workflow.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.12+ | Required by `a2a-sdk` |
| **[uv](https://docs.astral.sh/uv/)** | Latest | Fast Python packaging with workspace support |
| **Docker + Docker Compose** | Any | Required to run agents and observability stack |
| **API Key** | — | Anthropic API key, or use [Ollama](https://ollama.com/) for free local models |

---

## Installation

### 1. Clone and install

```bash title="Terminal"
git clone https://github.com/ajbarea/kourai_khryseai.git
cd kourai_khryseai

# Install all workspace packages
make setup
# (equivalent to: uv sync --all-packages)
```

??? tip "Multiple terminals / OS environments (WSL, Docker, Windows)"

    `make setup` automatically selects the right virtual environment for your platform:

    | Environment | venv folder |
    |---|---|
    | WSL | `.venv-wsl` |
    | Windows (Git Bash / PowerShell) | `.venv-win` |
    | Docker | `.venv` (inside container only) |

    If you run `uv sync` directly (without `make`), set `UV_PROJECT_ENVIRONMENT` in your shell profile to match the table above — otherwise `uv` defaults to `.venv` and collides across environments.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```bash title=".env"
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

```bash
make up              # Build images + start full stack (waits for healthy services)
make status          # Show service state/health
```

Docker Compose profiles for fine control:

=== "Full Stack (recommended)"

    ```bash
    docker compose --profile full up
    ```
    All six agents + Jaeger + Prometheus.

=== "Specialists Only"

    ```bash
    docker compose --profile agents up
    ```
    Five specialists without Hephaestus orchestrator.

=== "Observability Only"

    ```bash
    docker compose up jaeger
    ```
    Just Jaeger for trace inspection.

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

❯
```

Type a request in plain English:

```bash
# Full pipeline: plan → code → test → lint → commit messages
❯ implement CSV export with tests

# Fix a bug
❯ fix the null check in auth.py

# Add tests
❯ add tests for the payment module

# Style cleanup
❯ clean up comments in src/utils/

# Just commit messages
❯ commit prep
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

```python title="Quick voice demo"
from hosts.gui.tts_engine import TTSEngine
import asyncio

async def demo():
    engine = TTSEngine(master_volume=0.8)
    for agent in ['kallos', 'metis', 'hephaestus']:
        print(f'Speaking as {agent}...')
        await engine.speak(f'Hello! I am {agent}.', agent_name=agent)
    engine.cleanup()

asyncio.run(demo())
```

See [GUI Reference → Text-to-Speech System](gui.md#text-to-speech-system-) for voice customization, personality profiles, and advanced audio options.

---

## Viewing Traces & Metrics

Every request creates a distributed trace across all agents and generates performance metrics. Both Jaeger and Prometheus start automatically with `make up`.

- **Jaeger** — Trace inspection at [`localhost:16686`](http://localhost:16686). Select any agent from the service dropdown to see its spans, timings, and any errors.
- **Prometheus** — Metric inspection at [`localhost:9090`](http://localhost:9090). View RED metrics (Rate, Error, Duration) across all services, powering the "Monitor" tab in Jaeger.

---

## Stopping the Agents

```bash
make down
```

---

## Next Steps

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **[Agents](agents/index.md)**

    ---

    Learn what each specialist does and how they work

-   :material-sitemap:{ .lg .middle } **[Architecture](architecture/index.md)**

    ---

    Understand the system design and three-layer pattern

-   :material-console:{ .lg .middle } **[CLI Reference](cli.md)**

    ---

    All CLI commands, options, and keyboard shortcuts

-   :material-cog:{ .lg .middle } **[Configuration](configuration.md)**

    ---

    Environment variables, model assignments, timeouts

</div>
