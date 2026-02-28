# Python Style Guide

This guide documents the established patterns for Python code in the **Kourai Khryseai** project. All Python code should follow these conventions to maintain consistency across the multi-agent system.

## Quick Reference

- **Python version:** 3.10-3.13
- **Line length:** 100 characters max
- **Type hints:** Modern syntax (`X | None`, lowercase generics)
- **Docstrings:** Google style
- **Comments:** WHY not WHAT

## Tools and Configuration

The project uses these tools for code quality:

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| ruff | Linting + formatting | `pyproject.toml` |
| isort | Import sorting | `pyproject.toml` |
| mypy | Type checking | `pyproject.toml` |

Run all checks with:
```bash
make lint           # Linting only
make test           # Linting + tests
```

## Type Hints

### Modern Syntax (Python 3.10+)

Use modern type hint syntax throughout the codebase:

```python
# ✅ Correct (modern 3.10+ style)
def process(items: list[dict[str, Any]], name: str | None = None) -> dict[str, int]:
    ...

def get_value(key: str) -> int | str:
    ...
```

### Pattern Reference

| Pattern | Status | Use? |
|---------|--------|------|
| `list[str]`, `dict[str, int]` | ✅ | ✅ |
| `str \| None` | ✅ | ✅ Preferred |
| `int \| str` | ✅ | ✅ Preferred |
| `Optional[str]` | ✅ | ⚠️ Legacy |
| `Union[int, str]` | ✅ | ⚠️ Legacy |

## Docstrings (Google Style)

### Public Functions

One-liner + Args (+ Returns if non-None):

```python
def generate_agent_response(
    query: str,
    context_id: str,
    max_tokens: int = 1000,
) -> str:
    """Generate a response from the specialized agent.

    Args:
        query: The user query to process.
        context_id: Unique session identifier for tracing.
        max_tokens: Maximum tokens for the LLM output.

    Returns:
        The generated text response.
    """
```

### Private/Helper Functions

One-liner only (or skip if obvious):

```python
def _calculate_backoff(attempt: int) -> float:
    """Compute exponential backoff delay."""
```

## Comment Quality

### Remove WHAT Comments

Comments that restate what the code does provide no value:

```python
# ❌ BAD: Restates the code
# Initialize the agent
agent = TechneAgent()
```

### Keep WHY Comments

Comments that explain rationale, context, or design decisions are valuable:

```python
# ✅ GOOD: Research context
# Research: Krum requires n > 2f + 2 (Blanchard et al., NeurIPS 2017)
# https://proceedings.neurips.cc/paper_files/paper/2017/file/f4b9ec30ad9f68f89b29639786cb62ef-Paper.pdf
if num_of_malicious_clients > max_malicious_for_krum:
    raise ValueError(...)
```

## Research Citations

### Format

```python
# Research: [Algorithm/concept] [key constraint] (Author et al., Venue Year)
# [URL to paper]
```

## Imports

### Order (enforced by isort)

```python
# 1. Standard library
import json
import logging
from pathlib import Path

# 2. Third-party packages
from litellm import completion
from pydantic import BaseModel

# 3. Local imports
from kourai_common.config import AGENT_MODELS
```

## Classes

### Pydantic Models

Use Pydantic for configuration and data validation:

```python
from pydantic import BaseModel, ConfigDict

class AgentConfig(BaseModel):
    """Configuration for a specialized agent."""
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    port: int
```

## Logging

### Use logging, Not print

```python
import logging

log = logging.getLogger(__name__)

# ✅ Use logging
log.info("Starting agent process...")
```

## Testing

### Test Naming

```python
# File: tests/unit/test_mneme.py

class TestMnemeAgent:
    """Tests for commit message generation."""

    def test_generate_commit_with_valid_diff(self):
        """Valid git diff produces formatted commit groups."""
        ...
```

## Cleanup Checklist

1. ✅ Remove WHAT comments
2. ✅ Keep WHY comments (rationale, research refs)
3. ✅ Add Research citations where missing
4. ✅ Modern type hints (`X | None` syntax)
5. ✅ No marketing language ("robust", "comprehensive")

## Cross-Reference

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Shell Style Guide](shell-style-guide.md)
- [Frontend Style Guide](frontend-style-guide.md)

---

*Last Updated: 2026-02-28*
