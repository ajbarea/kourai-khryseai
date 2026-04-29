"""Weekly cron: watch MCP and A2A spec/SDK URLs, open issues on change.

Runs from ``.github/workflows/spec-watch.yml`` every Sunday plus on manual
dispatch. For each watched URL the script fetches the current content,
computes a stable digest, compares against the prior snapshot held in
``.cache/spec-watch/state.json``, and (when the digest changed) opens a
GitHub issue tagged ``protocol-watch`` summarising the delta. The state
file is preserved between CI runs via ``actions/cache``; a cache miss is
handled gracefully by treating the run as initial and emitting no
issues.

Why we built this
    Today's protocol-tracking is ad-hoc — AJ nudges Claude with "search
    the web for April 2026 best practice" and Claude does a sweep. That
    works for explicit refreshes but misses intermediate drift (e.g. v1.0
    of A2A landed with the spec-blessed ``Message.metadata`` channel for
    multi-turn metadata, but our text-tag carrier in ``a2a_utils.py``
    persisted for months because we hadn't revisited the spec). This
    cron makes "track latest aggressively" actually mean something — a
    spec change becomes an actionable inbox item rather than a thing
    we'll notice next time we happen to look.

Local usage
    ``python scripts/watch_protocols.py --dry-run`` runs the watch and
    prints what *would* be opened as issues without touching the issue
    tracker, against the local ``.cache/spec-watch/state.json`` (or
    ``KOURAI_SPEC_STATE`` if set). Useful for testing, useful for
    refreshing the snapshot manually before pushing.

Adding a new watch
    Append to ``WATCHES`` below. Pick a stable ``key`` (used as the
    state-file dict key and in the issue title), a URL, and a ``kind``
    that matches one of the ``_digest_*`` functions — extend that list
    if the new source's content shape doesn't fit ``html`` (full-content
    hash), ``feed`` (atom feed, hash entry titles), or ``pypi`` (JSON
    metadata, key on ``info.version``).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger("watch_protocols")


@dataclass(frozen=True)
class Watch:
    """A single URL we monitor for spec drift."""

    key: str
    url: str
    kind: str
    note: str  # one-liner that lands in the issue body for context


WATCHES: tuple[Watch, ...] = (
    Watch(
        key="mcp-spec-2025-11-25",
        url="https://modelcontextprotocol.io/specification/2025-11-25",
        kind="html",
        note="MCP 2025-11-25 spec page. Watch for spec edits or version bumps.",
    ),
    Watch(
        key="mcp-blog",
        url="https://blog.modelcontextprotocol.io/",
        kind="html",
        note="MCP blog index — roadmap posts, transport changes, release announcements.",
    ),
    Watch(
        key="a2a-spec-latest",
        url="https://a2a-protocol.org/latest/specification/",
        kind="html",
        note="A2A latest spec page. Watch for v1.x point releases, breaking changes, new primitives.",
    ),
    Watch(
        key="a2a-releases",
        url="https://github.com/a2aproject/A2A/releases.atom",
        kind="feed",
        note="A2A spec repo releases atom feed. New tag = new spec version.",
    ),
    Watch(
        key="mcp-spec-releases",
        # Repo was renamed `specification` -> `modelcontextprotocol` mid-2026.
        # GitHub still 301-redirects but pointing at the canonical name avoids
        # a redirect hop on every cron run (and a future cleanup of the redirect).
        url="https://github.com/modelcontextprotocol/modelcontextprotocol/releases.atom",
        kind="feed",
        note="MCP spec repo releases atom feed. New tag = new spec dated revision.",
    ),
    Watch(
        key="a2a-sdk-pypi",
        url="https://pypi.org/pypi/a2a-sdk/json",
        kind="pypi",
        note=(
            "a2a-sdk on PyPI. Stable 1.0.x landed 2026-04-20 (1.0.0); "
            "1.0.2 current. Pyproject still pinned <1.0; M7 cutover is the "
            "scoped-but-unstarted migration captured in IMPL.md → ROADMAP M7. "
            "Future 1.0.x point releases bumping this digest are the safe "
            "kind of drift; a 1.1.x or 2.x bump is a re-scope signal."
        ),
    ),
    Watch(
        key="mcp-pypi",
        url="https://pypi.org/pypi/mcp/json",
        kind="pypi",
        note="mcp Python SDK on PyPI. Used by our memory-mcp / context7-mcp / future M2 server.",
    ),
    Watch(
        key="dozzle-docker-tag",
        url="https://hub.docker.com/v2/repositories/amir20/dozzle/tags?page_size=20",
        kind="docker-tag",
        note=(
            "Dozzle (M16 observability log dashboard) image tag stream. "
            "The original PR shipped two majors stale (v8.13.0 → v10.5.0 "
            "mid-PR) because nothing watched the tag stream; this catches "
            "future drift automatically."
        ),
    ),
    Watch(
        key="jaeger-docker-tag",
        url="https://hub.docker.com/v2/repositories/jaegertracing/jaeger/tags?page_size=20",
        kind="docker-tag",
        note=(
            "Jaeger v2 image tag stream. Jaeger v1 went EOL 2025-12-31; "
            "currency on the trace plane matters for security patches on a "
            "process with read access to every inter-agent trace."
        ),
    ),
    Watch(
        key="prometheus-docker-tag",
        url="https://hub.docker.com/v2/repositories/prom/prometheus/tags?page_size=20",
        kind="docker-tag",
        note=(
            "Prometheus distroless image tag stream. v3.x is the current "
            "generation; the v2.55 → v3 staircase was mandatory hygiene "
            "even for a no-persistent-volume dev-loop deployment."
        ),
    ),
)


_HTTP_TIMEOUT = 20.0


def fetch(url: str) -> str:
    """Return the response body as text; raises on non-2xx for caller logging."""
    response = httpx.get(url, timeout=_HTTP_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    return response.text


def _digest_html(content: str) -> tuple[str, str]:
    """Hash full HTML; excerpt is the first <title> and first ~400 chars of body."""
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ""
    digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]
    body_text = re.sub(r"<[^>]+>", " ", content)
    body_text = re.sub(r"\s+", " ", body_text).strip()
    excerpt_parts = []
    if title:
        excerpt_parts.append(f"title: {title}")
    excerpt_parts.append(f"body[:400]: {body_text[:400]}")
    return digest, "\n".join(excerpt_parts)


def _digest_feed(content: str) -> tuple[str, str]:
    """Atom feed — hash the latest entry title + id; excerpt shows top-3 entries."""
    titles = re.findall(r"<title[^>]*>([^<]+)</title>", content)
    # First title is typically the feed title; the rest are entries.
    entries = titles[1:] if len(titles) > 1 else titles
    digest_input = "\n".join(entries[:5])  # first 5 entries — covers a handful of recent releases
    digest = hashlib.sha256(digest_input.encode("utf-8", errors="replace")).hexdigest()[:16]
    excerpt_lines = ["latest entries:"] + [f"  - {t.strip()}" for t in entries[:3]]
    return digest, "\n".join(excerpt_lines)


def _digest_pypi(content: str) -> tuple[str, str]:
    """PyPI JSON — digest is the version string itself; excerpt shows versions+date."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.warning("PyPI JSON malformed: %s", exc)
        return "<malformed>", "JSON decode failed"
    info = data.get("info") or {}
    version = info.get("version", "<unknown>")
    upload_time = ""
    releases = data.get("releases") or {}
    files = releases.get(version) or []
    if files:
        upload_time = files[0].get("upload_time", "") or files[0].get("upload_time_iso_8601", "")
    excerpt = f"version: {version}\nuploaded: {upload_time}\nname: {info.get('name', '')}"
    return version, excerpt


