# Python Style Guide

This guide documents the established patterns for Python code in the IntelliFL project. All Python code should follow these conventions to maintain consistency across the codebase.

## Quick Reference

- Python version: 3.10-3.13
- Line length: 100 characters max
- Type hints: Modern syntax (`X | None`, lowercase generics)
- Docstrings: Google style
- Comments: WHY not WHAT

## Tools and Configuration

The project uses these tools for code quality:

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| ruff | Linting + formatting | `pyproject.toml` |
| isort | Import sorting | `pyproject.toml` |
| mypy | Type checking | `pyproject.toml` |
| pyright | Type checking (optional) | `pyrightconfig.json` |

Run all checks with:
```bash
./tests/lint.sh           # Linting only
./tests/lint.sh --test    # Linting + tests
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

# ⚠️ Legacy (still works, but prefer | syntax)
from typing import Optional, Union
def process(items: list[dict[str, Any]], name: Optional[str] = None) -> dict[str, int]:
    ...

# ❌ Old style (deprecated)
from typing import List, Dict
def process(items: List[Dict[str, Any]]) -> Dict[str, int]:
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
| `List[str]`, `Dict[str, int]` | ✅ | ❌ Deprecated |

### When to Use `from __future__ import annotations`

```python
from __future__ import annotations  # Only if using forward refs or complex types
```

Use when:
- Forward references to classes defined later in the file
- Complex recursive type definitions
- Avoiding import cycles for type hints

## Docstrings (Google Style)

### Public Functions

One-liner + Args (+ Returns if non-None):

```python
def save_attack_timeline_gif(
    attack_timeline: dict[str, dict[str, list[str]]],
    filepath: Path,
    total_rounds: int,
) -> None:
    """Create animated GIF showing attack timeline progression.

    Args:
        attack_timeline: Nested dict mapping client_id -> round -> [attack_types].
            Example: {"0": {"2": ["label_flipping"]}}
        filepath: Output path for the GIF file.
        total_rounds: Total number of federated learning rounds.
    """
```

### Private/Helper Functions

One-liner only (or skip if obvious):

```python
def _calculate_weights(updates):
    """Compute normalized weights for client updates."""
```

### Inner Functions

No docstring needed:

```python
def init():
    line.set_data([], [])
    return line,
```

### Complex Data Structures

Include Example for complex types:

```python
def process_attack_schedule(
    schedule: list[AttackScheduleEntry],
) -> dict[int, list[str]]:
    """Process attack schedule into round-indexed lookup.

    Args:
        schedule: List of attack schedule entries.
            Example: [{"start_round": 1, "end_round": 5, "attack_type": "label_flipping"}]

    Returns:
        Dict mapping round number to list of active attack types.
    """
```

## Comment Quality

### Remove WHAT Comments

Comments that restate what the code does provide no value:

```python
# ❌ BAD: Restates the code
# Initialize the model
model = Model()

# ❌ BAD: Obvious from code
# Create mock client
client = create_mock_flower_client(1)

# ❌ BAD: Loop description
# Loop through clients
for client in clients:

# ❌ BAD: Obvious from hex value
attack_colors = {
    "label_flipping": "#e74c3c",  # Red
}

# ❌ BAD: Name already says it
DEFAULT_TIMEOUT = 30  # 30 seconds
```

### Keep WHY Comments but make CONCISE

Comments that explain rationale, context, or design decisions are valuable:

```python
# ✅ GOOD: Research context
# Krum paper recommends n-f-2 for Byzantine tolerance
selections = n - f - 2

# ✅ GOOD: Design rationale
# Use FedProx for non-IID data to improve convergence
strategy = FedProx(mu=0.1)

# ✅ GOOD: Security context
# Filter sensitive env vars before passing to subprocess
env = get_safe_env()

# ✅ GOOD: Performance rationale
# Cache results to avoid expensive recomputation
@lru_cache(maxsize=128)
def compute_metrics(params: Parameters) -> dict[str, float]:

# ✅ GOOD: Design tradeoff
DEFAULT_FPS = 2  # Slow enough to read, fast enough to engage
```

## Research Citations

### When to Add

Add `# Research:` comments when code implements algorithms from academic literature:

