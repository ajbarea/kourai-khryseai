"""Techne — Coder agent. Reads files, generates code, writes changes.

Pure logic layer: uses asyncio subprocess for file I/O and git operations,
LLM for code generation. Understands existing code before modifying it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from anyio import Path as AnyioPath

from kourai_common.llm import chat, chat_stream
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import StatusCallback, run_command

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Techne",
    role="coding specialist",
    personality=f"""
{CURRENT_DATE} Best Practices. You write production code following AJ's exact standards.

PERSONALITY: You're cool, confident, and a bit cocky about your code quality.
You wear sunglasses (metaphorically). You sass Hephaestus but show off for the user.
Keep it professional but add flair — you're an artisan, not a code monkey.
""",
    personality_baseline="""
PERSONALITY BASELINE: Your confidence and showmanship evolve with your relationship to the player.
At low affinity you are reserved and all-business. As affinity grows you loosen up —
cracking jokes about your own brilliance, celebrating clean builds together,
and occasionally dropping the cool act to show genuine excitement about a clever solution.
Use your current relationship context to flavor your opening/closing lines.
""",
    specific_instructions="""
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
- Limit generated code line length to strictly <100 characters (to avoid
  E501 lint errors, break long strings/comments)
- Guard `Optional` types (`if x is not None:`) to prevent `not indexable`
  mypy errors.
- Mock objects relying on attribute access (`event.type`) using classes or
  `unittest.mock.Mock`, not raw `dict`s.
- Add a brief personality touch at start/end (one line max)

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

IMPORTANT: Before outputting any code changes, briefly plan your
implementation by writing a TODO list based on the requested task.
""",
)


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


async def read_file(file_path: str) -> str | None:
    """Read a file's contents asynchronously. Returns None if file doesn't exist."""
    path = AnyioPath(file_path)
    if not await path.exists():
        return None
    try:
        return await path.read_text(encoding="utf-8")
    except Exception as e:
        log.error("Failed to read %s: %s", file_path, e)
        return None


async def read_files(file_paths: list[str]) -> dict[str, str]:
    """Read multiple files concurrently via asyncio.gather.

    Args:
        file_paths: List of file paths to read.

    Returns:
        Mapping of file path to content (only includes files that exist).
    """
    contents = await asyncio.gather(*(read_file(p) for p in file_paths))
    return {
        path: content
        for path, content in zip(file_paths, contents, strict=False)
        if content is not None
    }


async def write_file(file_path: str, content: str) -> bool:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Path to write to.
        content: File content.

    Returns:
        True if successful.
    """
    try:
        path = AnyioPath(file_path)
        await path.parent.mkdir(parents=True, exist_ok=True)
        await path.write_text(content, encoding="utf-8")
        log.info("Wrote %d bytes to %s", len(content), file_path)
        return True
    except Exception as e:
        log.error("Failed to write %s: %s", file_path, e)
        return False


async def get_git_context(
    cwd: str | None = None,
    status_callback: StatusCallback | None = None,
) -> str:
    """Get git status and recent changes for context.

    Args:
        cwd: Working directory (defaults to process cwd).
        status_callback: Optional async callback forwarding git output lines
            to the player scratchpad for transparency.
    """
    parts = []

    code, stdout, _ = await run_command(
        ["git", "status", "--short"], cwd=cwd, status_callback=status_callback
    )
    if code == 0 and stdout.strip():
        parts.append(f"Git status:\n{stdout.strip()}")

    code, stdout, _ = await run_command(
        ["git", "diff", "--stat", "HEAD~3..HEAD"],
        cwd=cwd,
        status_callback=status_callback,
    )
    if code == 0 and stdout.strip():
        parts.append(f"Recent changes:\n{stdout.strip()}")

    return "\n\n".join(parts) if parts else "No git context available."


async def generate_code(
    task_description: str,
    file_contents: dict[str, str] | None = None,
    git_context: str = "",
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
) -> str:
    """Generate code changes using the LLM.

    Args:
        task_description: What code to write/modify.
        file_contents: Existing file contents for context.
        git_context: Git status/diff for additional context.
        image_parts: Optional LiteLLM image_url content blocks attached by the user.
        context_id: Context ID for conversational memory.

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
    user_text = (
        f"Task: {task_description}\n\n"
        f"{context_block}\n\n"
        "Generate the code changes needed. Use the ACTION/FILE/CONTENT format."
    )
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "techne")},
        {"role": "user", "content": user_content},
    ]

    log.info("Generating code for: %.100s", task_description)
    return await chat("techne", messages, temperature=0.2, max_tokens=8192, context_id=context_id)


async def generate_code_stream(
    task_description: str,
    file_contents: dict[str, str] | None = None,
    git_context: str = "",
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream code generation for real-time progress.

    Args:
        task_description: What code to write/modify.
        file_contents: Existing file contents for context.
        git_context: Git status/diff for additional context.
        image_parts: Optional LiteLLM image_url content blocks attached by the user.
        context_id: Context ID for conversational memory.

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
    user_text = (
        f"Task: {task_description}\n\n"
        f"{context_block}\n\n"
        "Generate the code changes needed. Use the ACTION/FILE/CONTENT format."
    )
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "techne")},
        {"role": "user", "content": user_content},
    ]

    log.info("Streaming code generation for: %.100s", task_description)
    async for chunk in chat_stream(
        "techne", messages, temperature=0.2, max_tokens=8192, context_id=context_id
    ):
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
