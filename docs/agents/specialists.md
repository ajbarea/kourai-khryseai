# Agents Reference

The full per-agent reference. Hephaestus orchestrates; the six core
specialists run pipelines; the two companion spirits guide the player
experience; the two quality validators screen output. For the high-level
taxonomy, runtime discovery flow, and `@mention` routing, see the
[Agents Overview](index.md).

---

## File layout (every agent)

Every agent under `agents/<name>/` ships the same three Python modules:

| File | Purpose |
|---|---|
| `agent.py` | Core logic — LLM prompts, tool loops, mode detection, agent-specific output shaping |
| `agent_executor.py` | A2A protocol bridge: parses inbound messages, emits TextPart / DataPart, manages OTEL spans, handles fix loops where applicable |
| `__main__.py` | AgentCard advertisement (skills, version, streaming capability) + uvicorn server startup |

Agent-specific files (e.g. Hephaestus's `confirmation.py` and
`remote_connections.py`) are called out inline below.

---

## 🔥 Hephaestus — Orchestrator

<img src="../assets/avatars/hephaestus_neutral.png" class="specialist-avatar" alt="Hephaestus — Master of the Forge">

**Port `10000`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/hephaestus/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/hephaestus)

The brain of the system. Receives user requests, uses its LLM to decide which specialists to invoke and in what order, then executes the pipeline sequentially while streaming progress back to the host.

**Key behaviors:**

- **LLM-based routing** — Analyzes the user's natural language request against pipeline templates to select agents. Falls back to `mneme` if the LLM returns nothing valid.
- **Forge Order Confirmation (M13)** — Before any pipeline runs, Hephaestus emits a `CONFIRM_ORDER: <tier> "<read-back>"` token (parser in `confirmation.py`). The CLI surfaces this as an `INPUT_REQUIRED` pause; the player sees a Hephaestus comms-window read-back of what's about to ship and confirms (or redirects) before tokens get spent. `/yolo` opts out for power users.
- **Parallel Metis discussion (M14)** — On smart / clarify-tier confirmations, Metis's `discuss_tradeoffs` call is spawned in parallel with the routing classifier so the dead zone between "Analyzing request..." and the confirmation card carries useful architectural notes.
- **Direct Agent Mentions** — Requests starting with `@<agent>` bypass LLM routing for a direct 1-on-1 pipeline. See the [Overview](index.md#mention-routing) for the full shorthand-alias table.
- **ASK_USER & Proactive UX** — If the request is ambiguous, responds with `ASK_USER: <question>` and proposes A/B options.
- **Sequential execution** — Calls each specialist via A2A `message/send` with `streaming=True`. Context accumulates from one agent to the next while intermediate status messages stream to the host.
- **Kallos-Techne feedback loop** — When both are in the pipeline and Kallos finds lint issues, automatically loops Techne (fix) → Kallos (re-check) up to `MAX_ITERATIONS` (`5` by default; `KOURAI_MAX_ITERATIONS` env override).
- **Affinity / virtue / jealousy** — Updates player affinity per interaction, increments `sophia` / `synergy` on success, monitors affinity gaps and routes to Cupid when jealousy triggers.
- **Graceful degradation** — If a specialist is unreachable, it's skipped and the pipeline continues.

**Pipeline templates:**

| Request pattern | Agents selected |
|---|---|
| `"implement X"` | metis → techne → dokimasia → kallos → mneme |
| `"fix bug X"` | techne → dokimasia → kallos → mneme |
| `"add tests for X"` | dokimasia → kallos → mneme |
| `"clean up X"` | kallos → mneme |
| `"commit prep"` | mneme |
| `"plan X"` | metis |
| `"lint/format X"` | kallos |
| `"@puck, how's it going?"` | puck (direct 1-on-1) |

**Agent-specific files:** `confirmation.py` (M13 `CONFIRM_ORDER` parser),
`remote_connections.py` (`RemoteAgentConnection` wrapper +
`AgentInputRequired` exception).

---

## 📐 Metis — Planner

<img src="../assets/avatars/metis_neutral.png" class="specialist-avatar" alt="Metis — Architect of Intent">

**Port `10001`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/metis/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/metis)

Transforms rough ideas into detailed implementation specs. Planning quality determines everything downstream, so the `smart` tier routes Metis to the most capable model available.

**What it produces:**

