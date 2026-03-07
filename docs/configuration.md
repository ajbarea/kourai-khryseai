# Configuration

All configuration is managed through environment variables in `.env` (or exported in your shell). Copy `.env.example` to get started:

```bash
cp .env.example .env
```

---

## Environment Variables

### Required (per provider)

| Provider | Variable | Where to get it |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `google` | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `local` | *(none)* | [Ollama](https://ollama.com/) runs locally |

### Agent Behavior

| Variable | Default | Description |
|---|---|---|
| `KOURAI_LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `KOURAI_PROVIDER` | `anthropic` | LLM provider: `anthropic`, `google`, or `local` |
| `KOURAI_MODEL_TIER` | `cheap` | Quality tier within the provider: `cheap`, `standard`, `smart` |
| `KOURAI_MAX_ITERATIONS` | `5` | Max Kallos ↔ Techne feedback loop iterations before giving up |
| `KOURAI_STREAM_ENABLED` | `true` | Enable SSE streaming for real-time progress |

### Infrastructure

| Variable | Default | Description |
|---|---|---|
| `KOURAI_AGENT_HOST` | `false` | Set to `true` in Docker — switches URL resolution from `localhost:PORT` to Docker service names |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Jaeger OTLP HTTP endpoint |
| `ENVIRONMENT` | `development` | Environment tag for traces |
| `SERVICE_VERSION` | `0.1.0` | Version tag for traces |

### Optional API Keys

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (for GPT models via LiteLLM) |
| `GOOGLE_API_KEY` | Google API key — alias for `GEMINI_API_KEY` |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |

---

## LLM Models

Agents are assigned models in [shared/src/kourai_common/config.py](../shared/src/kourai_common/config.py) based on `KOURAI_PROVIDER` and `KOURAI_MODEL_TIER`. Switch providers by changing one line in `.env` — LiteLLM handles the rest.

```bash
# Claude (your default)
KOURAI_PROVIDER=anthropic

# Gemini (e.g., Google AI Pro subscriber)
KOURAI_PROVIDER=google

# Ollama (free, local GPU)
KOURAI_PROVIDER=local
```

=== "Anthropic (Claude) :material-cloud:"

    **Default provider.** Set `KOURAI_MODEL_TIER` to select a tier:

    === "`cheap` (default)"

        All Haiku — lowest cost, good for testing and iteration.

        | Agent | Model |
        |---|---|
        | 🔥 Hephaestus | Claude Haiku 4.5 |
        | 📐 Metis | Claude Haiku 4.5 |
        | ⚙️ Techne | Claude Haiku 4.5 |
        | 🧪 Dokimasia | Claude Haiku 4.5 |
        | ✨ Kallos | Claude Haiku 4.5 |
        | 📜 Mneme | Claude Haiku 4.5 |

    === "`standard`"

        Sonnet for heavy lifting, Haiku for lightweight. Balanced cost and quality.

        | Agent | Model | Why |
        |---|---|---|
        | 🔥 Hephaestus | Claude Sonnet 4.6 | Routing decisions need to be accurate |
        | 📐 Metis | Claude Sonnet 4.6 | Spec generation needs strong reasoning |
        | ⚙️ Techne | Claude Sonnet 4.6 | Code generation needs strong reasoning |
        | 🧪 Dokimasia | Claude Haiku 4.5 | Test execution is mostly subprocess |
        | ✨ Kallos | Claude Haiku 4.5 | Mostly subprocess work; LLM only for comment analysis |
        | 📜 Mneme | Claude Haiku 4.5 | Commit messages are structured and formulaic |

    === "`smart`"

        Maximum quality — highest cost, best output quality across the board.

        | Agent | Model | Why |
        |---|---|---|
        | 🔥 Hephaestus | Claude Sonnet 4.6 | Routing decisions need to be fast and accurate |
        | 📐 Metis | Claude Opus 4.6 | Planning quality determines everything downstream |
        | ⚙️ Techne | Claude Sonnet 4.6 | Code generation needs strong reasoning |
        | 🧪 Dokimasia | Claude Sonnet 4.6 | Test generation needs code understanding |
        | ✨ Kallos | Claude Sonnet 4.6 | Higher quality comment analysis |
        | 📜 Mneme | Claude Sonnet 4.6 | Better commit message grouping |

=== "Google (Gemini) :material-google:"

    Set `KOURAI_PROVIDER=google` and add your `GEMINI_API_KEY`. Tiers map to Claude capability equivalents:

    | Tier | Model | Claude equivalent |
    |---|---|---|
    | `cheap` | Gemini 2.0 Flash | Haiku 4.5 |
    | `standard` | Gemini 2.5 Pro (heavy) / Flash (light) | Sonnet 4.6 / Haiku 4.5 |
    | `smart` | Gemini 2.5 Pro | Opus 4.6 |

=== "Local / Ollama :material-server: (free)"

    Set `KOURAI_PROVIDER=local` to use these via [Ollama](https://ollama.com/):

    | Agent | Model | VRAM |
    |---|---|---|
    | 🔥 Hephaestus | llama3.3:70b | ~40GB |
    | 📐 Metis | llama3.3:70b | ~40GB |
    | ⚙️ Techne | llama3.3:70b | ~40GB |
    | 🧪 Dokimasia | qwen2.5-coder:32b | ~20GB |
    | ✨ Kallos | llama3.3:8b | ~5GB |
    | 📜 Mneme | llama3.3:8b | ~5GB |

    No per-token charges. You pay electricity and hardware only.

---

## Agent Ports

Each agent runs on a fixed port:

| Agent | Port | Health check |
|---|---|---|
| Hephaestus | `10000` | `http://localhost:10000/.well-known/agent-card.json` |
| Metis | `10001` | `http://localhost:10001/.well-known/agent-card.json` |
| Techne | `10002` | `http://localhost:10002/.well-known/agent-card.json` |
| Dokimasia | `10003` | `http://localhost:10003/.well-known/agent-card.json` |
| Kallos | `10004` | `http://localhost:10004/.well-known/agent-card.json` |
| Mneme | `10005` | `http://localhost:10005/.well-known/agent-card.json` |

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

---

## Text-to-Speech Configuration

The GUI includes a full text-to-speech system with neural voices and real-time audio control. Configure it in `~/.kourai_khryseai/settings.json` or through the settings overlay (`Press S` in GUI).

### TTS Dependencies

Automatically installed with `make setup`:

```toml
[project]
dependencies = [
    "edge-tts>=0.30.0",           # Microsoft neural voice synthesis
    "pygame-ce>=2.5.0",            # Enhanced audio mixer (community edition)
]
```

### TTS Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `tts_enabled` | bool | `true` | Enable/disable speech synthesis |
| `master_volume` | float | `0.8` | Master volume (0.0-1.0) |
| `voice_pacing` | enum | `NORMAL` | Speech pacing mode |
| `reading_speed` | int | `30` | Milliseconds per character for thinking pauses |
| `thinking_pauses` | bool | `true` | Add pause before agent responses |

### Voice Pacing Modes

| Mode | Delay | Use Case |
|------|-------|----------|
| **INSTANT** | 0s | No pauses, immediate response |
| **FAST** | 0.5s | Quick interactions |
| **NORMAL** | 1.5s | Balanced pacing (default) |
| **SLOW** | 3.0s | Light-novel style, immersive |
| **CUSTOM** | User-defined | Custom millisecond-based timing |

### Voice Personality Profiles

Each agent's voice is optimized for personality. Customize per-agent characteristics through the TTS settings:

```json
{
  "tts_agent_voices": {
    "hephaestus": {"voice": "Guy", "speed": 0.95, "pitch": 1.0},
    "metis": {"voice": "Aria", "speed": 0.90, "pitch": 1.1},
    "kallos": {"voice": "Jenny", "speed": 1.05, "pitch": 1.15},
    "mneme": {"voice": "Michelle", "speed": 0.92, "pitch": 0.95},
    "techne": {"voice": "Sonia", "speed": 0.93, "pitch": 1.05},
    "dokimasia": {"voice": "Aria", "speed": 0.88, "pitch": 1.0}
  }
}
```

### Audio Quality Settings

**Sample Rate:** 44.1 kHz (CD quality) — fixed for compatibility  
**Depth:** 16-bit — fixed for quality  
**Format:** MP3 — ~90% smaller than WAV, still high quality  
**Buffer:** 512 bytes — <100ms latency  

### Advanced Features

**Volume Normalization:**
- Peak normalization prevents clipping
- RMS loudness normalization ensures consistency
- Automatic loudness metering in LUFS (professional standard)

**Fade Effects:**
- Smooth fade-in for dialogue start
- Fade-out for transitions
- Configurable fade duration (100-500ms)

**Real-Time Control:**
- Adjust volume while speaking: `engine.set_master_volume(0.6)`
- Modulate pitch on-the-fly: `await engine.speak(text, pitch=1.2)`
- Adjust speed: `await engine.speak(text, speed=1.3)`

### For Technical Details

See [Architecture → TTS System](architecture/tts.md) for complete API reference, audio processing pipeline, performance metrics, and advanced usage examples.

---

## Makefile Commands

| Command | Description |
|---|---|
| `make setup` | Install all dependencies (`uv sync --all-packages`) |
| `make cli` | Launch the interactive CLI client |
| `make gui` | Launch the visual GUI with voice synthesis |
| `make up` | Start all agents in Docker + Jaeger + Prometheus (build + wait healthy) |
| `make down` | Stop all Docker containers from the full profile |
| `make status` | Show Docker service status and health |
| `make lint` | Run ruff + mypy |
| `make test` | Run linters + full test suite with coverage |
| `make clean` | Remove `__pycache__`, `.pytest_cache`, build artifacts |
| `make docs` | Serve documentation locally (Zensical) |
| `make upgrade` | Update all dependencies to latest versions |
| `make restart` | Restart all agents (`make down` then `make up`) |
| `make dev` | Full workflow: restart services + launch GUI |
| `make help` | Show all available commands |