- Byzantine fault tolerance constraints (Krum, Bulyan, Trimmed Mean)
- Aggregation algorithm implementations (FedAvg, FedProx, SCAFFOLD)
- Attack implementations (label flipping, gradient inversion, model poisoning)
- Defense mechanisms (differential privacy, secure aggregation)
- Convergence bounds or theoretical guarantees
- Any algorithm with a canonical paper reference

### Format

```python
# Research: [Algorithm/concept] [key constraint] (Author et al., Venue Year)
# [URL to paper]
```

### Examples

```python
# Research: Krum requires n > 2f + 2 (Blanchard et al., NeurIPS 2017)
# https://proceedings.neurips.cc/paper_files/paper/2017/file/f4b9ec30ad9f68f89b29639786cb62ef-Paper.pdf
if num_of_malicious_clients > max_malicious_for_krum:
    raise ValueError(...)

# Research: Bulyan requires n ≥ 4f + 3 (El Mhamdi et al., MLSys 2019)
# https://mlsys.org/Conferences/2019/doc/2019/54.pdf
max_byzantine = (num_clients - 3) // 4
```

### Finding the Canonical Citation

Before adding a Research note:

1. Search: `"[algorithm name]" original paper` or `"[algorithm name]" [author if known]`
2. Prefer the original paper that introduced the algorithm (not surveys or follow-ups)
3. Prefer peer-reviewed venues (NeurIPS, ICML, ICLR, MLSys, IEEE S&P) over arXiv preprints
4. If arXiv only, check if a published version exists at a conference/journal
5. Verify the constraint/formula matches what the paper actually states

```python
# ❌ Don't assume: "Krum needs n > 2f" (might be misremembered)
# ✅ Do search: "Krum" "Byzantine" original paper NeurIPS
# ✅ Verify in paper: Theorem 2 states n > 2f + 2
```

## Imports

### Order (enforced by isort)

```python
# 1. Standard library
import json
import logging
from pathlib import Path

# 2. Third-party packages
import torch
from pydantic import BaseModel

# 3. Local imports
from src.config_loaders.config_loader import ConfigLoader
from src.data_models.simulation_strategy_config import StrategyConfig
```

### Style

```python
# ✅ Preferred: Explicit imports
from pathlib import Path
from typing import Any

# ⚠️ Acceptable for large modules
import numpy as np
import torch

# ❌ Avoid: Star imports
from typing import *
```

## Classes

### Pydantic Models

Use Pydantic for configuration and data validation:

```python
from pydantic import BaseModel, ConfigDict, field_validator

class StrategyConfig(BaseModel):
    """Configuration for a single simulation strategy."""

    model_config = ConfigDict(extra="allow")

    aggregation_strategy_keyword: str | None = None
    num_of_rounds: int | None = None
    num_of_clients: int | None = None

    @field_validator("num_of_rounds", mode="before")
    @classmethod
    def validate_rounds(cls, v: Any) -> int | None:
        """Ensure rounds is positive."""
        if v is not None and v <= 0:
            raise ValueError("num_of_rounds must be positive")
        return v

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> StrategyConfig:
        """Create config instance from dict using Pydantic validation."""
        return cls.model_validate(config)
```

### TypedDict for Internal Types

Use TypedDict for internal configuration dictionaries without validation overhead:

```python
from typing import TypedDict, NotRequired

class AttackScheduleEntry(TypedDict):
    """Type definition for attack schedule entries."""

    start_round: int
    end_round: int
    attack_type: str
    selection_strategy: str

    # Optional fields
    malicious_percentage: NotRequired[float]
    malicious_client_ids: NotRequired[list[int]]
```

## Error Handling

### Specific Exceptions

```python
# ✅ Specific exception
except FileNotFoundError:
    log.error(f"Config file not found: {path}")
    raise

# ✅ Multiple specific exceptions
except (ValueError, TypeError) as e:
    log.error(f"Invalid configuration: {e}")
    raise

# ❌ Bare except (never use)
except:
    pass

# ⚠️ Acceptable only when re-raising or logging
except Exception as e:
    log.error(f"Unexpected error: {e}")
    raise
```