# Mutable / non-release tags that should never be picked as the "latest
# release" by the docker-tag digester — they always point at the head of
# some moving stream and would either trigger drift on every cron tick
# or, worse, mask real version bumps under a stable name.
_MUTABLE_DOCKER_TAGS: frozenset[str] = frozenset(
    {"latest", "master", "main", "nightly", "edge", "develop", "dev", "stable"}
)


# Live smoke against Docker Hub during M16 follow-on caught three failure
# modes the mutable-tag set didn't cover:
#   1. PR-build artifacts (``pr-4662`` in dozzle) — churn constantly.
#   2. Major-version aliases (``v3-distroless`` in prometheus) — point at
#      the head of v3.x and would mask real version bumps under a moving
#      alias.
#   3. Minor-stream aliases (``v10.5`` in dozzle) — re-pushed when a new
#      10.5.x patch lands but the tag name stays the same, so a
#      name-only digest would never flip.
# Restricting candidates to a full ``MAJOR.MINOR.PATCH`` triplet catches
# all three: real releases always carry the full triplet (``v10.5.0``,
# ``2.17.0``, ``v3.10.0-distroless``); aliases and build artifacts don't.
_SEMVER_LIKE = re.compile(r"\d+\.\d+\.\d+")


def _digest_docker_tag(content: str) -> tuple[str, str]:
    """Docker Hub repositories/<ns>/<repo>/tags JSON.

    Picks the most recently pushed *stable* tag (active, non-mutable name,
    semver-shaped) and uses its name as the digest — when a new tag
    releases, the digest flips and an issue opens. Excerpt shows the top
    three candidates so the triage path includes the surrounding
    release-cadence context (e.g. is this a routine point release, or a
    major bump).
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.warning("Docker Hub JSON malformed: %s", exc)
        return "<malformed>", "JSON decode failed"
    results = data.get("results") or []
    candidates = [
        r
        for r in results
        if r.get("tag_status") == "active"
        and isinstance(r.get("name"), str)
        and r["name"].lower() not in _MUTABLE_DOCKER_TAGS
        and _SEMVER_LIKE.search(r["name"]) is not None
    ]
    if not candidates:
        return "<no-stable-tag>", "no stable tag found in Docker Hub response"
    # Sort newest-first by last_updated; Docker Hub returns ISO-8601 strings
    # which sort lexicographically.
    candidates.sort(key=lambda r: r.get("last_updated", ""), reverse=True)
    latest = candidates[0]
    digest = latest["name"]
    excerpt_lines = [
        f"latest stable tag: {digest}",
        f"last_updated: {latest.get('last_updated', '')}",
        "top candidates:",
        *(f"  - {r['name']} ({r.get('last_updated', '')})" for r in candidates[:3]),
    ]
    return digest, "\n".join(excerpt_lines)


_DIGESTERS: dict[str, Callable[[str], tuple[str, str]]] = {
    "html": _digest_html,
    "feed": _digest_feed,
    "pypi": _digest_pypi,
    "docker-tag": _digest_docker_tag,
}


@dataclass
class Change:
    """One watch flipped from the prior snapshot — caller decides whether to act."""

    watch: Watch
    prior_digest: str
    current_digest: str
    excerpt: str
    checked_at: str


def diff_watches(
    watches: tuple[Watch, ...],
    state: dict[str, Any],
    fetcher: Callable[[str], str],
) -> tuple[list[Change], dict[str, Any]]:
    """Pure: fetch each watch, compute digests, return changes + new state.

    Splitting this from the IO of issue-creation makes the loop unit-testable
    with a mocked ``fetcher`` and an in-memory state dict.
    """
    changes: list[Change] = []
    new_state: dict[str, Any] = {}
    now_iso = _dt.datetime.now(_dt.UTC).isoformat()
    for watch in watches:
        try:
            content = fetcher(watch.url)
        except Exception as exc:
            log.warning("Fetch failed for %s (%s): %s", watch.key, watch.url, exc)
            # Carry the prior snapshot forward unchanged so a transient outage
            # doesn't wipe state. Equivalent to "missed this week."
            if watch.key in state:
                new_state[watch.key] = state[watch.key]
            continue
        digester = _DIGESTERS.get(watch.kind)
        if digester is None:
            log.error("No digester registered for kind=%s (key=%s)", watch.kind, watch.key)
            continue
        digest, excerpt = digester(content)
        new_state[watch.key] = {
            "digest": digest,
            "url": watch.url,
            "checked_at": now_iso,
        }
        prior = (state.get(watch.key) or {}).get("digest")
        if prior is not None and prior != digest:
            changes.append(
                Change(
                    watch=watch,
                    prior_digest=prior,
                    current_digest=digest,
                    excerpt=excerpt,
                    checked_at=now_iso,
                )
            )
    return changes, new_state


def format_issue_body(change: Change) -> str:
    """Markdown body for the GitHub issue. Stable shape so the format itself
    isn't a moving target; future readers grep for `prior_digest` etc."""
    return (
        f"**Watch key:** `{change.watch.key}`\n"
        f"**URL:** {change.watch.url}\n"
        f"**Kind:** `{change.watch.kind}`\n"
        f"**Checked at:** {change.checked_at}\n"
        f"**Prior digest:** `{change.prior_digest}`\n"
        f"**Current digest:** `{change.current_digest}`\n\n"
        f"**Note:** {change.watch.note}\n\n"
        "---\n\n"
        "**Current excerpt:**\n\n"
        f"```\n{change.excerpt}\n```\n\n"
        "---\n\n"
        "_Auto-opened by `scripts/watch_protocols.py`. Triage path: read the "
        "linked URL, check the diff against the prior digest, and decide "
        "whether ROADMAP M2 (forge MCP) or M7 (a2a-sdk migration) needs to "
        "shift. Close as `not-actionable` if the change is incidental "
        "(typo, tracking-pixel, etc.); convert to a follow-up PR otherwise._"
    )