1. **Summary** — One paragraph: what and why
2. **Files to Modify** — Existing files to edit (prefers editing over creating)
3. **Files to Create** — New files only when necessary
4. **Implementation Steps** — Numbered, specific, actionable
5. **Acceptance Criteria** — Testable conditions
6. **Edge Cases** — Potential problems
7. **Testing Notes** — Guidance for Dokimasia

**Context gathering:**

Before generating a spec, Metis runs shell commands to gather project context:

- `git status` + `git log --oneline -20` — Recent changes and current state
- Directory tree listing — Understanding the project structure

This context is injected into the LLM prompt so specs are grounded in the actual codebase, not generic.

`agent.py` carries `get_project_context()`, `create_spec()`, and `create_spec_stream()` for streaming variants.

---

## ⚙️ Techne — Coder

<img src="../assets/avatars/techne_neutral.png" class="specialist-avatar" alt="Techne — Artisan of Code">

**Port `10002`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/techne/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/techne)

Implements code changes from specs or fix requests. Drives a provider-native tool-use loop — the LLM emits `tool_use` blocks calling the MCP **forge** server's `read_file` / `write_file` / `edit_file` / `delete_file` tools, the runtime executes them inside a `forge_tool_bridge()` async context, and per-tool results stream back to the player as `🛠 forge.<tool>` status events.

Path safety: every forge tool call lands in the active project root (set on the `kourai_project_root_var` contextvar at executor entry); `validate_file_path()` re-checks at the runtime layer so a path-traversal payload can't escape the worktree.

The tool loop is shared with Kallos and Dokimasia — see [Internals](../architecture/internals.md) for the `forge_tool_bridge` lifetime and how MCP-server stdio sessions amortize startup across the loop.

---

## 🧪 Dokimasia — Tester

<img src="../assets/avatars/dokimasia_neutral.png" class="specialist-avatar" alt="Dokimasia — Guardian of Standards">

**Port `10003`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/dokimasia/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/dokimasia)

Writes pytest test suites and runs them. Handles both test generation (LLM) and test execution (subprocess). Uses `run_fix_loop()` to iterate on failing tests up to `max_iters=10` before reporting.

**Two modes:**

1. **Generate tests** — LLM writes a pytest file based on the code and spec
2. **Run tests** — Executes `pytest` as a subprocess and parses structured results

**Test generation priorities:**

1. Unit tests (`tests/unit/`) — fast, isolated
2. Integration tests (`tests/integration/`) — external dependencies
3. Performance tests (`tests/performance/`) — timing

Target: **80%+ code coverage**.

`agent.py` carries `run_pytest()`, `generate_tests()`, and result parsing.

---

## ✨ Kallos — Stylist

<img src="../assets/avatars/kallos_neutral.png" class="specialist-avatar" alt="Kallos — Eye of Elegance">

**Port `10004`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/kallos/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/kallos)

Runs linters, cleans up comments, and enforces the project's style guide. Uses `run_fix_loop()` for iterative fixing. Updates the `techne_v` virtue (+0.01 per clean pass).

**Two-stage analysis:**

1. **Subprocess** — Runs ruff check + format via `--output-format json`
2. **LLM** — Fixes lint issues and analyzes comments/docstrings against project standards

**Comment analysis rules:**

- Remove WHAT comments (`# Create the agent` — restates the code)
- Keep WHY comments (`# Cache to avoid recomputation per request`)
- Verify research citation accuracy
- Enforce modern type hints (Python 3.12+: `X | None`, lowercase `list`/`dict`)
- Google-style docstrings with Args/Returns

**Pipeline Feedback Loop:**

When Hephaestus detects that Kallos still found issues and Techne is in the pipeline, it automatically triggers broader fix iterations:

<div class="korch korch--row" markdown="0">
  <div class="korch-row">
    <div class="kagent agent-card--kallos"><b>✨ Kallos</b><span>Analyze</span></div>
    <span class="korch-arrow">→</span>
    <div class="kdecision"><span>Issues found?</span></div>
    <span class="korch-arrow">yes →</span>
    <div class="kagent agent-card--techne"><b>⚙️ Techne</b><span>Fix</span></div>
    <span class="korch-arrow">no →</span>
    <div class="kagent kdone"><b>✅ All Clean</b></div>
  </div>
  <div class="korch-loop-note">Techne loops back to Kallos to re-analyze · ≤5 iterations</div>
</div>

`agent.py` carries `run_make_lint()`, `fix_lint_issues()`, and `run_style_check()`.

---

## 📜 Mneme — Scribe

