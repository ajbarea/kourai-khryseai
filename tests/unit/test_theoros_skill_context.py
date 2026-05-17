"""Validate the `## theoros` section of .claude/skill-context.md."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_CTX = REPO_ROOT / ".claude" / "skill-context.md"


def _extract_theoros_yaml() -> str:
    """Return the YAML block content from the `## theoros` section, or empty string."""
    text = SKILL_CTX.read_text()
    section_match = re.search(
        r"^## theoros\s*\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        return ""
    section = section_match.group(1)
    yaml_match = re.search(r"```yaml\s*\n(.*?)\n```", section, flags=re.DOTALL)
    return yaml_match.group(1) if yaml_match else ""


def test_theoros_section_exists():
    assert SKILL_CTX.is_file(), f"{SKILL_CTX} not found"
    text = SKILL_CTX.read_text()
    assert re.search(r"^## theoros\s*$", text, flags=re.MULTILINE), (
        "`## theoros` section missing from skill-context.md"
    )


def test_theoros_yaml_block_has_required_fields():
    yaml = _extract_theoros_yaml()
    assert yaml, "no fenced ```yaml block inside `## theoros`"
    assert re.search(r"^repl_command:\s*\S", yaml, flags=re.MULTILINE), (
        "`repl_command` field missing"
    )
    assert re.search(r"^session_name:\s*\S", yaml, flags=re.MULTILINE), (
        "`session_name` field missing"
    )
    assert re.search(r"^ops_command:\s*\S", yaml, flags=re.MULTILINE), (
        "`ops_command` field missing"
    )
    assert re.search(r"^prerequisites:\s*$", yaml, flags=re.MULTILINE), (
        "`prerequisites` field missing"
    )


def test_theoros_aesthetic_operational_table_present():
    """The prose table outside the YAML block is the discipline anchor."""
    text = SKILL_CTX.read_text()
    section_match = re.search(
        r"^## theoros\s*\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert section_match
    section = section_match.group(1)
    assert "Aesthetic vs operational" in section, (
        "aesthetic vs operational table heading missing from `## theoros` section"
    )
