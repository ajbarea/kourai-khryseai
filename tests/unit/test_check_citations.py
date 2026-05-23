"""Tests for scripts/check_citations.py — mechanical CI gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.check_citations import check_project, find_citation_links

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_find_citation_links_in_python(tmp_path: Path):
    src = _write(
        tmp_path / "foo.py",
        """
# research(2026-05): Baruch et al. ALIE perturbation
# see docs/citations/1902.06156-baruch-alie.md
def alie():
    pass
""".strip(),
    )
    links = list(find_citation_links([src]))
    assert ("1902.06156-baruch-alie.md", src) in [(p, s) for p, s in links]


def test_find_citation_links_in_markdown(tmp_path: Path):
    src = _write(
        tmp_path / "README.md",
        """
ALIE [Baruch et al. 2019][^alie] perturbs honest updates.

[^alie]: See [docs/citations/1902.06156-baruch-alie.md] for the verified source.
""".strip(),
    )
    links = list(find_citation_links([src]))
    assert ("1902.06156-baruch-alie.md", src) in [(p, s) for p, s in links]


def test_md_fenced_code_block_citations_are_ignored(tmp_path: Path):
    """Illustrative citation paths inside ```fenced``` blocks are documentation,
    not real references; user-facing docs (e.g. docs/agents/aletheia.md) carry
    examples that would otherwise trigger spurious missing-artifact errors.
    """
    src = _write(
        tmp_path / "docs.md",
        """
# Using citations

Real claim: see [docs/citations/real-paper.md] for the verified source.

Here's how to add one in code:

```python
# see docs/citations/example-paper.md
def foo():
    pass
```

And in markdown:

```markdown
[^x]: See [docs/citations/another-example.md] for details.
```
""".strip(),
    )
    found = sorted({p for p, _ in find_citation_links([src])})
    assert "real-paper.md" in found
    assert "example-paper.md" not in found
    assert "another-example.md" not in found


def test_md_python_files_still_match_inside_comments(tmp_path: Path):
    """Python files have no fence-stripping; citation comments in real code
    must keep matching even if their syntax superficially resembles a fence
    boundary (this guards against accidental over-stripping)."""
    src = _write(
        tmp_path / "real.py",
        """
\"\"\"Module docstring with backticks like `foo` inline.\"\"\"

# research(2026-05): see docs/citations/real-comment.md
def cited():
    pass
""".strip(),
    )
    found = sorted({p for p, _ in find_citation_links([src])})
    assert "real-comment.md" in found


def test_check_project_passes_when_artifact_exists(tmp_path: Path):
    _write(tmp_path / "src/foo.py", "# see docs/citations/1902.06156-baruch-alie.md\n")
    _write(
        tmp_path / "docs/citations/1902.06156-baruch-alie.md",
        """---
title: ALIE
authors: [Baruch et al.]
year: 2019
urls:
  abs: https://arxiv.org/abs/1902.06156
verified_at: "2026-01-01T00:00:00+00:00"
verified_by: aletheia
claim_supported: true
---
""",
    )
    rc, errors = check_project(tmp_path)
    assert rc == 0
    assert errors == []


def test_check_project_fails_when_artifact_missing(tmp_path: Path):
    _write(tmp_path / "src/foo.py", "# see docs/citations/missing-paper.md\n")
    rc, errors = check_project(tmp_path)
    assert rc == 1
    assert len(errors) == 1
    assert "missing-paper.md" in errors[0]


def test_check_project_validates_artifact_frontmatter_yaml(tmp_path: Path):
    _write(tmp_path / "src/foo.py", "# see docs/citations/bad.md\n")
    _write(tmp_path / "docs/citations/bad.md", "not yaml at all")
    rc, errors = check_project(tmp_path)
    assert rc == 1
    assert any("frontmatter" in e.lower() or "yaml" in e.lower() for e in errors)


def test_check_project_flags_stale_verified_at(tmp_path: Path):
    """Artifact with verified_at older than 365 days should be flagged."""
    _write(tmp_path / "src/foo.py", "# see docs/citations/stale.md\n")
    _write(
        tmp_path / "docs/citations/stale.md",
        """---
title: Stale Paper
authors: [Stale Author]
year: 2020
urls:
  abs: https://example.com
arxiv_id: "0000.0001"
doi: null
sources_consulted: [semantic_scholar]
triangulation:
  primary_source: semantic_scholar
  secondary_source: openalex
  decisive_fields_agreed: true
  decisive_fields_checked: []
  notes: []
single_source_verified: false
verified_by: aletheia
verified_at: "2020-01-01T00:00:00+00:00"
verification_version: "1.0"
human_overridden: false
override_reason: null
claim_supported: stale
---
""",
    )
    rc, errors = check_project(tmp_path)
    assert rc == 1
    assert any("stale" in e.lower() for e in errors)
