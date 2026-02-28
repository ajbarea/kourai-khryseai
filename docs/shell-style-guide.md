# Shell Style Guide

This guide documents the established patterns for shell scripts in the **Kourai Khryseai** project.

## Quick Reference

- **Shebang:** `#!/bin/bash`
- **Line length:** 100 characters max
- **Formatting:** ShellCheck v0.11.0+
- **Comments:** `# ` (hash + space)
- **Function docs:** Google Shell Style Guide format

## File Headers

Every shell script must have a file header immediately after the shebang.

```bash
#!/bin/bash
# Brief description of the script's purpose.
#
# Usage: ./script_name [OPTIONS]
#
# Dependencies: python3, uv, docker
```

## Function Documentation

Functions must have header comments following Google Shell Style Guide format.

```bash
# Log an informational message.
#
# Arguments:
#   $1: Message to log
log_info() {
    echo "✅ $1"
}
```

## Section Separators

Use 76 `=` characters for section separators.

```bash
# ============================================================================
# Agent Orchestration
# ============================================================================
```

## Comment Quality

### Remove WHAT Comments

Comments that restate what the code does provide no value.

```bash
# ❌ BAD: Restates the code
# Check if uv exists
if command -v uv &> /dev/null; then
```

### Keep WHY Comments

Comments that explain rationale, context, or design decisions are valuable.

```bash
# ✅ GOOD: Explains rationale
# Use uv for faster dependency resolution than standard pip.
uv sync
```

## Phrasing Patterns

- Use **active voice**: "Install dependencies"
- Use **present tense**: "Cleans artifacts"
- Use **imperative**: "Run this script"

## Cross-Reference

- [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- [Python Style Guide](python-style-guide.md)
- [Frontend Style Guide](frontend-style-guide.md)

---

*Last Updated: 2026-02-28*