### Custom Exceptions

```python
class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass

class SimulationError(Exception):
    """Raised when simulation execution fails."""
    pass
```

## Logging

### Use logging, Not print

```python
import logging

log = logging.getLogger(__name__)

# ✅ Use logging
log.info("Starting simulation...")
log.debug(f"Config: {config}")
log.warning("Dataset not found, using default")
log.error(f"Simulation failed: {e}")

# ❌ Avoid print in library code
print("Starting simulation...")
```

### Log Levels

| Level | Use For |
|-------|---------|
| DEBUG | Detailed diagnostic info |
| INFO | Progress updates, milestones |
| WARNING | Recoverable issues |
| ERROR | Failures that stop execution |

## Testing

### Test File Location

```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Tests with external dependencies
├── performance/    # Timing and resource tests
└── fixtures/       # Shared test data
```

### Test Naming

```python
# File: tests/unit/test_strategy_config.py

class TestStrategyConfig:
    """Tests for StrategyConfig validation."""

    def test_from_dict_with_valid_config(self):
        """Valid config dict creates StrategyConfig instance."""
        ...

    def test_from_dict_with_invalid_rounds_raises_error(self):
        """Negative rounds value raises ValueError."""
        ...

    def test_coerce_bool_strings_converts_true(self):
        """String 'true' is coerced to boolean True."""
        ...
```

### Fixtures

```python
import pytest

@pytest.fixture
def sample_strategy_config() -> dict[str, Any]:
    """Minimal valid strategy configuration."""
    return {
        "aggregation_strategy_keyword": "fedavg",
        "num_of_rounds": 10,
        "num_of_clients": 5,
    }
```

## Code Organization

### Module Structure

```
src/
├── api/                    # FastAPI endpoints
├── attack_utils/           # Attack implementations
├── client_models/          # FL client implementations
├── config_loaders/         # Configuration parsing
├── data_models/            # Pydantic models
├── dataset_handlers/       # Dataset management
├── dataset_loaders/        # Dataset loading
├── network_models/         # Neural network architectures
├── output_handlers/        # Plotting and file output
├── simulation_strategies/  # Aggregation strategies
└── utils/                  # Shared utilities
```

### File Organization

```python
"""Module docstring explaining purpose."""

from __future__ import annotations

# Standard library imports
import json
import logging
from pathlib import Path

# Third-party imports
import torch
from pydantic import BaseModel

# Local imports
from src.config_loaders import ConfigLoader

# Module-level constants
DEFAULT_ROUNDS = 10
DEFAULT_CLIENTS = 5

# Module-level logger
log = logging.getLogger(__name__)


# Classes
class MyClass:
    ...


# Public functions
def public_function():
    ...


# Private functions
def _private_helper():
    ...


# Main block (if applicable)
if __name__ == "__main__":
    ...
```

## Cleanup Checklist

When reviewing or writing Python code:

1. ✅ Remove WHAT comments (restating code)
2. ✅ Keep WHY comments (rationale, research refs, security)
3. ✅ Verify existing Research citations (web search to confirm accuracy)
4. ✅ Add Research citations where missing (algorithms, constraints, thresholds)
5. ✅ One-liner + Args for public functions
6. ✅ One-liner only for private helpers
7. ✅ No docstrings on inner functions
8. ✅ Modern type hints (`X | None` syntax, lowercase generics)
9. ✅ No marketing language ("robust", "comprehensive")
10. ✅ Include Example for complex data structures

## Cross-Reference

This style guide aligns with:

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [PEP 8](https://peps.python.org/pep-0008/) - Style Guide for Python Code
- [PEP 257](https://peps.python.org/pep-0257/) - Docstring Conventions
- [PEP 585](https://peps.python.org/pep-0585/) - Lowercase generics (3.9+)
- [PEP 604](https://peps.python.org/pep-0604/) - Union `|` syntax (3.10+)
- Project ruff configuration (100-char line limit)
- [Shell Style Guide](SHELL_STYLE_GUIDE.md) - Companion guide for shell scripts

---

*Last Updated: 2026-01-11*
