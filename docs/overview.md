# Overview

## :material-compass-outline: What is this?

Kourai Khryseai is a **multi-agent development system** where six AI specialists collaborate through the [A2A protocol](https://a2a-protocol.org) to handle the full software development lifecycle.

You describe what you want. They build it.

```
$ kourai "implement CSV export with tests"

🔥 Hephaestus → 📐 Metis → ⚙️ Techne → 🧪 Dokimasia → ✨ Kallos → 📜 Mneme

feat(parser): add CSV export support
- Added parse_csv() function with streaming reader
- Integrated with existing data pipeline
Files: src/utils/parser.py, src/api/endpoints.py
```

---

## :material-layers-outline: Built With

| | |
|---|---|
| :material-api: **Protocols** | [A2A v0.4](https://a2a-protocol.org) · [MCP](https://modelcontextprotocol.io/) |
| :material-language-python: **Language** | Python 3.12+ · modern type hints · Google docstrings |
| :material-brain: **LLM** | [LiteLLM](https://docs.litellm.ai/) — Claude, Gemini, or Ollama |
| :material-tray-full: **Infrastructure** | Docker · uv workspaces · OpenTelemetry → Jaeger |
| :material-book-open-variant: **Docs** | [Zensical](https://zensical.dev) |

---

> *In Greek mythology, Hephaestus forged the Κοῦραι Χρύσεαι — golden woman-shaped automatons — to serve as attendants in his divine workshop. Each agent in this system is named after a Greek concept matching their role.*
