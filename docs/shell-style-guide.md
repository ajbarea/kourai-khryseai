# Shell Style Guide

Standards for shell scripts in Kourai Khryseai. Enforced by [ShellCheck](https://www.shellcheck.net/).

## Quick Reference

| | |
|---|---|
| **Shebang** | `#!/bin/bash` |
| **Line length** | 100 characters |
| **Linter** | ShellCheck v0.11.0+ |
| **Comments** | `# ` (hash + space) |
| **Functions** | Google Shell Style Guide format |

---

## File Headers

Every script starts with a shebang and a brief purpose:

```bash
#!/bin/bash
# Update all workspace dependencies and regenerate lock files.
#
# Usage: ./scripts/update_dependencies.sh
#
# Dependencies: uv, python3
```

---

## Functions

Header comments using Google Shell Style Guide format:

```bash
# Start an agent process in the background.
#
# Arguments:
#   $1: Agent name (e.g., "mneme", "kallos")
#   $2: Port number
start_agent() {
    local agent_name="$1"
    local port="$2"
    uv run python -m "agents.${agent_name}" > "logs/${agent_name}.log" 2>&1 &
    echo "✅ ${agent_name} started on :${port}"
}
```

---

## Section Separators

Use 76 `=` characters:

```bash
# ============================================================================
# Agent Orchestration
# ============================================================================
```

---

## Comments

### Remove WHAT comments

```bash
# ❌ Restates the code
# Check if uv exists
if command -v uv &> /dev/null; then
```

### Keep WHY comments

```bash
# ✅ Explains rationale
# Use uv for faster dependency resolution than pip
uv sync --all-packages
```

---

## Style

- **Active voice:** "Install dependencies"
- **Present tense:** "Cleans build artifacts"
- **Imperative mood:** "Run this script"
- Quote all variable expansions: `"${var}"` not `$var`
- Use `local` for function variables

---

**References:** [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html) · [Python Guide](python-style-guide.md) · [Frontend Guide](frontend-style-guide.md)
