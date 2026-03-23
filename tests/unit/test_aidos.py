"""Tests for Aidos anti-slop detection — slop words and vacuous docstrings.

Phase 15: Unit tests for pre-screen layer (pure functions, no LLM calls).
"""

from __future__ import annotations

from agents.aidos.agent import (
    SLOP_PATTERN,
    _name_to_words,
    flag_slop_words,
    flag_vacuous_docstrings,
)

# ── SLOP_PATTERN / flag_slop_words ─────────────────────────────────────────


def test_flag_slop_words_detects_single():
    assert flag_slop_words("This is a robust system.") == ["robust"]


def test_flag_slop_words_detects_multiple():
    found = flag_slop_words("A comprehensive and seamless solution for leverage.")
    assert "comprehensive" in found
    assert "seamless" in found
    assert "solution" in found
    assert "leverage" in found


def test_flag_slop_words_case_insensitive():
    assert flag_slop_words("ROBUST and Comprehensive") == ["robust", "comprehensive"]


def test_flag_slop_words_empty_on_clean_text():
    assert flag_slop_words("This function parses JSON and returns a dict.") == []


def test_flag_slop_words_empty_string():
    assert flag_slop_words("") == []


def test_flag_slop_words_multi_word_phrases():
    found = flag_slop_words("Let's circle back and take a deep dive into the low-hanging fruit.")
    assert "circle back" in found
    assert "deep dive" in found
    assert "low-hanging fruit" in found


def test_slop_pattern_word_boundary():
    """'platform' should match but 'platforms' substring 'platform' should too."""
    assert SLOP_PATTERN.search("The platform is ready.")
    # 'robustness' should NOT match — 'robust' has word boundary
    assert not SLOP_PATTERN.search("Testing robustness of the system.")


# ── _name_to_words ─────────────────────────────────────────────────────────


def test_name_to_words_snake_case():
    words = _name_to_words("get_user")
    assert "get" in words
    assert "user" in words


def test_name_to_words_camel_case():
    words = _name_to_words("getUserProfile")
    assert "get" in words
    assert "user" in words
    assert "profile" in words


def test_name_to_words_single_word():
    assert _name_to_words("process") == {"process"}


def test_name_to_words_mixed_case_with_underscores():
    words = _name_to_words("parse_XMLDocument")
    assert "parse" in words
    # CamelCase split handles transitions from lower→upper, not consecutive uppercase
    assert "xmldocument" in words or "document" in words


# ── flag_vacuous_docstrings ────────────────────────────────────────────────


def test_vacuous_detects_restated_name():
    code = '''
def get_user():
    """Get user."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 1
    assert results[0]["name"] == "get_user"


def test_vacuous_detects_with_filler_words():
    code = '''
def process_data():
    """Process the data."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 1
    assert results[0]["name"] == "process_data"


def test_vacuous_detects_class_docstring():
    code = '''
class UserManager:
    """User manager."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 1
    assert results[0]["name"] == "UserManager"


def test_vacuous_passes_specific_docstring():
    code = '''
def calculate_total(items):
    """Sum all item prices after applying discounts and tax."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 0


def test_vacuous_passes_detailed_docstring():
    code = '''
def get_user(user_id):
    """Fetch user from the database by primary key, raising NotFoundError if missing."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 0


def test_vacuous_multiple_functions():
    code = '''
def get_user():
    """Get user."""
    pass

def calculate_total(items):
    """Sum prices after discounts."""
    pass

def process_data():
    """Process the data."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"get_user", "process_data"}


def test_vacuous_empty_input():
    assert flag_vacuous_docstrings("") == []


def test_vacuous_no_docstrings():
    code = """
def get_user():
    pass
"""
    assert flag_vacuous_docstrings(code) == []


def test_vacuous_camel_case_class():
    code = '''
class DataProcessor:
    """Data processor."""
    pass
'''
    results = flag_vacuous_docstrings(code)
    assert len(results) == 1
    assert results[0]["name"] == "DataProcessor"
