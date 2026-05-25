"""HTTP clients for academic citation lookup.

Three direct REST backends -- no MCP wrapper (per design spec: May 2026
100-MCP study showed median 71% pass rate; direct HTTP is more reliable).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from kourai_common.citation_artifacts import PaperMetadata

# Polite User-Agent per API guidance (S2, OpenAlex both ask for it)
_KOURAI_UA = "kourai-khryseai/aletheia-v2 (+mailto:ajbareaa@gmail.com)"


def _is_retryable(exc: BaseException) -> bool:
    """True for transient HTTP errors; False for 429 (rate-limit -- caller must
    back off, not hammer the server again).
    """
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code != 429
    return False


_RETRY = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    reraise=True,
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": _KOURAI_UA},
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
    )


def _s2_client() -> httpx.AsyncClient:
    """AsyncClient with optional S2_API_KEY header."""
    headers = {"User-Agent": _KOURAI_UA}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(15.0), follow_redirects=True)


def _s2_paper_to_meta(p: dict[str, Any]) -> PaperMetadata:
    """Convert a Semantic Scholar paper dict to PaperMetadata."""
    authors = [a.get("name", "") for a in p.get("authors", [])]
    ext = p.get("externalIds") or {}
    urls: dict[str, str] = {}
    if p.get("openAccessPdf"):
        urls["pdf"] = p["openAccessPdf"]["url"]
    if ext.get("DOI"):
        urls["doi"] = f"https://doi.org/{ext['DOI']}"
    if ext.get("ArXiv"):
        urls["abs"] = f"https://arxiv.org/abs/{ext['ArXiv']}"
    elif p.get("url"):
        urls["abs"] = p["url"]

    return PaperMetadata(
        title=p["title"],
        authors=authors or ["Unknown"],
        year=p.get("year") or 0,
        venue=p.get("venue") or None,
        arxiv_id=ext.get("ArXiv"),
        doi=ext.get("DOI"),
        urls=urls,
    )


@_RETRY
async def search_semantic_scholar(
    query: str,
    *,
    limit: int = 5,
    year_hint: int | None = None,
) -> list[PaperMetadata]:
    """Search S2's /graph/v1/paper/search endpoint."""
    params: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,venue,externalIds,openAccessPdf,url",
    }
    if year_hint:
        params["year"] = f"{year_hint - 1}-{year_hint + 1}"

    async with _s2_client() as client:
        r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    out: list[PaperMetadata] = []
    for paper in data.get("data", []):
        try:
            out.append(_s2_paper_to_meta(paper))
        except (KeyError, ValueError):
            continue
    return out


_ARXIV_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _arxiv_entry_to_meta(entry: ET.Element) -> PaperMetadata:
    title = (entry.findtext("atom:title", default="", namespaces=_ARXIV_ATOM_NS) or "").strip()
    authors: list[str] = [
        (e.findtext("atom:name", default="", namespaces=_ARXIV_ATOM_NS) or "").strip()
        for e in entry.findall("atom:author", _ARXIV_ATOM_NS)
    ]
    published = entry.findtext("atom:published", default="", namespaces=_ARXIV_ATOM_NS) or ""
    year = int(published[:4]) if len(published) >= 4 else 0
    link_abs = entry.findtext("atom:id", default="", namespaces=_ARXIV_ATOM_NS) or ""
    arxiv_id = link_abs.rsplit("/", 1)[-1].split("v")[0] if link_abs else None
    urls: dict[str, str] = {"abs": link_abs} if link_abs else {}
    if arxiv_id:
        urls["pdf"] = f"https://arxiv.org/pdf/{arxiv_id}"
        urls["html"] = f"https://arxiv.org/html/{arxiv_id}"
    return PaperMetadata(
        title=title,
        authors=authors or ["Unknown"],
        year=year,
        urls=urls,
        arxiv_id=arxiv_id,
    )


@_RETRY
async def lookup_arxiv_metadata(arxiv_id: str) -> PaperMetadata | None:
    """Fetch one paper's metadata via arXiv's Atom API."""
    async with _client() as client:
        r = await client.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id, "max_results": 1},
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)  # noqa: S314 -- arXiv Atom feed is trusted academic API
    entries = root.findall("atom:entry", _ARXIV_ATOM_NS)
    if not entries:
        return None
    return _arxiv_entry_to_meta(entries[0])


@_RETRY
async def fetch_arxiv_html(arxiv_id: str) -> str | None:
    """Fetch the arXiv HTML5 rendering of a paper (preferred over PDF).

    Available for most submissions since late 2023 via LaTeXML.
    """
    async with _client() as client:
        r = await client.get(f"https://arxiv.org/html/{arxiv_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text


def _openalex_work_to_meta(w: dict[str, Any]) -> PaperMetadata:
    authors = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])]
    doi_raw = w.get("doi") or None
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
    arxiv_id = None
    if w.get("locations"):
        for loc in w["locations"]:
            src = (loc.get("source") or {}).get("display_name", "") or ""
            if "arxiv" in src.lower() and loc.get("landing_page_url"):
                page = loc["landing_page_url"]
                if "/abs/" in page:
                    arxiv_id = page.rsplit("/abs/", 1)[-1].split("v")[0]
                    break

    urls: dict[str, str] = {}
    if w.get("doi"):
        urls["doi"] = w["doi"]
    pdf = w.get("open_access", {}).get("oa_url")
    if pdf:
        urls["pdf"] = pdf
    if arxiv_id:
        urls.setdefault("abs", f"https://arxiv.org/abs/{arxiv_id}")

    primary_loc = w.get("primary_location") or {}
    primary_src = primary_loc.get("source") or {}
    venue_name: str | None = primary_src.get("display_name") or None

    return PaperMetadata(
        title=w.get("title", ""),
        authors=authors or ["Unknown"],
        year=w.get("publication_year") or 0,
        venue=venue_name,
        arxiv_id=arxiv_id,
        doi=doi,
        urls=urls,
    )


@_RETRY
async def lookup_openalex_by_doi(doi: str) -> PaperMetadata | None:
    """OpenAlex /works/doi:{doi} lookup.

    Requires API key from openalex.org/signup (30-second registration).
    Set OPENALEX_API_KEY env var.
    """
    api_key = os.environ.get("OPENALEX_API_KEY")
    headers = {"User-Agent": _KOURAI_UA}
    # research(2026-05): OpenAlex authenticates via an `api_key` query param,
    # not a header; the keyless "polite pool" was retired 2026-02.
    params = {"api_key": api_key} if api_key else None

    async with httpx.AsyncClient(
        headers=headers, timeout=httpx.Timeout(15.0), follow_redirects=True
    ) as client:
        r = await client.get(f"https://api.openalex.org/works/doi:{doi}", params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return _openalex_work_to_meta(r.json())


@_RETRY
async def fetch_paper_pdf_text(pdf_url: str) -> str | None:
    """Download a PDF and extract its text via Docling (Apache 2.0)."""
    import asyncio
    import tempfile

    from docling.document_converter import DocumentConverter

    async with _client() as client:
        r = await client.get(pdf_url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        pdf_bytes = r.content

    def _convert() -> str:
        import pathlib

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = pathlib.Path(f.name)
        try:
            result = DocumentConverter().convert(str(tmp_path))
            return result.document.export_to_markdown()
        finally:
            tmp_path.unlink(missing_ok=True)

    return await asyncio.to_thread(_convert)
