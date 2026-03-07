# Python Style Guide

Standards for all Python code in Kourai Khryseai. Enforced by [ruff](https://docs.astral.sh/ruff/) and Kallos.

## Quick Reference

| | |
|---|---|
| **Python** | 3.12+ |
| **Line length** | 100 characters |
| **Type hints** | Modern syntax (`X | None`, lowercase generics) |
| **Docstrings** | Google style |
| **Comments** | WHY not WHAT |
| **Linter** | ruff (check + format) |

```bash
make lint    # Run ruff check + format
make test    # Run pytest
```

---

## Type Hints

Use modern 3.12+ syntax everywhere:

```python
# ✅ Modern
def process(items: list[dict[str, Any]], name: str | None = None) -> dict[str, int]:
    ...

# ❌ Legacy — don't use
from typing import Optional, List
def process(items: List[Dict[str, Any]], name: Optional[str] = None) -> Dict[str, int]:
    ...
```

| Pattern | Use? |
|---------|------|
| `list[str]`, `dict[str, int]` | ✅ Always |
| `str \| None` | ✅ Preferred |
| `Optional[str]`, `Union[int, str]` | ❌ Legacy |

---

## Docstrings

### Public functions — one-liner + Args + Returns

```python
def generate_commit_messages(git_output: str) -> str:
    """Generate commit message groups from git status/diff output.

    Args:
        git_output: Combined output of git status + git diff.

    Returns:
        Formatted commit message groups.
    """
```

### Private helpers — one-liner only

```python
def _calculate_backoff(attempt: int) -> float:
    """Compute exponential backoff delay."""
```

### Inner functions — no docstring

```python
def process():
    def _validate(item):  # No docstring needed
        return item.is_valid
```

---

## Comments

### Remove WHAT comments

```python
# ❌ Restates the code — remove it
# Create the agent
agent = TechneAgent()

# ❌ Restates the value — remove it
DEFAULT_TIMEOUT = 30  # 30 seconds
```

### Keep WHY comments

```python
# ✅ Explains rationale
# Cache to avoid recomputation on every request
_cached_models: dict[str, str] = {}

# ✅ Constraints
# Max 5 iterations to prevent infinite Kallos ↔ Techne loops
MAX_ITERATIONS = int(os.getenv("KOURAI_MAX_ITERATIONS", "5"))
```

### Research citations

When implementing algorithms or using non-obvious thresholds, add a citation:

```python
# Research: Krum requires n > 2f + 2 (Blanchard et al., NeurIPS 2017)
# https://proceedings.neurips.cc/paper/2017/file/f4b9ec30ad9f68f89b29639786cb62ef-Paper.pdf
if num_clients <= 2 * num_malicious + 2:
    raise ValueError("Not enough clients for Krum aggregation")
```

**Format:**

```python
# Research: [Algorithm/concept] [key constraint] (Author et al., Venue Year)
# [URL to paper]
```

---

## Imports

Ordered by ruff — stdlib, third-party, local:

```python
# 1. Standard library
import logging
from collections.abc import AsyncIterable

# 2. Third-party
from a2a.server.agent_execution import AgentExecutor, RequestContext
from litellm import acompletion

# 3. Local
from kourai_common.config import get_model
from kourai_common.tracing import create_span
```

---

## Logging

Use `logging`, never `print`:

```python
import logging

log = logging.getLogger(__name__)

log.info("Starting agent on port %d", port)
log.error("Pipeline failed: %s", error)
```

---

## Error Handling

Specific exceptions only. Never bare `except:`.

```python
# ✅ Specific
try:
    response = await client.send_message(request)
except httpx.ConnectError as e:
    log.error("Agent unreachable: %s", e)
    raise
except httpx.TimeoutException:
    log.warning("Agent timed out, retrying...")

# ❌ Never
try:
    ...
except:
    pass
```

---

## Testing

```python
# File: tests/unit/test_mneme.py

class TestMnemeAgent:
    """Tests for commit message generation."""

    def test_generate_with_valid_diff(self):
        """Valid git diff produces formatted commit groups."""
        ...

    def test_rejects_empty_input(self):
        """Empty diff returns INPUT_REQUIRED state."""
        ...
```

**Priority:** unit → integration → performance. Target 80%+ coverage.

---

## Cleanup Checklist

- [x] Remove WHAT comments
- [x] Keep WHY comments (rationale, research refs)
- [x] Add Research citations where missing
- [x] Modern type hints (`X | None` syntax)
- [x] No marketing language ("robust", "comprehensive")
- [x] `logging` over `print`
- [x] Specific exceptions only

---

**References:** [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) · [Shell Guide](shell-style-guide.md) · [Frontend Guide](frontend-style-guide.md)
