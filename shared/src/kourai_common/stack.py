"""Default tech stack definitions for player project scaffolding.

Agents (Metis, Techne) import these to know which technologies to use
when a player asks to build a new project. The stack is injected into
LLM prompts as context — players can override any choice.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StackLayer:
    """A single technology choice within a project stack."""

    category: str
    name: str
    version: str
    notes: str = ""


@dataclass(frozen=True)
class ProjectStack:
    """Complete tech stack for a project type."""

    name: str
    layers: tuple[StackLayer, ...]

    def to_prompt_context(self) -> str:
        """Format as a text block for LLM system prompts."""
        lines = [f"## {self.name} — Default Stack"]
        for layer in self.layers:
            line = f"- **{layer.category}**: {layer.name} {layer.version}"
            if layer.notes:
                line += f" — {layer.notes}"
            lines.append(line)
        return "\n".join(lines)


DEFAULT_BACKEND = ProjectStack(
    name="Python Backend",
    layers=(
        StackLayer("framework", "FastAPI", "0.115+", "app factory pattern"),
        StackLayer("orm", "SQLAlchemy", "2.0+", "mapped_column declarative style"),
        StackLayer("migrations", "Alembic", "1.15+", "async env, auto-generate from models"),
        StackLayer("database", "PostgreSQL", "16+"),
        StackLayer("validation", "Pydantic", "2.10+", "BaseSettings for config"),
        StackLayer("testing", "pytest", "8.0+", "xdist, parametrize, hypothesis, asyncio"),
        StackLayer("linting", "ruff", "0.9+", "format + check + isort"),
        StackLayer("type checking", "ty", "0.0.25+", "strict on src/, 10x faster than mypy"),
        StackLayer("packaging", "uv", "0.10+", "pyproject.toml + uv.lock"),
        StackLayer("containerization", "Docker", "", "multi-stage with uv"),
    ),
)

DEFAULT_FRONTEND = ProjectStack(
    name="React Frontend",
    layers=(
        StackLayer("framework", "React", "19+", "named exports, no default exports"),
        StackLayer("bundler", "Vite", "7+"),
        StackLayer("language", "TypeScript", "5.7+", "strict mode"),
        StackLayer("data fetching", "TanStack Query", "5+", "array keys, isPending"),
        StackLayer("styling", "Tailwind CSS", "4+"),
        StackLayer("containerization", "Docker", "", "multi-stage nginx"),
    ),
)

SCAFFOLD_KEYWORDS = frozenset(
    {
        "build",
        "create",
        "scaffold",
        "new project",
        "new app",
        "start a",
        "set up",
        "setup",
        "initialize",
        "init",
        "bootstrap",
        "generate project",
        "make me a",
        "build me a",
    }
)


def looks_like_scaffolding(user_input: str) -> bool:
    """Heuristic: does the user input look like a new project request?"""
    lower = user_input.lower()
    return any(kw in lower for kw in SCAFFOLD_KEYWORDS)


def get_stack_context(
    backend: ProjectStack = DEFAULT_BACKEND,
    frontend: ProjectStack = DEFAULT_FRONTEND,
) -> str:
    """Return formatted stack context for injection into agent prompts.

    Args:
        backend: Backend stack definition (defaults to FastAPI + SQLAlchemy).
        frontend: Frontend stack definition (defaults to React + Vite).

    Returns:
        Markdown-formatted text block describing both stacks.
    """
    return (
        "# Default Tech Stack\n"
        "Use these technologies unless the player specifies otherwise.\n"
        "Reference templates in templates/backend/ and templates/frontend/ "
        "for file patterns.\n\n"
        f"{backend.to_prompt_context()}\n\n"
        f"{frontend.to_prompt_context()}"
    )
