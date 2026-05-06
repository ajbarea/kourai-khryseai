"""Content-addressable disk cache for TTS synth output.

Wraps an engine's bytes-returning synth call with a disk cache keyed
by ``sha256(text + voice_id + model_id + voice_settings_json)``.
Identical inputs return the cached bytes; misses run the supplied
``fetch`` callable and write the result.

Layout::

    ${XDG_CACHE_HOME:-~/.cache}/kourai/tts/{key[:2]}/{key}.{ext}

The two-char shard prefix prevents inode bloat on large caches; the
full hex digest as filename keeps the layout greppable for debugging
("did kourai cache this line?" answers via plain ``find``).

Eviction is size-bounded with oldest-mtime-first removal when total
on-disk bytes exceed the cap (default 500 MB). Eviction runs on every
miss-write; the directory walk is O(files) and 500 MB at ~50 KB per
WAV is ~10 K files, well inside cheap. No TTL — same engine + same
inputs is deterministic, so a hit is always valid.

`research(2026-05)`: rolled custom rather than diskcache because the
spec wants greppable hex filenames + 2-char shard prefix; diskcache
stores opaque rowid-keyed values inside a SQLite file plus value
files under random hex names. ~150 LOC of stdlib fits without the
SQLite layer or its ~3 MB dep footprint. Source: diskcache tutorial
(storage layout) + ElevenLabs Supabase cookbook (client-side
caching pattern — server-side caching by content hash is not
provided by ElevenLabs).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

logger = logging.getLogger(__name__)

DEFAULT_CACHE_SIZE_BYTES: int = 500 * 1024 * 1024
"""500 MB default cap. Spec'd in IMPL.md M6 sub-task 2."""


