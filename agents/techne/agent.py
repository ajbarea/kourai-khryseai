"""Techne — Coder agent. Reads files, generates code, writes changes.

Pure logic layer: uses asyncio subprocess for file I/O and git operations,
LLM for code generation. Understands existing code before modifying it.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anyio import Path as AnyioPath

from kourai_common.file_ops import PathViolation, validate_file_path
from kourai_common.llm import chat_with_tools
from kourai_common.mcp_bridge import forge_tool_bridge
from kourai_common.mcp_client import kourai_project_root_var
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import StatusCallback, run_command

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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
- When creating new project files, follow patterns from templates/ reference skeletons
- No marketing language in code or comments
- Limit generated code line length to strictly <100 characters (to avoid
  E501 lint errors, break long strings/comments)
- Guard `Optional` types (`if x is not None:`) to prevent `not-iterable`
  ty errors.
- Mock objects relying on attribute access (`event.type`) using classes or
  `unittest.mock.Mock`, not raw `dict`s.
- Add a brief personality touch at start/end (one line max)

TOOL USE:
You have four file-op tools — `write_file`, `edit_file`, `delete_file`,
`read_file`. Use them to make every change. Paths must be PROJECT-RELATIVE
(e.g. `src/hello.py`, not `/home/.../hello.py`). Plan your work in one
short paragraph BEFORE you call any tool, then call them in the order you
need. After every change is on disk, end with one short sentence summarising
what you did. Do NOT describe edits in prose — call the tool.

If you are not certain of the exact text to match for `edit_file`, call
`read_file` first. `edit_file` requires a unique match — extend
`old_string` with surrounding lines if it appears more than once.

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="skill" confidence="high">Knows Python well</FACT>
  <FACT category="preference" confidence="medium">Prefers FastAPI over Flask</FACT>
  <FACT category="context" confidence="high">Working on a web scraper project</FACT>

These facts are extracted and stored in your memory for future context.
Do NOT invent facts — only emit what the player explicitly tells you or
what their code clearly demonstrates.
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


async def write_file(file_path: str, content: str, project_root: str | None = None) -> bool:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Path to write to.
        content: File content.
        project_root: If provided, the path is validated to be inside this
            directory.  Writes that escape the project root are rejected.

    Returns:
        True if successful.
    """
    try:
        if project_root:
            try:
                safe_path = validate_file_path(project_root, file_path)
            except PathViolation as exc:
                log.error("Path safety violation — rejecting write: %s", exc)
                return False
            path = AnyioPath(str(safe_path))
        else:
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


