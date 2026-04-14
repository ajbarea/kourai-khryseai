# Getting Started

Kourai Khryseai works as a **real-time conversation** with ten AI specialists. You describe what you need, they ask clarifying questions, show their work as they build it, and iterate based on your feedback. Three paths to the same system:

- **CLI** — Fast, scriptable, terminal-based
- **GUI** — Rich desktop experience with agent portraits, TTS, and visual effects
- **VN** — Dating-sim inspired visual novel with affinity, romance, and character progression

All three are equally capable and connect to the same Docker-hosted agent backend. Pick whichever fits your workflow.

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

Start everything:

```bash
docker compose up
```

All ten agents + Jaeger + Prometheus.

To start a single agent (plus its dependencies):

```bash
docker compose up mneme
```

For just Jaeger trace inspection:

```bash
docker compose up jaeger
```

---

## Your First Request

### :octicons-terminal-24: Option 1: CLI

```bash
make cli
```

```
╔══════════════════════════════════════════╗
║     Kourai Khryseai — Golden Maidens     ║
╚══════════════════════════════════════════╝
Type your request. Commands: :q (quit), :status (agent info)

Connecting to Hephaestus at http://localhost:10000/...
Connected to Hephaestus — Orchestrator v0.1.0

❯ implement CSV export with tests
```

Hephaestus automatically routes your request to the right pipeline. You'll see real-time progress with agent emojis as each step completes.

See the [CLI Reference](cli.md) for all commands.

### :octicons-device-desktop-24: Option 2: Pygame GUI

```bash
make gui
```

Opens a full-screen JRPG-styled interface with:
- **Full-color portraits** of each agent with glow effects and crossfade transitions
- **Dialogue bubbles** with real-time streaming responses
- **Personality-matched voices** with neural speech synthesis
- **Golden particle effects** and typewriter text animation
- **Settings overlay** for voice customization and accessibility

??? tip "WSL2 audio prerequisites (TTS, music, ambient)"

    WSLg routes audio through PulseAudio (`PULSE_SERVER`), but your distro still needs Pulse runtime libs:

    ```bash
    sudo apt update
    sudo apt install -y libpulse0 pulseaudio-utils libpipewire-0.3-0 espeak-ng
    ```

    If SDL picks the wrong backend, force PulseAudio for the GUI process:

    ```bash
    SDL_AUDIODRIVER=pulseaudio make gui
    ```

See the [GUI Reference](gui.md) for keyboard shortcuts, visual effects, and TTS configuration.

### :octicons-book-24: Option 3: Ren'Py Visual Novel

```bash
cd hosts/vn/renpy-8.5.2-sdk
./renpy.sh ../kourai_vn    # Linux/Mac
renpy.exe ..\kourai_vn     # Windows
```

Opens a Ren'Py visual novel with:
- **Warm forge aesthetic** — gold, cream, charcoal
- **Affinity HUD** — tracks your relationship tier with each agent
- **Gossip system** — idle agents share personality-driven flavor text
- **Choice events** — agents present choices that affect affinity
- **Full save/load** — portrait thumbnails, conversation context, bridge reconnect

See the [VN Reference](vn.md) for architecture, screens, and troubleshooting.

---

## Viewing Traces & Metrics

Every request creates a distributed trace across all agents and generates performance metrics. Both Jaeger and Prometheus start automatically with `make up`.

- **Jaeger** — Trace inspection at [`localhost:16686`](http://localhost:16686). Select any agent from the service dropdown to see its spans, timings, and any errors.
- **Prometheus** — Metric inspection at [`localhost:9090`](http://localhost:9090). View RED metrics (Rate, Error, Duration) across all services.

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

-   :material-gamepad-variant:{ .lg .middle } **[VN Reference](vn.md)**

    ---

    Ren'Py visual novel architecture and features

-   :material-cog:{ .lg .middle } **[Configuration](configuration.md)**

    ---

    Environment variables, model assignments, timeouts

-   :material-currency-usd:{ .lg .middle } **[Pricing](pricing.md)**

    ---

    Cost breakdown per provider and tier

</div>
