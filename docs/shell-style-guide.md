# Shell Script Style Guide

This guide documents the established patterns for shell scripts in the IntelliFL project. All shell scripts should follow these conventions to maintain consistency across the codebase.

## Quick Reference

- Shebang: `#!/bin/bash`
- Line length: 100 characters max
- Section separators: 76 `=` characters
- Comments: `# ` (hash + space)
- Function docs: Google Shell Style Guide format

## File Headers

Every shell script must have a file header immediately after the shebang.

### Executable Scripts

```bash
#!/bin/bash
# Brief one-line description of what the script does.
#
# Longer description if needed, explaining the purpose and behavior.
# Can span multiple lines.
#
# Usage: ./script_name [OPTIONS] [ARGUMENTS]
#
# Options:
#   --flag    Description of flag
#   --option  Description of option
#
# Examples:
#   ./script_name --flag
#   ./script_name --option value
#
# Dependencies: tool1, tool2 (optional: tool3)
```

### Library Scripts (Sourced by Other Scripts)

```bash
#!/bin/bash
# Brief one-line description of the library's purpose.
#
# This library provides utilities for X, Y, and Z.
# Source this file to access its functions - do not execute directly.
#
# Function Categories:
#   - Category 1: Description
#   - Category 2: Description
#
# Dependencies: tool1, tool2
```

### Real Example (from setup.sh)

```bash
#!/bin/bash
# Complete project setup for IntelliFL.
#
# Installs both Python and frontend dependencies in a single command.
# This is the recommended first step after cloning the repository.
#
# Usage: ./setup.sh
#
# What it does:
#   1. Creates Python virtual environment and installs dependencies
#   2. Installs frontend npm packages (React, Vite, ESLint, etc.)
#
# Dependencies: python3 (3.10-3.13), npm
#
# Example:
#   ./setup.sh
```

## Function Documentation

Functions must have header comments following Google Shell Style Guide format.

### Template

```bash
# Brief one-line description of what the function does.
#
# Longer description if needed, explaining the purpose and behavior.
# Can span multiple lines.
#
# Arguments:
#   $1: Description of first argument
#   $2: Description of second argument (optional)
#
# Returns:
#   0: Success
#   1: Error condition description
#
# Globals:
#   VAR_NAME: Description of how this global is used/modified
#
# Example:
#   function_name "arg1" "arg2"
function_name() {
    # Implementation
}
```

### Real Example (from common.sh)

```bash
# Log an informational message to stdout and optionally to a log file.
#
# Arguments:
#   $1: Message to log
#
# Globals:
#   LOG_FILE: If set, message is appended to this file
log_info() {
    if [ -n "${LOG_FILE:-}" ]; then
        echo "✅ $1" | tee -a "$LOG_FILE"
    else
        echo "✅ $1"
    fi
}
```

## Section Separators

Use section separators to organize large scripts into logical sections.

### Format

```bash
# ============================================================================
# Section Name
# ============================================================================
```

- Use 76 `=` characters (fits within 100-char limit with `# ` prefix)
- Blank line before and after the separator block
- Title case for section names

### Real Example (from common.sh)

```bash
# ============================================================================
# Logging
# ============================================================================

log_info() { ... }
log_error() { ... }

# ============================================================================
# System
# ============================================================================

command_exists() { ... }
```

## Comment Quality

### Remove WHAT Comments

Comments that restate what the code does provide no value and should be removed.

```bash
# ❌ BAD: Restates the code
# Check if wget exists
if command_exists wget; then

# ❌ BAD: Duplicates log message
# Log info message
log_info "Starting download..."

# ❌ BAD: Restates variable assignment
# Set the venv directory
VENV_DIR="$VIRTUAL_ENV"
```

### Keep WHY Comments

Comments that explain rationale, context, or design decisions are valuable.

```bash
# ✅ GOOD: Explains WHY (rationale)
# Prefer wget for better progress reporting and resume capability.
# Fall back to Python's urllib if wget is unavailable (minimal dependencies).
if command_exists wget; then
    wget "$DATASET_URL"
else
    run_python -c "import urllib.request; ..."
fi

# ✅ GOOD: Explains non-obvious behavior
# Wait briefly if venv directory exists but activation scripts don't yet.
# On Windows, venv creation may not be atomic.
if [ ! -d ".venv/Scripts" ] && [ ! -d ".venv/bin" ] && [ -d ".venv" ]; then
    sleep 1
fi

# ✅ GOOD: Explains platform-specific behavior
# Windows: /T kills child processes, /F forces termination.
taskkill //F //T //PID $API_PID 2>/dev/null || true
```

## Formatting Rules

### Comment Syntax

- Always use `# ` (hash followed by space)
- Place comments on their own line above the code they describe
- Use blank lines to separate comment blocks from code
- Align comments at the same indentation level as the code

### Capitalization and Punctuation

- Use sentence case for comments (capitalize first word)
- End complete sentence comments with a period
- Use title case for section headers

### Line Length

- Keep comment lines to 100 characters or less
- Align with project ruff configuration

## Terminology

Use consistent terminology across all scripts:

| Preferred | Avoid |
|-----------|-------|
| virtual environment | venv (in prose) |
| Python interpreter | Python binary |
| dependencies | requirements (in prose) |
| log file | logfile |

## Phrasing Patterns

- Use active voice: "Install dependencies" not "Dependencies are installed"
- Use present tense for descriptions: "Cleans artifacts" not "Will clean artifacts"
- Use imperative for instructions: "Run this script" not "This script should be run"
- Be specific: "Wait 30-60s for SonarQube initialization" not "Wait for startup"

## ShellCheck

All scripts must pass ShellCheck v0.11.0+ with no warnings.

### Configuration

The project uses `.shellcheckrc` in the root directory:

```bash
# ShellCheck configuration for IntelliFL project
shell=bash
source-path=SCRIPTDIR
```

### Running ShellCheck

```bash
# Check a single script
shellcheck script.sh

# Check all scripts
shellcheck setup.sh run_simulation.sh clean.sh reinstall_requirements.sh \
    run_frontend.sh run_experiments.sh update_dependencies.sh entrypoint.sh \
    tests/lint.sh tests/scripts/common.sh tests/scripts/sonar.sh

# Follow sourced files
shellcheck -x tests/scripts/sonar.sh
```

## Commented-Out Code

- Do not leave commented-out code in scripts
- If code must be temporarily disabled, add a TODO comment explaining why
- Use version control for code history, not inline comments

## TODO Comments

When documenting issues for future work:

```bash
# TODO(username): Brief description of the issue or improvement needed
```

- Include "TODO" in all caps
- Include an identifier (name, email, or username) in parentheses
- Briefly describe the issue

## Script Categories

### Executable Utilities

User-facing scripts with clear purposes. Need comprehensive file headers with usage examples.

Examples: `clean.sh`, `setup.sh`, `reinstall_requirements.sh`

### Library Scripts

Sourced by other scripts. Every function needs documentation.

Examples: `tests/scripts/common.sh`

### Wrapper Scripts

Orchestrate other tools/processes. Document what they wrap and why.

Examples: `run_experiments.sh`, `entrypoint.sh`, `run_frontend.sh`

## Cross-Reference

This style guide aligns with:

- [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- [Python Style Guide](PYTHON_STYLE_GUIDE.md) - Backend code conventions
- [Frontend Style Guide](FRONTEND_STYLE_GUIDE.md) - React + TypeScript conventions
- Project ruff configuration (100-char line limit)

---

*Last Updated: 2026-01-10*
