"""
This module defines the system prompt templates for Kourai agents, including
identity, personality, instructions, and standards. The build_system_prompt()
function constructs a complete prompt with layered architecture for any agent role.
"""

from __future__ import annotations

import datetime

CURRENT_DATE = datetime.date.today().strftime("%B %Y")

PYTHON_STANDARDS = f"""
Python Standards ({CURRENT_DATE} Best Practices):
- Python 3.12+ features (match statements, contextlib.suppress, modern typing)
- Modern type hints: X | None (not Optional[X]), lowercase generics (list, dict)
- Dependency Management: ALWAYS use `uv` (no pip/venv), understand `uv.lock` and workspaces
- Google-style docstrings: public = one-liner + Args/Returns, private = one-liner, inner = none
- Comments: WHY not WHAT. Add Research: citations for algorithms with paper URLs
- Specific exceptions only, never bare except. Raise from None when appropriate
- logging over print, use log = logging.getLogger(__name__)
- Tools: ONLY use `ruff` for formatting and linting (no `isort`), `ty` for typing
"""

GIT_BOUNDARIES = """
GIT BOUNDARIES: FORBIDDEN — git commit, git push, git tag
NEVER run git commit, git push, or git tag. Your role is code generation, not version control.
"""

UNIVERSAL_RULES = """
=== UNIVERSAL RULES (AJ's Preferences) ===
1. MINIMAL CHANGES: Keep modifications small and focused
2. EDIT OVER CREATE: Prefer editing existing files over creating new ones
3. REMOVE OVER ADD: Delete unnecessary code when possible
4. NO FLUFF: Technical language only, no marketing speak
5. EMOJIS: Use emojis in markdown output
6. PYTHON: 100 char lines, modern type hints, Google docstrings
7. COMMENTS: WHY not WHAT, Research citations for algorithms
8. FACT EXTRACTION: If you learn something new about the player (e.g., preference, identity, skill, context, goal, personality), embed it anywhere in your response using this tag format: <FACT category="preference" confidence="high">Player prefers X</FACT>. The tag will be parsed and hidden from the player.
9. SPEECH VS ACTION: When you address the player directly — greeting, question, handoff line, commentary, explanation — wrap that line in double quotes ("like this"). When you describe what you're doing — analyzing, running tests, listing findings, streaming file ops — leave it unquoted. The host renders quoted lines as dialogue (italic) and unquoted lines as plain status, so this single rule controls how the player perceives you on screen.
"""


def build_system_prompt(
    agent_name: str,
    role: str,
    personality: str,
    specific_instructions: str,
    include_python_standards: bool = True,
    player_context: str | None = None,
    personality_baseline: str | None = None,
) -> str:
    """Build a complete agent system prompt with layered architecture.

    Layers (in order):
    1. Identity: "You are {name}, the {role}..."
    2. Personality: core function description (personality param)
    3. Personality baseline: tier-adaptive foundation (optional, new layer)
    4. Instructions: task-specific checklists and output formats
    5. Standards: Python standards, git boundaries, universal rules
    6. Player context: injected at runtime (not at build time)

    Args:
        agent_name: Name of the agent (e.g., "Techne", "Kallos")
        role: Role description (e.g., "coding specialist")
        personality: Core identity/function description
        specific_instructions: Agent-specific instructions and output formats
        include_python_standards: Whether to include Python standards section
        player_context: Optional player identity/memory block from build_player_context()
        personality_baseline: Optional tier-adaptive personality foundation.
            Separates the immutable identity (personality) from the evolving
            relationship behavior. If provided, warmth/sass/formality can shift
            via tier adaptations without contradicting the base identity.
    """
    sections = [
        f"You are {agent_name}, the {role} of Kourai Khryseai.",
        personality,
    ]

    if personality_baseline:
        sections.append(personality_baseline)

    sections.extend(["", specific_instructions])

    if include_python_standards:
        sections.append(PYTHON_STANDARDS)

    sections.extend([GIT_BOUNDARIES, UNIVERSAL_RULES])

    if player_context:
        sections.append(player_context)

    return "\n".join(sections)
