"""Tests for Aletheia agent — Brave Search fallback and claim detection.

Verifies Brave Search graceful degradation (missing key, curl failure,
parse errors) and the regex-based find_unsupported_claims pre-screen.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.aletheia.agent import brave_web_search, find_unsupported_claims

# ── brave_web_search — key checks ────────────────────────────────────────────


class TestBraveWebSearchApiKey:
    @pytest.mark.asyncio
    async def test_returns_empty_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch):
        """No BRAVE_API_KEY → returns [] without making any network call."""
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        results = await brave_web_search("O(n log n) sort")
        assert results == []

    @pytest.mark.asyncio
    async def test_does_not_call_curl_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch):
        """subprocess.run must not be called when BRAVE_API_KEY is absent."""
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with patch("subprocess.run") as mock_run:
            await brave_web_search("algorithm complexity")
        mock_run.assert_not_called()


# ── brave_web_search — curl / network paths ───────────────────────────────────


class TestBraveWebSearchCurlPaths:
    @pytest.mark.asyncio
    async def test_returns_empty_when_curl_returns_empty_json(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Curl succeeds but API returns {} (no 'web' key) → []."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        with patch("asyncio.to_thread", new=AsyncMock(return_value="{}")):
            results = await brave_web_search("some query")
        assert results == []

    @pytest.mark.asyncio
    async def test_parses_web_results_correctly(self, monkeypatch: pytest.MonkeyPatch):
        """Parses title, description, and url from API response."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        mock_json = '{"web": [{"title": "QuickSort", "description": "Fast sort", "url": "https://cs.example.com"}]}'
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_json)):
            results = await brave_web_search("quicksort algorithm")

        assert len(results) == 1
        assert results[0]["title"] == "QuickSort"
        assert results[0]["description"] == "Fast sort"
        assert results[0]["url"] == "https://cs.example.com"

    @pytest.mark.asyncio
    async def test_respects_max_results_limit(self, monkeypatch: pytest.MonkeyPatch):
        """Returns at most max_results items from the API response."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        entries = [
            {"title": f"Result {i}", "description": "...", "url": f"https://example.com/{i}"}
            for i in range(10)
        ]
        import json

        mock_json = json.dumps({"web": entries})
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_json)):
            results = await brave_web_search("algorithm", max_results=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self, monkeypatch: pytest.MonkeyPatch):
        """Any unexpected exception in the outer try → returns [] without raising."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        with patch("asyncio.to_thread", new=AsyncMock(side_effect=OSError("net fail"))):
            results = await brave_web_search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_handles_missing_result_fields_gracefully(self, monkeypatch: pytest.MonkeyPatch):
        """Partial API results (missing title/url) produce empty-string defaults."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        import json

        mock_json = json.dumps({"web": [{}]})  # entry has no title, description, url
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_json)):
            results = await brave_web_search("query")

        assert len(results) == 1
        assert results[0]["title"] == ""
        assert results[0]["url"] == ""


# ── find_unsupported_claims ───────────────────────────────────────────────────


class TestFindUnsupportedClaims:
    def test_detects_algorithm_keyword(self):
        """'algorithm' triggers a claim — classic unsupported keyword."""
        text = "The algorithm runs in constant time."
        claims = find_unsupported_claims(text)
        assert len(claims) >= 1
        assert any("algorithm" in c.lower() for c in claims)

    def test_detects_proven_to_keyword(self):
        """'proven to' triggers a claim."""
        text = "It has been proven to converge for convex functions."
        claims = find_unsupported_claims(text)
        assert len(claims) >= 1

    def test_detects_optimal_keyword(self):
        """'optimal' triggers a claim."""
        text = "This is the optimal solution for this class of problem."
        claims = find_unsupported_claims(text)
        assert len(claims) >= 1

    def test_detects_heuristic_keyword(self):
        """'heuristic' triggers a claim."""
        text = "We use a heuristic that performs well in practice."
        claims = find_unsupported_claims(text)
        assert len(claims) >= 1

    def test_returns_empty_for_clean_text(self):
        """No algorithmic keywords → returns empty list."""
        text = "This function reads a file and returns its contents as a string."
        claims = find_unsupported_claims(text)
        assert claims == []

    def test_returns_context_window_around_claim(self):
        """Each claim includes surrounding context (up to 60 chars on each side)."""
        text = "Performance is excellent because we use a well-known algorithm for lookup."
        claims = find_unsupported_claims(text)
        assert len(claims) >= 1
        # The context window (60 chars) should capture text around the keyword
        assert "algorithm" in claims[0].lower()

    def test_detects_multiple_claims(self):
        """Multiple keywords in one text produce multiple claim snippets."""
        text = (
            "The algorithm is optimal for this class. "
            "It has been proven to be the fastest approach."
        )
        claims = find_unsupported_claims(text)
        assert len(claims) >= 2

    def test_case_insensitive_matching(self):
        """Keyword matching is case-insensitive (ALGORITHM matches 'algorithm')."""
        text = "This is the OPTIMAL Algorithm for the problem."
        claims = find_unsupported_claims(text)
        assert len(claims) >= 1
