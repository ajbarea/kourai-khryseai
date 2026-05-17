from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "theoros.md"
ZENSICAL_TOML = REPO_ROOT / "zensical.toml"


def test_theoros_docs_page_exists():
    assert DOCS.is_file(), "docs/theoros.md missing"


def test_theoros_docs_covers_required_sections():
    text = DOCS.read_text()
    for heading in (
        "# Theoros",
        "## Role split",
        "## Starting a session",
        "## Aesthetic vs operational",
        "## Troubleshooting",
    ):
        assert heading in text, f"docs/theoros.md missing section: {heading}"


def test_zensical_toml_includes_theoros():
    text = ZENSICAL_TOML.read_text()
    assert "theoros.md" in text, "zensical.toml does not register theoros.md in nav"
