# Configuration

All configuration is managed through environment variables in `.env` (or exported in your shell). Copy `.env.example` to get started:

```bash
cp .env.example .env
```

The `.env.example` file is intentionally minimal — it only contains variables you need to set. Everything else has sensible defaults in code and can be overridden in `.env` when needed.

---

## Required Settings

### LLM Provider

```bash title=".env"
KOURAI_PROVIDER=anthropic          # anthropic | google | local
KOURAI_MODEL_TIER=cheap            # cheap | standard | smart
```

### API Keys

Set the key matching your provider:

| Provider | Variable | Where to get it |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `google` | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `local` | *(none)* | [Ollama](https://ollama.com/) runs locally |

---

## Optional Integrations

These are all optional. The system works without them — features that need a missing key are skipped gracefully.

### GitHub

Used by Mneme (PR generation), Techne (code search), Metis, and Hephaestus.

```bash
GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_xxxx...
```

Create a token at [github.com/settings/tokens](https://github.com/settings/tokens) with scopes: `repo`, `read:org`, `gist`.

### Brave Search

Used by Aletheia for web search and claim verification.

```bash
BRAVE_API_KEY=YOUR_BRAVE_API_KEY
```

Sign up at [brave.com/search/api](https://brave.com/search/api/).

### HuggingFace (Artifact Storage)

Enables agent artifact sync and automated backups to HF Storage Buckets. Without this, artifacts save to local Docker volumes only.

```bash
HF_TOKEN=hf_xxx...
```

Create a write-scope token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). The bucket ID is auto-derived as `<your-username>/kourai-artifacts` via the HF API. Override with `KOURAI_BUCKET_ID` if needed.

### Player Project Database

Used by Techne and Dokimasia for database schema introspection. Only needed for database-backed player projects.

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mydb
```

### Docker Hub

For pushing built images and build cache.

```bash
DOCKER_HUB_USERNAME=your-username
```

Setup: create an account at [hub.docker.com](https://hub.docker.com), create a PAT under Security settings, then `docker login`.

### OpenAI (Fallback)

Optional fallback provider via LiteLLM.

```bash
OPENAI_API_KEY=sk-proj-...
```

---

## Defaults & Overrides

These variables have sensible defaults in code. You only need to set them if you want to change the default behavior.

### Agent Behavior

| Variable | Default | Description |
|---|---|---|
| `KOURAI_LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `KOURAI_MAX_ITERATIONS` | `5` | Max Kallos / Techne feedback loop iterations before giving up |
| `KOURAI_STREAM_ENABLED` | `true` | Enable SSE streaming for real-time progress |

### Infrastructure & Observability

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Jaeger OTLP HTTP endpoint (overridden to `http://jaeger:4318` in Docker Compose) |
| `ENVIRONMENT` | `development` | Environment tag for traces |
| `SERVICE_VERSION` | `0.1.0` | Version tag for traces |

### Local LLM (Ollama)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama server URL. Only needed if running Ollama on a non-default address |

When `KOURAI_PROVIDER=local`, `make setup` will check Ollama connectivity and auto-pull required models.

### Artifact & Backup Settings

| Variable | Default | Description |
|---|---|---|
| `KOURAI_BUCKET_ID` | *(auto-derived: `<username>/kourai-artifacts`)* | HF Storage Bucket for agent artifacts. Auto-resolved from your HF token |
| `BACKUP_USER` | *(auto-detected from HF_TOKEN)* | HuggingFace username for backup ownership |
| `BACKUP_BUCKET_NAME` | `kourai-backups` | HF bucket name for player data backups |
| `BACKUP_RETENTION_DAYS` | `30` | Days to retain old backups before cleanup |

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
        | 🎭 Puck | Claude Haiku 4.5 |
        | 💘 Cupid | Claude Haiku 4.5 |
        | 🪞 Aidos | Claude Haiku 4.5 |
        | 📚 Aletheia | Claude Haiku 4.5 |

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
        | 🎭 Puck | Claude Haiku 4.5 | Companion dialogue — fast and light |
        | 💘 Cupid | Claude Haiku 4.5 | Relationship coaching — fast and light |
        | 🪞 Aidos | Claude Haiku 4.5 | Regex pre-screening handles most work |
        | 📚 Aletheia | Claude Sonnet 4.6 | Research validation benefits from reasoning |

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
        | 🎭 Puck | Claude Haiku 4.5 | Companion dialogue — personality over power |
        | 💘 Cupid | Claude Sonnet 4.6 | Deeper emotional context building |
        | 🪞 Aidos | Claude Haiku 4.5 | Fast regex screening, no heavy reasoning needed |
        | 📚 Aletheia | Claude Sonnet 4.6 | Research validation benefits from reasoning |

=== "Google (Gemini) :material-google:"

    Set `KOURAI_PROVIDER=google` and add your `GEMINI_API_KEY`. Tiers map to Claude capability equivalents:

    | Tier | Model | Claude equivalent |
    |---|---|---|
    | `cheap` | Gemini 2.0 Flash (all agents) | Haiku 4.5 |
    | `standard` | Gemini 2.5 Pro (heavy) / Flash (light) | Sonnet 4.6 / Haiku 4.5 |
    | `smart` | Gemini 2.5 Pro (all agents) | Opus 4.6 |

    !!! warning "Google free tier"
        Free tier prompts are used to improve Google's products. Switch to Paid tier in AI Studio to opt out.

=== "Local / Ollama :material-server: (free)"

    Set `KOURAI_PROVIDER=local` to use these via [Ollama](https://ollama.com/):

    | Agent | Model | VRAM |
    |---|---|---|
    | 🔥 Hephaestus, 📐 Metis, ⚙️ Techne | llama3.3:70b | ~40GB |
    | 🧪 Dokimasia | qwen2.5-coder:32b | ~20GB |
    | ✨📜🎭💘🪞 Others | llama3.3:8b | ~5GB |
    | 📚 Aletheia | llama3.3:70b | ~40GB |

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
| Puck | `10006` | `http://localhost:10006/.well-known/agent-card.json` |
| Cupid | `10007` | `http://localhost:10007/.well-known/agent-card.json` |
| Aidos | `10008` | `http://localhost:10008/.well-known/agent-card.json` |
| Aletheia | `10009` | `http://localhost:10009/.well-known/agent-card.json` |

---

## Timeouts

Per-agent timeouts are defined in `shared/src/kourai_common/config.py`:

| Operation | Timeout | Notes |
|---|---|---|
| Agent card fetch | 5s | Initial connection to discover agent capabilities |
| Mneme | 30s | Lightweight commit message generation |
| Puck | 30s | Companion dialogue |
| Kallos | 60s | Linting is fast; comment analysis takes longer |
| Cupid | 60s | Relationship context building |
| Aidos | 60s | Anti-slop analysis |
| Techne | 120s | Code generation with large context |
| Dokimasia | 120s | Test generation and execution |
| Metis | 120s | Spec generation with project context |
| Aletheia | 120s | Research validation with claim checking |
| Full pipeline | 600s | End-to-end timeout for the CLI |

---

## Docker Networking

Agents resolve each other via Docker service names on the `kourai` bridge network (e.g., `http://techne:10002/`). This is handled automatically by Docker Compose — no user configuration needed.

---

## Text-to-Speech Configuration

The Pygame GUI includes a full text-to-speech system with neural voices and real-time audio control. Configure it in `~/.kourai_khryseai/settings.json` or through the settings overlay.

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

See [GUI Reference](gui.md#text-to-speech-system-) for voice profiles and audio customization.

---

## Makefile Commands

| Command | Description |
|---|---|
| `make setup` | Install all dependencies (`uv sync --all-packages`) |
| `make cli` | Launch the interactive CLI client |
| `make gui` | Launch the visual GUI with voice synthesis |
| `make up` | Start all agents in Docker + Jaeger + Prometheus |
| `make down` | Stop all Docker containers |
| `make status` | Show Docker service status and health |
| `make lint` | Run ruff + ty |
| `make test` | Run linters + full test suite with coverage |
| `make clean` | Remove `__pycache__`, `.pytest_cache`, build artifacts |
| `make docs` | Serve documentation locally (Zensical) |
| `make upgrade` | Update all dependencies to latest versions |
| `make restart` | Restart all agents (`make down` then `make up`) |
| `make dev` | Full workflow: restart services + launch GUI |
| `make help` | Show all available commands |
