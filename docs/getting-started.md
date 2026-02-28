# Getting Started

Welcome to **Kourai Khryseai** (The Golden Maidens). This system is a multi-agent framework built on the **A2A (Agent-to-Agent)** and **MCP (Model Context Protocol)** protocols, designed to accelerate software development through specialized AI collaboration.

## 🏛️ The Golden Maiden Architecture

Inspired by the autonomous gold attendants of Hephaestus, the system distributes the development lifecycle across six specialized agents:

| Agent | Role | Port |
| :--- | :--- | :--- |
| 🔥 **Hephaestus** | Orchestrator & Router | `10000` |
| 📐 **Metis** | Planner & Architect | `10001` |
| ⚙️ **Techne** | Lead Programmer | `10002` |
| 🧪 **Dokimasia** | Quality Assurance | `10003` |
| ✨ **Kallos** | Stylist & Linter | `10004` |
| 📜 **Mneme** | Scribe (Commit Generator) | `10005` |

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (highly recommended for performance)
- **Anthropic API Key** (for Claude 3.5/3.7 models)

### 2. Installation
Clone the repository and sync dependencies using `uv`:

```bash
git clone https://github.com/ajbarea/Kourai_Khryseai.git
cd Kourai_Khryseai
uv sync
```

### 3. Configuration
Create a `.env` file in the root directory:

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 4. Launching the System
You can start the full stack (Orchestrator + Specialists) using the provided Makefile:

```bash
make up
```

This will launch all six agents as independent microservices. You can verify their status at any time:

```bash
make status
```

## 🛠️ Usage

Interaction with the system is handled through the `kourai` CLI. 

### Implementation Pipeline
To build a new feature from scratch, provide a high-level prompt. Hephaestus will coordinate with Metis to plan, Techne to code, and Dokimasia to test:

```bash
uv run kourai "implement a CSV export utility for the data module"
```

### Commit Generation
If you have local changes and want Mneme to generate logical commit groups:

```bash
uv run kourai "generate commit messages"
```

### Style Cleanup
To have Kallos and Techne collaborate on cleaning up logic and comments:

```bash
uv run kourai "clean up the style in agents/hephaestus/"
```

## 🔍 Observability
Kourai Khryseai supports **OpenTelemetry**. If you have Jaeger running, you can visualize the full A2A trace of every request:

```bash
make jaeger
# View traces at http://localhost:16686
```

---

*For detailed protocol specifications, see the [A2A Reference](#) (Coming Soon).*