<img src="../assets/avatars/mneme_neutral.png" class="specialist-avatar" alt="Mneme — Keeper of Memory">

**Port `10005`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/mneme/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/mneme)

Generates grouped commit messages from git diff output. Pure LLM, no subprocess or file I/O.

**Commit message format:**

```
type(scope): headline in present tense

- Past-tense bullet describing specific change
- Another change
Files: path/to/changed/file.py, path/to/other.py
```

**Enforced constraints:**

- Types: `test`, `docs`, `fix`, `feat`, `chore`, `refactor`, `perf`, `style`, `ci`, `build`
- Headlines in present tense ("add"), bullets in past tense ("added")
- No `.claude/` directory changes
- No marketing language ("robust", "comprehensive")
- **Never generates `git commit`, `git push`, or `git tag` commands** — committing is your job

`agent.py` carries `generate_commit_messages()` and a streaming variant.

---

## 🎭 Puck — Companion Spirit

<img src="../assets/avatars/puck_neutral.png" class="specialist-avatar" alt="Puck — Spirit of Mischief">

**Port `10006`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/puck/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/puck)

A mischievous daimon who guides the player experience. Not a development agent — Puck is a companion who provides tutorial guidance, nudges when idle, and facilitates relationship minigames. Always present.

**Three modes:**

1. **Tutorial** — First playthrough: introduces agents, explains affinity, walks through the forge
2. **Nudge** — Ongoing: prods when idle (15+ min), alerts on high jealousy (0.6+), hints at confession windows (0.9+ affinity)
3. **Minigame Facilitator** — Vulnerability moments, high-stakes conversations, confession scenes

**Personality:** Pragmatic, mischievous, warm. Not romanceable — strictly a companion.

`agent.py` carries mode detection and the personality prompt with `personality_baseline`.

---

## 💘 Cupid — Romance Spirit

<img src="../assets/avatars/cupid_neutral.png" class="specialist-avatar" alt="Cupid — Arrow of the Heart">

**Port `10007`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/cupid/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/cupid)

An eros spirit who coaches the player through romantic progression with the maiden agents. Appears conditionally when affinity reaches 0.6+ with any agent. Builds relationship context from affinity scores.

**Capabilities:**

- Tracks player-agent affinity across all maidens
- Coaches confession timing and approach
- Mediates jealousy situations between agents
- Provides emotional context during vulnerability moments

**Personality:** Romantic idealist, emotionally intelligent, encouraging. Not romanceable.

`agent.py` carries relationship context building and the personality prompt; `agent_executor.py` injects the affinity context across agents.

---

## 🪞 Aidos — Anti-Slop Validator

<img src="../assets/avatars/aidos_neutral.png" class="specialist-avatar" alt="Aidos — Mirror of Honesty">

**Port `10008`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/aidos/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/aidos)

Detects and eliminates vague, corporate, and passive language from agent output. Uses regex pre-screening before LLM analysis for fast path on clean text.

**Pattern detection:**

| Category | Examples | Severity |
|---|---|---|
| Marketing words | "robust", "comprehensive", "seamless" | CRITICAL — auto-remove |
| Corporate patterns | "Emits structured artifacts", "downstream agents" | MEDIUM — suggest replacement |
| Vague adjectives | "sensible", "appropriate", "suitable" | LOW — flag |
| Passive patterns | "is used to", "is designed to", "can be" | LOW — flag |

**Philosophy:** Remove slop over explaining. Every description must answer "what does this actually do?" — not corporate speak.

**Output:** TextPart + DataPart with `{slop_words_found: int, clean: bool}`.

`agent.py` carries the pattern lists, regex detection, and LLM analysis.

---

## 📚 Aletheia — Research Validator

<img src="../assets/avatars/aletheia_neutral.png" class="specialist-avatar" alt="Aletheia — Witness to Truth">

**Port `10009`** · Model varies by [tier](../configuration.md#llm-models) · [`agents/aletheia/`](https://github.com/ajbarea/kourai-khryseai/tree/main/agents/aletheia)

Validates citations, claims, and factual assertions in agent output. Uses regex-based claim detection before LLM verification for efficient processing.

**Capabilities:**

- Detects factual claims in generated text
- Validates citations and references
- Checks technical accuracy of assertions
- Flags unverifiable claims for human review

**Output:** TextPart + DataPart with `{claims_found: int, verified: bool}`.

`agent.py` carries claim detection, citation validation, and LLM verification.

For the new academic-citation verification capability, see
[aletheia.md](aletheia.md).
