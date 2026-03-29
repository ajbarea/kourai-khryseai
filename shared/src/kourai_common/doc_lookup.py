"""Documentation lookup utility for Techne & Metis.

Agents can query live API docs, standards references, and tutorials before
generating code or plans. Provides Context7 as primary source with Context Hub
(chub CLI) as fallback when Context7 is rate-limited.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from typing import Any

log = logging.getLogger(__name__)


class DocLookupError(Exception):
    """Raised when documentation lookup fails."""


async def query_context7(
    query: str,
    max_results: int = 3,
) -> list[dict[str, Any]]:
    """Query Context7 MCP sidecar for documentation.

    Connects to the context7-mcp Docker service via mcp_client.query_context7().
    The sidecar exposes the @upstash/context7-mcp server over SSE (port 3001).

    Args:
        query: Documentation search (e.g., "async/await Python 3.12").
        max_results: Max doc snippets to return (currently returns 1 rich result).

    Returns:
        List of dicts with keys: title, snippet, source_url.
        Empty list if context7-mcp sidecar is unavailable.
    """
    from kourai_common.mcp_client import (
        MCPUnavailable,
        query_context7 as mcp_query_context7,
    )

    # Use the first word as the library name; rest of query becomes the topic
    parts = query.split(None, 1)
    library = parts[0] if parts else ""
    topic = parts[1] if len(parts) > 1 else query

    if not library:
        return []

    try:
        docs_text = await mcp_query_context7(library, topic)
        if not docs_text:
            return []
        return [
            {
                "title": f"{library} — Context7 docs",
                "snippet": docs_text[:500],
                "source_url": f"https://context7.com/{library}",
            }
        ]
    except MCPUnavailable:
        log.debug("context7-mcp sidecar unavailable — falling back to Context Hub")
        return []
    except Exception as e:
        log.warning("Context7 lookup failed: %s", e)
        return []


async def query_context_hub(
    query: str,
    max_results: int = 3,
) -> list[dict[str, Any]]:
    """Query Context Hub (chub CLI) for documentation.

    Context Hub is a community-driven documentation index. Free and
    works offline via CLI fallback (chub get).

    Args:
        query: Documentation search.
        max_results: Max snippets to return.

    Returns:
        List of dicts with keys: title, snippet, source_url.
        Empty list if chub is not installed or query fails.
    """
    try:
        # Call chub CLI (added to shell allowlist in B2)
        cmd = ["chub", "get", "--query", query, "--limit", str(max_results)]

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            log.debug("chub lookup failed: %s", result.stderr)
            return []

        # Parse chub JSON output
        try:
            results = json.loads(result.stdout)
            return [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "source_url": r.get("url", ""),
                }
                for r in results.get("results", [])
            ]
        except json.JSONDecodeError:
            log.warning("chub output was not valid JSON")
            return []

    except FileNotFoundError:
        log.debug("chub not found on PATH — install via: npm install -g context-hub")
        return []
    except subprocess.TimeoutExpired:
        log.warning("chub lookup timed out")
        return []
    except Exception as e:
        log.warning("Context Hub lookup failed: %s", e)
        return []


async def lookup_documentation(
    query: str,
    agent_name: str = "unknown",
    max_results: int = 3,
) -> str:
    """Lookup documentation from Context7 (primary) or Context Hub (fallback).

    This is the main entry point for agents that need to query docs before
    generating code or plans.

    Args:
        query: Documentation search (e.g., "asyncio.gather Python semantics")
        agent_name: Agent requesting (for logging/metrics).
        max_results: Max doc snippets to return.

    Returns:
        Formatted documentation block (plain text) suitable for prompt injection.
        Empty string if no docs found (agent should proceed without context).
    """
    # Try Context7 first
    docs = await query_context7(query, max_results=max_results)

    # Fall back to Context Hub if needed
    if not docs:
        log.debug("%s: Context7 unavailable, trying Context Hub", agent_name)
        docs = await query_context_hub(query, max_results=max_results)

    if not docs:
        log.debug("%s: No documentation found for query: %s", agent_name, query)
        return ""

    # Format as readable block for prompt injection
    lines = ["=== RELEVANT DOCUMENTATION ==="]
    for doc in docs:
        lines.append(f"\n📖 {doc.get('title', 'Untitled')}")
        lines.append(f"   {doc.get('snippet', '')[:200]}...")
        url = doc.get("source_url", "")
        if url:
            lines.append(f"   Source: {url}")

    return "\n".join(lines)


async def build_docs_context(
    task_description: str,
    agent_name: str = "unknown",
) -> str:
    """Extract key terms from a task and lookup relevant documentation.

    Helper for agents that want to auto-fetch docs based on task keywords.

    Args:
        task_description: The task (e.g., "Implement async data loading for React").
        agent_name: Agent name (for logging).

    Returns:
        Documentation block or empty string.
    """
    # Extract key terms (naive keyword extraction)
    # In production, could use NLP or LLM for smarter extraction
    keywords = task_description.split()[:5]  # First 5 words
    query = " ".join(keywords)

    log.debug("%s: Extracting docs for: %s", agent_name, query)
    return await lookup_documentation(query, agent_name=agent_name)