def _xdg_cache_home() -> Path:
    """Resolve ``${XDG_CACHE_HOME:-~/.cache}`` per the XDG Base Directory spec.

    Empty-string env value treated identically to unset (XDG spec section
    "Variables") so that ``XDG_CACHE_HOME=""`` doesn't write to ``/kourai/tts``.
    """
    raw = os.environ.get("XDG_CACHE_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".cache"


def default_cache_dir() -> Path:
    """The default cache root: ``<xdg cache home>/kourai/tts``."""
    return _xdg_cache_home() / "kourai" / "tts"


def hash_key(
    text: str,
    voice_id: str,
    model_id: str,
    voice_settings: Mapping[str, Any],
) -> str:
    """Compute a stable sha256 hex digest from the synth request shape.

    ``voice_settings`` is JSON-serialized with ``sort_keys=True`` so dict
    insertion order doesn't affect the digest. Fields are length-prefixed
    when concatenated (``f"{len(b)}:{b}"`` per field), which makes the
    encoding uniquely parseable and immune to cross-field collisions
    like ``"ab|cd" + "ef"`` vs ``"ab" + "cd|ef"`` even if a separator
    byte showed up inside an input. Length is taken on the UTF-8 byte
    string so multibyte characters can't perturb the prefix.

    Note: ``1`` (int) and ``1.0`` (float) hash differently because
    ``json.dumps`` preserves the distinction; synthesizers may treat
    them differently. Callers that want them collapsed should normalize
    types upstream before passing here.
    """
    settings_json = json.dumps(voice_settings, sort_keys=True, default=str)
    h = hashlib.sha256()
    for field in (text, voice_id, model_id, settings_json):
        encoded = field.encode("utf-8")
        h.update(f"{len(encoded)}:".encode("ascii"))
        h.update(encoded)
    return h.hexdigest()


def _path_for_key(cache_dir: Path, key: str, extension: str) -> Path:
    return cache_dir / key[:2] / f"{key}.{extension}"


def read_cached(cache_dir: Path, key: str, extension: str) -> bytes | None:
    """Return cached bytes for ``key``, or ``None`` on miss / read failure.

    Read errors are swallowed and logged at WARNING — a degraded cache
    must not break synthesis. The caller falls through to ``fetch``.
    """
    path = _path_for_key(cache_dir, key, extension)
    try:
        return path.read_bytes()
    except (FileNotFoundError, IsADirectoryError):
        return None
    except OSError as exc:
        logger.warning("tts_cache: read failed for %s (%s)", path, exc)
        return None


def write_cached(cache_dir: Path, key: str, extension: str, data: bytes) -> bool:
    """Write ``data`` to the cache atomically. Returns True on success.

    Atomicity: write to a sibling ``.tmp`` file under the same directory
    (so ``os.replace`` stays on the same filesystem) and rename into
    place. POSIX ``rename`` is atomic; concurrent writers may race but
    both wrote bytes the cache promises to be equivalent (deterministic
    synth from identical inputs), so the race is harmless.
    """
    path = _path_for_key(cache_dir, key, extension)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{key}-",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(data)
            tmp_name = tmp.name
        Path(tmp_name).replace(path)
        return True
    except OSError as exc:
        logger.warning("tts_cache: write failed for %s (%s)", path, exc)
        return False


def cache_size_bytes(cache_dir: Path) -> int:
    """Sum on-disk bytes of all non-dotfile entries under ``cache_dir``.

    Returns 0 if the directory is missing. Dotfiles are skipped so that
    in-flight ``.tmp`` artifacts from atomic writes don't count toward
    the cap (which would otherwise force premature eviction).
    """
    if not cache_dir.exists():
        return 0
    total = 0
    for entry in cache_dir.rglob("*"):
        try:
            if entry.is_file() and not entry.name.startswith("."):
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def evict_if_over_cap(cache_dir: Path, cap_bytes: int) -> int:
    """Evict oldest-mtime files until total ≤ ``cap_bytes``. Returns bytes freed.

    No-op when total is already under the cap or when ``cache_dir`` is
    missing. Walks the directory once, sorts by mtime, deletes oldest-first
    until the running total drops to or below the cap.

    Eviction order is "oldest by mtime", which is FIFO-ish — read access
    doesn't update mtime by default. For kourai's static-dialogue use
    case (HANDOFF_LINES, VICTORY_LINES, etc.) FIFO and LRU converge:
    those entries are written once and read many times, so they all
    stay hot until the cap forces a sweep of genuinely-cold entries.
    """
    if not cache_dir.exists():
        return 0
    files: list[tuple[float, int, Path]] = []
    total = 0
    for entry in cache_dir.rglob("*"):
        try:
            if entry.is_file() and not entry.name.startswith("."):
                stat = entry.stat()
                files.append((stat.st_mtime, stat.st_size, entry))
                total += stat.st_size
        except OSError:
            continue
    if total <= cap_bytes:
        return 0
    files.sort(key=lambda x: x[0])  # oldest mtime first
    freed = 0
    for _, size, path in files:
        if total - freed <= cap_bytes:
            break
        try:
            path.unlink()
            freed += size
        except OSError:
            continue
    if freed:
        logger.info(
            "tts_cache: evicted %d bytes (total was %d, cap %d)",
            freed,
            total,
            cap_bytes,
        )
    return freed


async def cached_synthesize(
    text: str,
    voice_id: str,
    model_id: str,
    voice_settings: Mapping[str, Any],
    *,
    fetch: Callable[[], Awaitable[bytes]],
    cache_dir: Path | None = None,
    extension: str = "wav",
    cacheable: bool = True,
    size_cap_bytes: int = DEFAULT_CACHE_SIZE_BYTES,
) -> bytes:
    """Return synth bytes for the request, calling ``fetch`` on miss.

    Engine-agnostic: ``fetch`` is the engine's actual synth call, wrapped
    in a closure that captures voice / settings / etc. The cache module
    only knows about bytes and content-hash keys.

    Empty fetch results are returned to the caller but not written to
    disk — empty WAVs would clutter the cache and block real-content
    writes once they happened.

    ``cacheable=False`` is the dynamic-content opt-out: fetch always
    runs, no read, no write. Use for one-shot LLM responses or anything
    else where the hit rate would be near zero.

    Eviction runs on every miss-write — see :func:`evict_if_over_cap`
    for the size-bounded oldest-first pass.
    """
    if not cacheable:
        return await fetch()
    cdir = cache_dir if cache_dir is not None else default_cache_dir()
    key = hash_key(text, voice_id, model_id, voice_settings)
    cached = read_cached(cdir, key, extension)
    if cached is not None:
        logger.debug("tts_cache: hit voice=%s key=%s len=%d", voice_id, key[:8], len(cached))
        return cached
    data = await fetch()
    if not data:
        return data
    if write_cached(cdir, key, extension, data):
        logger.debug(
            "tts_cache: miss-write voice=%s key=%s len=%d",
            voice_id,
            key[:8],
            len(data),
        )
        # Best-effort eviction; offload the directory walk so it doesn't
        # block the synth-return on the awaiter's side.
        await asyncio.to_thread(evict_if_over_cap, cdir, size_cap_bytes)
    return data
