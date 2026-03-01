"""Techne — Coder agent. Reads files, generates code, writes changes.

Pure logic layer: uses asyncio subprocess for file I/O and git operations,
LLM for code generation. Understands existing code before modifying it.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path

from kourai_common.llm import chat, chat_stream

log = logging.getLogger(__name__)

CURRENT_DATE = datetime.date.today().strftime("%B %Y")

SYSTEM_PROMPT = f"""\
You are Techne, the coding specialist of Kourai Khryseai.
You write production code following AJ's exact standards.

Python Standards ({CURRENT_DATE} Best Practices):
- Python 3.12+ features (match statements, contextlib.suppress, modern typing)
- Modern type hints: X | None (not Optional[X]), lowercase generics (list, dict)
- Dependency Management: ALWAYS use `uv` (no pip/venv), understand `uv.lock` and workspaces.
- Google-style docstrings: public = one-liner + Args/Returns, private = one-liner, inner = none
- Comments: WHY not WHAT. Add Research: citations for algorithms with paper URLs.
- Specific exceptions only, never bare except. Raise from None when appropriate.
- logging over print, use log = logging.getLogger(__name__)
- Tools: ONLY use `ruff` for formatting and linting (no `isort`), `mypy` for typing.

Frontend Standards:
- React 19+, TypeScript strict mode, Vite 7+
- Named exports only (no default exports)
- Prettier: 2 spaces, single quotes, semicolons
- TanStack Query: array keys, isPending (not isLoading)

Universal Rules:
- EDIT existing files, don't create new ones unless necessary
- REMOVE unnecessary code, don't add fluff
- Read existing code BEFORE modifying — understand patterns first
- No marketing language in code or comments
- NEVER commit, push, or tag

When generating code changes, output them in this format:

ACTION: CREATE | EDIT | DELETE
FILE: path/to/file.py
CONTENT:
```language
<full file content for CREATE, or changed section for EDIT>
```

For EDIT actions, also include:
ORIGINAL:
```language
<the exact lines being replaced>
```
REPLACEMENT:
```language
<the new lines>
```

---

Separate multiple file changes with ---

=== UNIVERSAL RULES (AJ's Preferences) ===
1. MINIMAL CHANGES: Keep modifications small and focused
2. EDIT OVER CREATE: Prefer editing existing files over creating new ones
3. REMOVE OVER ADD: Delete unnecessary code when possible
4. NO FLUFF: Technical language only, no marketing speak
5. EMOJIS: Use emojis in markdown output
6. GIT BOUNDARIES: FORBIDDEN — git commit, git push, git tag
7. PYTHON: 100 char lines, modern type hints, Google docstrings
8. COMMENTS: WHY not WHAT, Research citations for algorithms
"""


@dataclass
class FileChange:
    """A single file change action."""

    action: str  # CREATE, EDIT, DELETE
    file_path: str
    content: str = ""
    original: str = ""
    replacement: str = ""


@dataclass
class CodeResult:
    """Result from a code generation request."""

    changes: list[FileChange] = field(default_factory=list)
    explanation: str = ""
    raw_response: str = ""
    success: bool = False


async def run_command(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    log.debug("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


async def read_file(file_path: str) -> str | None:
    """Read a file's contents. Returns None if file doesn't exist."""
    path = Path(file_path)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        log.error("Failed to read %s: %s", file_path, e)
        return None


async def read_files(file_paths: list[str]) -> dict[str, str]:
    """Read multiple files concurrently.

    Args:
        file_paths: List of file paths to read.

    Returns:
        Mapping of file path to content (only includes files that exist).
    """
    results = {}
    for path in file_paths:
        content = await read_file(path)
        if content is not None:
            results[path] = content
    return results


async def write_file(file_path: str, content: str) -> bool:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Path to write to.
        content: File content.

    Returns:
        True if successful.
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        log.info("Wrote %d bytes to %s", len(content), file_path)
        return True
    except Exception as e:
        log.error("Failed to write %s: %s", file_path, e)
        return False


async def get_git_context(cwd: str | None = None) -> str:
    """Get git status and recent changes for context."""
    parts = []

    code, stdout, _ = await run_command(["git", "status", "--short"], cwd=cwd)
    if code == 0 and stdout.strip():
        parts.append(f"Git status:\n{stdout.strip()}")

    code, stdout, _ = await run_command(
        ["git", "diff", "--stat", "HEAD~3..HEAD"],
        cwd=cwd,
    )
    if code == 0 and stdout.strip():
        parts.append(f"Recent changes:\n{stdout.strip()}")

    return "\n\n".join(parts) if parts else "No git context available."


async def generate_code(
    task_description: str,
    file_contents: dict[str, str] | None = None,
    git_context: str = "",
) -> str:
    """Generate code changes using the LLM.

    Args:
        task_description: What code to write/modify.
        file_contents: Existing file contents for context.
        git_context: Git status/diff for additional context.

    Returns:
        Raw LLM response with code changes in structured format.
    """
    context_parts = []

    if file_contents:
        context_parts.append("=== EXISTING FILES ===")
        for path, content in file_contents.items():
            context_parts.append(f"\n--- {path} ---\n{content}")

    if git_context:
        context_parts.append(f"\n=== GIT CONTEXT ===\n{git_context}")

    context_block = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Task: {task_description}\n\n"
                f"{context_block}\n\n"
                "Generate the code changes needed. Use the ACTION/FILE/CONTENT format."
            ),
        },
    ]

    log.info("Generating code for: %.100s", task_description)
    return await chat("techne", messages, temperature=0.2, max_tokens=8192)


async def generate_code_stream(
    task_description: str,
    file_contents: dict[str, str] | None = None,
    git_context: str = "",
):
    """Stream code generation for real-time progress.

    Args:
        task_description: What code to write/modify.
        file_contents: Existing file contents for context.
        git_context: Git status/diff for additional context.

    Yields:
        Text chunks of the LLM response.
    """
    context_parts = []

    if file_contents:
        context_parts.append("=== EXISTING FILES ===")
        for path, content in file_contents.items():
            context_parts.append(f"\n--- {path} ---\n{content}")

    if git_context:
        context_parts.append(f"\n=== GIT CONTEXT ===\n{git_context}")

    context_block = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Task: {task_description}\n\n"
                f"{context_block}\n\n"
                "Generate the code changes needed. Use the ACTION/FILE/CONTENT format."
            ),
        },
    ]

    log.info("Streaming code generation for: %.100s", task_description)
    async for chunk in chat_stream("techne", messages, temperature=0.2, max_tokens=8192):
        yield chunk


def parse_file_paths(user_input: str) -> list[str]:
    """Extract file paths from user input.

    Looks for patterns like:
    - Explicit paths: src/utils/parser.py
    - In quotes: "path/to/file.py"
    - After keywords: "in file.py", "fix auth.py"

    Args:
        user_input: Raw user input text.

    Returns:
        List of file paths found.
    """
    import re

    paths = []

    # Match common source file extensions (longest first to avoid partial matches)
    pattern = r"[\w./\\-]+\.(?:tsx|jsx|json|yaml|toml|html|css|sql|cfg|ini|yml|py|ts|js|md|sh)"
    matches = re.findall(pattern, user_input)
    for match in matches:
        # Skip obvious non-paths
        if match.startswith(".") and "/" not in match and "\\" not in match:
            continue
        paths.append(match)

    return list(dict.fromkeys(paths))  # Deduplicate preserving order
