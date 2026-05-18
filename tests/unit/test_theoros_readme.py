from pathlib import Path

KOURAI_README = Path(__file__).resolve().parents[2] / "README.md"


def test_kourai_readme_documents_theoros():
    text = KOURAI_README.read_text()
    assert "theoros" in text.lower(), "theoros not mentioned in kourai README"
    assert "make theoros" in text, "kourai README should mention `make theoros`"
    assert "tmux attach -t kourai-theoros -r" in text, (
        "kourai README should show the spectator attach command"
    )