def open_issue(change: Change, *, dry_run: bool, repo: str | None) -> None:
    """Either ``gh issue create`` or print the body when dry-running."""
    title = f"Protocol watch: {change.watch.key} drifted ({change.prior_digest} -> {change.current_digest})"
    body = format_issue_body(change)
    if dry_run or not repo:
        print(f"\n=== DRY RUN ISSUE: {title} ===")
        print(body)
        print("=== END DRY RUN ===\n")
        return
    cmd = [
        "gh",
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--label",
        "protocol-watch",
        "--body",
        body,
    ]
    try:
        # cmd is a fixed list invocation of `gh` with our own dataclass values
        # (Watch.key/url/note are constants; digests are sha256 hex / version
        # strings). No shell, no untrusted input — S603 is a false positive
        # for this call shape.
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
        log.info("Opened issue for %s: %s", change.watch.key, result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        # Don't crash the run on a single issue failure — log + continue.
        # The state file still gets the new digest, so the next run won't
        # re-flag this same change unless it shifts again.
        log.error("gh issue create failed for %s: %s", change.watch.key, exc.stderr)


def load_state(path: Path) -> dict[str, Any]:
    """Read the prior snapshot, returning an empty dict if absent or malformed."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("State file %s unreadable (%s); treating as initial run", path, exc)
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically replace the snapshot file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("KOURAI_PROTOCOL_WATCH_DRY_RUN") == "1",
        help="Print would-be issues to stdout; do not call gh.",
    )
    p.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("KOURAI_SPEC_STATE", ".cache/spec-watch/state.json")),
        help="Path to the snapshot JSON file (default: .cache/spec-watch/state.json).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = _build_arg_parser().parse_args(argv)
    state = load_state(args.state)
    changes, new_state = diff_watches(WATCHES, state, fetch)
    save_state(args.state, new_state)
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not changes:
        log.info("No drift across %d watches.", len(WATCHES))
        return 0
    log.info("Detected %d change(s); opening issues.", len(changes))
    for change in changes:
        open_issue(change, dry_run=args.dry_run, repo=repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