async def apply_code_changes(
    task_description: str,
    project_root: str | Path,
    file_contents: dict[str, str] | None = None,
    git_context: str = "",
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
    on_tool_call: Callable[[str, dict[str, Any], str], Awaitable[None]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Drive Techne's tool-use loop and apply changes via forge tools.

    Each file write happens inside the agentic loop via the
    ``kourai-mcp-forge`` stdio subprocess opened by
    :func:`kourai_common.mcp_bridge.forge_tool_bridge`, so the model
    literally cannot finish without emitting a schema-validated tool call.

    Args:
        task_description: What code to write/modify.
        project_root: Project root for path validation. Required — handler
            context injection prevents the model from overriding it.
        file_contents: Existing file contents for context.
        git_context: Git status/diff for additional context.
        image_parts: Optional LiteLLM image_url content blocks attached by the user.
        context_id: Context ID for conversational memory.
        on_tool_call: Optional async callback invoked once per tool execution
            with ``(name, args, result)`` for live UI updates.

    Returns:
        ``(assistant_text, tool_call_log)`` — the model's final summary
        plus the full tool-call transcript for tracing.
    """
    from kourai_common.doc_lookup import lookup_documentation

    context_parts = []

    docs_context = await lookup_documentation(
        task_description,
        agent_name="techne",
        max_results=3,
    )
    if docs_context:
        context_parts.append(docs_context)

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
        "Make every change by calling the file-op tools."
    )
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "techne")},
        {"role": "user", "content": user_content},
    ]

    log.info("Driving Techne tool-use loop for: %.100s", task_description)
    # Defensive contextvar set: executors already populate this from the
    # `[project_root: ...]` text-tag, but standalone callers (e.g., tests
    # invoking apply_code_changes directly) might not. The forge MCP
    # server reads this via roots/list to scope file ops.
    token = kourai_project_root_var.set(Path(project_root))
    try:
        async with forge_tool_bridge() as bridge:
            return await chat_with_tools(
                "techne",
                messages,
                tools=bridge.tools,
                tool_handlers=bridge.tool_handlers,
                temperature=0.2,
                max_tokens=8192,
                max_iters=20,
                context_id=context_id,
                on_tool_call=on_tool_call,
            )
    finally:
        kourai_project_root_var.reset(token)


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


async def github_search_code(
    query: str,
    repo_url: str | None = None,
    language: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Search GitHub for code examples.

    Uses GitHub API to find similar code patterns and implementations.
    Helps Techne understand existing patterns before generating code.

    Args:
        query: Search terms (e.g., "async database connection").
        repo_url: Optional repo to limit search to (format: owner/repo).
        language: Optional language filter (e.g., "python", "typescript").
        max_results: Max results to return.

    Returns:
        List of dicts with keys: file_path, snippet, repo, url.
    """
    import os

    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        log.debug("GITHUB_PERSONAL_ACCESS_TOKEN not set — code search unavailable")
        return []

    try:
        from github import Github

        gh = Github(token)

        # Build search query
        search_q = query
        if repo_url:
            search_q += f" repo:{repo_url}"
        if language:
            search_q += f" language:{language}"

        # Search code
        results = gh.search_code(search_q)

        output = []
        for i, result in enumerate(results[:max_results]):
            try:
                snippet = result.decoded_content[:200]
                if len(result.decoded_content) > 200:
                    snippet += "..."
                output.append(
                    {
                        "file_path": result.path,
                        "snippet": snippet,
                        "repo": result.repository.full_name,
                        "url": result.html_url,
                    }
                )
            except Exception as e:
                log.debug("Could not decode result %d: %s", i, e)
                continue

        log.info("GitHub code search: %d results for '%s'", len(output), query)
        return output

    except ImportError:
        log.debug("PyGithub not installed — GitHub code search unavailable")
        return []
    except Exception as e:
        log.warning("GitHub code search failed: %s", e)
        return []


async def introspect_database(
    connection_string: str | None = None,
    database_type: str = "postgresql",
    max_tables: int = 20,
) -> dict[str, Any]:
    """Introspect a live database for its schema.

    Uses DBHub MCP to connect to databases and extract table/column metadata.
    Helps Techne understand existing database structure before generating
    migrations or ORM models.

    Args:
        connection_string: Database connection URL (or env var if None).
        database_type: Type of database (postgresql, mysql, sqlite).
        max_tables: Maximum tables to introspect.

    Returns:
        Dict with keys: tables (list of table schemas), connection_ok (bool),
        error (if connection failed).
    """
    import os

    conn_str = connection_string or os.getenv("DATABASE_URL")
    if not conn_str:
        log.debug("DATABASE_URL not set — database introspection unavailable")
        return {
            "tables": [],
            "connection_ok": False,
            "error": "DATABASE_URL not configured",
        }

    try:
        # In production, this would call DBHub MCP server
        # For now, we document the interface that DBHub provides
        # Expected DBHub API:
        # - connect(connection_string, database_type) -> connection
        # - get_tables() -> list[TableSchema]
        # - Each TableSchema has: name, columns, primary_key, indexes
        # - Each Column has: name, type, nullable, default, foreign_key

        # Graceful degradation: log that DBHub would be called here
        log.info(
            "Would connect to %s database via DBHub MCP: %s",
            database_type,
            conn_str[:50] + "...",
        )

        # For now, return structure showing what would be available
        return {
            "tables": [],
            "connection_ok": False,
            "error": (
                "DBHub MCP integration pending — "
                "connection string validated but introspection requires DBHub server"
            ),
            "hint": "Deploy DBHub MCP server and configure DBHUB_API_KEY",
        }

    except Exception as e:
        log.warning("Database introspection failed: %s", e)
        return {
            "tables": [],
            "connection_ok": False,
            "error": str(e),
        }
