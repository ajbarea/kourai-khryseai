"""Tests for doc_lookup.py — Context7 MCP round-trip and fallback chain.

Phase 4.2: Tests Context7 → Context Hub fallback, formatting, and graceful
degradation when the MCP sidecar is unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from kourai_common.doc_lookup import (
    build_docs_context,
    lookup_documentation,
    query_context7,
    query_context_hub,
)
from kourai_common.mcp_client import MCPUnavailable

# ── query_context7 ────────────────────────────────────────────────────────────


class TestQueryContext7:
    @pytest.mark.asyncio
    async def test_returns_result_when_sidecar_available(self):
        """Returns a single-item list with title/snippet/source_url when MCP responds."""
        mock_docs = "FastAPI routes are defined using @app.get() decorators..."
        with patch(
            "kourai_common.mcp_client.query_context7",
            new=AsyncMock(return_value=mock_docs),
        ):
            results = await query_context7("fastapi routes")

        assert len(results) == 1
        assert "fastapi" in results[0]["title"].lower()
        assert results[0]["snippet"] == mock_docs[:500]
        assert "source_url" in results[0]

    @pytest.mark.asyncio
    async def test_returns_empty_when_mcp_unavailable(self):
        """Returns [] without raising when the Context7 sidecar raises MCPUnavailable."""
        with patch(
            "kourai_common.mcp_client.query_context7",
            new=AsyncMock(side_effect=MCPUnavailable("sidecar not running")),
        ):
            results = await query_context7("asyncio gather")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_unexpected_error(self):
        """Catches unexpected exceptions and returns [] without propagating."""
        with patch(
            "kourai_common.mcp_client.query_context7",
            new=AsyncMock(side_effect=RuntimeError("network blip")),
        ):
            results = await query_context7("react hooks")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_blank_query(self):
        """Returns [] immediately without calling MCP for an empty query string."""
        with patch(
            "kourai_common.mcp_client.query_context7",
            new=AsyncMock(return_value="some docs"),
        ) as mock_mcp:
            results = await query_context7("")

        assert results == []
        mock_mcp.assert_not_called()

    @pytest.mark.asyncio
    async def test_splits_query_into_library_and_topic(self):
        """First word is the library; remaining words become the topic."""
        captured: dict[str, str] = {}

        async def capture(library: str, topic: str, **_: object) -> str:
            captured["library"] = library
            captured["topic"] = topic
            return "some docs"

        with patch("kourai_common.mcp_client.query_context7", new=capture):
            await query_context7("asyncio gather semantics Python 3.12")

        assert captured["library"] == "asyncio"
        assert captured["topic"] == "gather semantics Python 3.12"

    @pytest.mark.asyncio
    async def test_returns_empty_when_mcp_returns_empty_string(self):
        """An empty string from the sidecar means no docs — return []."""
        with patch(
            "kourai_common.mcp_client.query_context7",
            new=AsyncMock(return_value=""),
        ):
            results = await query_context7("fastapi docs")

        assert results == []

    @pytest.mark.asyncio
    async def test_single_word_query_uses_same_word_for_both(self):
        """Single-word query: library == query, topic == query (no split)."""
        captured: dict[str, str] = {}

        async def capture(library: str, topic: str, **_: object) -> str:
            captured["library"] = library
            captured["topic"] = topic
            return "docs"

        with patch("kourai_common.mcp_client.query_context7", new=capture):
            await query_context7("asyncio")

        assert captured["library"] == "asyncio"
        assert captured["topic"] == "asyncio"


# ── query_context_hub ─────────────────────────────────────────────────────────


class TestQueryContextHub:
    @pytest.mark.asyncio
    async def test_returns_empty_when_chub_not_found(self):
        """chub not on PATH → FileNotFoundError is caught, returns []."""

        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=FileNotFoundError("chub not found")),
        ):
            results = await query_context_hub("react hooks")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_non_zero_returncode(self):
        """chub returns non-zero exit code → returns []."""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "not found"

        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_result)):
            results = await query_context_hub("some query")

        assert results == []


# ── lookup_documentation ──────────────────────────────────────────────────────


class TestLookupDocumentation:
    @pytest.mark.asyncio
    async def test_returns_formatted_block_when_context7_responds(self):
        """Returns a non-empty documentation block when Context7 has results."""
        mock_result = [
            {
                "title": "asyncio — Context7 docs",
                "snippet": "gather() runs coroutines concurrently...",
                "source_url": "https://context7.com/asyncio",
            }
        ]
        with patch(
            "kourai_common.doc_lookup.query_context7",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await lookup_documentation("asyncio event loop", agent_name="techne")

        assert "RELEVANT DOCUMENTATION" in result
        assert "asyncio" in result
        assert "context7.com" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_context_hub_when_context7_empty(self):
        """When Context7 returns [], lookup falls back to Context Hub."""
        hub_result = [
            {
                "title": "React Hooks Guide",
                "snippet": "useState manages component state...",
                "source_url": "https://react.dev/hooks",
            }
        ]
        with (
            patch(
                "kourai_common.doc_lookup.query_context7",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "kourai_common.doc_lookup.query_context_hub",
                new=AsyncMock(return_value=hub_result),
            ),
        ):
            result = await lookup_documentation("react hooks", agent_name="techne")

        assert "React Hooks Guide" in result

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_both_sources_empty(self):
        """Returns '' when both Context7 and Context Hub return []."""
        with (
            patch(
                "kourai_common.doc_lookup.query_context7",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "kourai_common.doc_lookup.query_context_hub",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await lookup_documentation("unknownlib", agent_name="metis")

        assert result == ""

    @pytest.mark.asyncio
    async def test_context_hub_not_called_when_context7_succeeds(self):
        """Context Hub is NOT queried if Context7 already returns results."""
        mock_result = [{"title": "FastAPI", "snippet": "...", "source_url": "http://x"}]
        hub_mock = AsyncMock(return_value=[])
        with (
            patch(
                "kourai_common.doc_lookup.query_context7",
                new=AsyncMock(return_value=mock_result),
            ),
            patch("kourai_common.doc_lookup.query_context_hub", new=hub_mock),
        ):
            await lookup_documentation("fastapi async", agent_name="techne")

        hub_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_format_includes_source_url(self):
        """Output block includes the source URL for the found documentation."""
        mock_result = [
            {
                "title": "Python asyncio",
                "snippet": "event loop manages coroutines",
                "source_url": "https://docs.python.org/asyncio",
            }
        ]
        with patch(
            "kourai_common.doc_lookup.query_context7",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await lookup_documentation("asyncio", agent_name="metis")

        assert "docs.python.org/asyncio" in result


# ── build_docs_context ────────────────────────────────────────────────────────


class TestBuildDocsContext:
    @pytest.mark.asyncio
    async def test_extracts_first_five_words_as_query(self):
        """build_docs_context passes the first 5 words to lookup_documentation."""
        captured: dict[str, str] = {}

        async def capture(query: str, agent_name: str = "unknown", **_: object) -> str:
            captured["query"] = query
            return ""

        with patch("kourai_common.doc_lookup.lookup_documentation", new=capture):
            await build_docs_context(
                "Implement async data loading for React with suspense",
                agent_name="techne",
            )

        assert captured["query"] == "Implement async data loading for"

    @pytest.mark.asyncio
    async def test_propagates_doc_block(self):
        """Returns the documentation string from lookup_documentation."""
        with patch(
            "kourai_common.doc_lookup.lookup_documentation",
            new=AsyncMock(return_value="=== RELEVANT DOCUMENTATION ===\n📖 asyncio"),
        ):
            result = await build_docs_context("asyncio gather usage", agent_name="metis")

        assert "RELEVANT DOCUMENTATION" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_docs_found(self):
        """Returns '' when lookup_documentation finds nothing."""
        with patch(
            "kourai_common.doc_lookup.lookup_documentation",
            new=AsyncMock(return_value=""),
        ):
            result = await build_docs_context("some obscure task", agent_name="techne")

        assert result == ""
