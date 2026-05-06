"""Unit tests for kourai_common.tts_cache.

Content-addressable disk cache for TTS synth output. Tests cover the
hash key shape, sharded filesystem layout, atomic writes, oldest-mtime
eviction, and the engine-agnostic ``cached_synthesize`` wrapper.

Cache root is always overridden to ``tmp_path`` so the user's real
``${XDG_CACHE_HOME}/kourai/tts`` is never touched.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from kourai_common.tts_cache import (
    cache_size_bytes,
    cached_synthesize,
    default_cache_dir,
    evict_if_over_cap,
    hash_key,
    read_cached,
    write_cached,
)

# ===================================================================
# hash_key — deterministic, sensitive to every input axis
# ===================================================================


class TestHashKey:
    def test_returns_sha256_hex_digest(self):
        key = hash_key("hello", "af_heart", "kokoro", {})
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic_across_calls(self):
        a = hash_key("hello", "af_heart", "kokoro", {"speed": 1.0})
        b = hash_key("hello", "af_heart", "kokoro", {"speed": 1.0})
        assert a == b

    def test_text_sensitivity(self):
        a = hash_key("hello", "af_heart", "kokoro", {})
        b = hash_key("world", "af_heart", "kokoro", {})
        assert a != b

    def test_voice_sensitivity(self):
        a = hash_key("hi", "af_heart", "kokoro", {})
        b = hash_key("hi", "am_michael", "kokoro", {})
        assert a != b

    def test_model_sensitivity(self):
        a = hash_key("hi", "af_heart", "kokoro", {})
        b = hash_key("hi", "af_heart", "eleven_v3", {})
        assert a != b

    def test_settings_sensitivity(self):
        a = hash_key("hi", "af_heart", "kokoro", {"speed": 1.0})
        b = hash_key("hi", "af_heart", "kokoro", {"speed": 1.5})
        assert a != b

    def test_settings_dict_order_invariant(self):
        """sorted-keys serialization must mean dict-insertion order is irrelevant."""
        a = hash_key("hi", "af_heart", "kokoro", {"speed": 1.0, "pitch": 1.1})
        b = hash_key("hi", "af_heart", "kokoro", {"pitch": 1.1, "speed": 1.0})
        assert a == b

    def test_settings_value_types_normalized(self):
        """``default=str`` lets Mapping values that aren't JSON-native still hash;
        identical str-coerced values yield identical keys."""
        a = hash_key("hi", "af_heart", "kokoro", {"speed": 1})
        b = hash_key("hi", "af_heart", "kokoro", {"speed": 1.0})
        # 1 vs 1.0 serialize differently in json (1 vs 1.0); they SHOULD
        # produce different keys — synthesizers may treat ints / floats
        # differently. This test pins that behaviour as documented.
        assert a != b

    def test_separator_collision_resistant(self):
        """The NUL separator can't collide across input boundaries."""
        # If the separator were '|', "ab|cd" + "ef" would collide with
        # "ab" + "cd|ef". NUL bytes can't appear in any of our text inputs.
        a = hash_key("ab\0cd", "ef", "kokoro", {})
        b = hash_key("ab", "cd\0ef", "kokoro", {})
        assert a != b


# ===================================================================
# default_cache_dir — XDG-compliant resolution
# ===================================================================


class TestDefaultCacheDir:
    def test_uses_xdg_cache_home_when_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        assert default_cache_dir() == tmp_path / "xdg" / "kourai" / "tts"

    def test_falls_back_to_home_cache_when_unset(self, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert default_cache_dir() == Path.home() / ".cache" / "kourai" / "tts"

    def test_falls_back_to_home_cache_when_empty(self, monkeypatch):
        """XDG spec: empty string is treated identically to unset."""
        monkeypatch.setenv("XDG_CACHE_HOME", "")
        assert default_cache_dir() == Path.home() / ".cache" / "kourai" / "tts"


# ===================================================================
# read_cached / write_cached — sharded filesystem layout, atomic writes
# ===================================================================


class TestReadWrite:
    def test_read_returns_none_on_miss(self, tmp_path):
        assert read_cached(tmp_path, "deadbeef" * 8, "wav") is None

    def test_write_creates_sharded_path(self, tmp_path):
        key = "ab" + "0" * 62
        write_cached(tmp_path, key, "wav", b"hello")
        # Layout must place the file under {key[:2]}/{key}.{ext}
        assert (tmp_path / "ab" / f"{key}.wav").is_file()

    def test_write_then_read_roundtrips(self, tmp_path):
        key = "cd" + "1" * 62
        assert write_cached(tmp_path, key, "wav", b"hello world") is True
        assert read_cached(tmp_path, key, "wav") == b"hello world"

    def test_write_creates_parent_dir(self, tmp_path):
        # Nested cache dir that doesn't exist yet — write should mkdir.
        cache = tmp_path / "nested" / "tts"
        key = "ef" + "2" * 62
        assert write_cached(cache, key, "wav", b"x") is True
        assert (cache / "ef" / f"{key}.wav").is_file()

    def test_write_overwrites_existing(self, tmp_path):
        key = "ff" + "3" * 62
        write_cached(tmp_path, key, "wav", b"first")
        write_cached(tmp_path, key, "wav", b"second")
        assert read_cached(tmp_path, key, "wav") == b"second"

    def test_write_does_not_leave_tmpfile_after_success(self, tmp_path):
        """Atomic write via NamedTemporaryFile + os.replace must leave no .tmp behind."""
        key = "12" + "4" * 62
        write_cached(tmp_path, key, "wav", b"clean")
        leftovers = list((tmp_path / "12").glob("*.tmp"))
        assert leftovers == []

    def test_write_returns_false_on_oserror(self, tmp_path, monkeypatch):
        """Permission / disk-full / etc. degrades gracefully — function returns
        False, caller still returns the bytes from the synth call.
        """

        def boom(*_args, **_kwargs):
            raise OSError("no space left on device")

        monkeypatch.setattr(Path, "mkdir", boom)
        result = write_cached(tmp_path, "aa" + "0" * 62, "wav", b"data")
        assert result is False

    def test_read_returns_none_on_oserror(self, tmp_path, monkeypatch):
        """Read failure (not just FileNotFoundError) should not raise."""

        def boom(*_args, **_kwargs):
            raise OSError("io error")

        # Make read_bytes raise; layout must still resolve to a path first.
        monkeypatch.setattr(Path, "read_bytes", boom)
        # Touch a file so it's "present" but can't be read.
        key = "bc" + "5" * 62
        (tmp_path / "bc").mkdir()
        (tmp_path / "bc" / f"{key}.wav").write_bytes(b"x")
        assert read_cached(tmp_path, key, "wav") is None

    def test_read_returns_none_when_path_is_directory(self, tmp_path):
        """Pathological case: a directory exists where a file should be."""
        key = "de" + "6" * 62
        (tmp_path / "de" / f"{key}.wav").mkdir(parents=True)
        assert read_cached(tmp_path, key, "wav") is None


# ===================================================================
# cache_size_bytes / evict_if_over_cap — size-bounded LRU-by-mtime
# ===================================================================


class TestEviction:
    def test_size_zero_when_dir_missing(self, tmp_path):
        assert cache_size_bytes(tmp_path / "does-not-exist") == 0

    def test_size_zero_when_dir_empty(self, tmp_path):
        assert cache_size_bytes(tmp_path) == 0

    def test_size_sums_files(self, tmp_path):
        write_cached(tmp_path, "aa" + "0" * 62, "wav", b"x" * 100)
        write_cached(tmp_path, "bb" + "1" * 62, "wav", b"y" * 200)
        assert cache_size_bytes(tmp_path) == 300

    def test_size_excludes_dotfiles(self, tmp_path):
        """In-flight .tmp atomic-write artifacts must not count toward the cap."""
        (tmp_path / "aa").mkdir()
        (tmp_path / "aa" / "real.wav").write_bytes(b"x" * 100)
        (tmp_path / "aa" / ".inflight-write.tmp").write_bytes(b"y" * 9999)
        assert cache_size_bytes(tmp_path) == 100

    def test_evict_no_op_under_cap(self, tmp_path):
        write_cached(tmp_path, "aa" + "0" * 62, "wav", b"x" * 100)
        freed = evict_if_over_cap(tmp_path, cap_bytes=1000)
        assert freed == 0
        assert cache_size_bytes(tmp_path) == 100

    def test_evict_removes_oldest_first(self, tmp_path):
        # Three files with controlled mtimes: oldest evicts first.
        keys = ["aa" + "0" * 62, "bb" + "1" * 62, "cc" + "2" * 62]
        for k in keys:
            write_cached(tmp_path, k, "wav", b"x" * 100)

        # Stagger mtimes — aa older, bb middle, cc newest.
        paths = [tmp_path / k[:2] / f"{k}.wav" for k in keys]
        os.utime(paths[0], (1_000_000_000, 1_000_000_000))
        os.utime(paths[1], (2_000_000_000, 2_000_000_000))
        os.utime(paths[2], (3_000_000_000, 3_000_000_000))

        # Cap at 200 bytes — must evict ONE file (the oldest).
        freed = evict_if_over_cap(tmp_path, cap_bytes=200)
        assert freed == 100
        assert not paths[0].exists()
        assert paths[1].exists()
        assert paths[2].exists()

    def test_evict_stops_when_under_cap(self, tmp_path):
        """Don't over-evict: stop as soon as remaining ≤ cap."""
        keys = ["aa" + "0" * 62, "bb" + "1" * 62, "cc" + "2" * 62]
        for k in keys:
            write_cached(tmp_path, k, "wav", b"x" * 100)

        paths = [tmp_path / k[:2] / f"{k}.wav" for k in keys]
        os.utime(paths[0], (1_000_000_000, 1_000_000_000))
        os.utime(paths[1], (2_000_000_000, 2_000_000_000))
        os.utime(paths[2], (3_000_000_000, 3_000_000_000))

        # Cap at 250 — still over by 50, so evict the oldest one (frees 100,
        # remainder 200 ≤ 250). Don't continue evicting bb.
        freed = evict_if_over_cap(tmp_path, cap_bytes=250)
        assert freed == 100
        assert not paths[0].exists()
        assert paths[1].exists()
        assert paths[2].exists()

    def test_evict_handles_missing_dir(self, tmp_path):
        assert evict_if_over_cap(tmp_path / "nope", cap_bytes=100) == 0


# ===================================================================
# cached_synthesize — engine-agnostic wrapper, fetch injection
# ===================================================================


def _async_value(value: bytes) -> AsyncMock:
    """AsyncMock that resolves to ``value`` when awaited."""
    fetch = AsyncMock()
    fetch.return_value = value
    return fetch


class TestCachedSynthesize:
    @pytest.mark.asyncio
    async def test_miss_calls_fetch_and_writes_bytes(self, tmp_path):
        fetch = _async_value(b"WAVbytes")
        result = await cached_synthesize(
            text="hello",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={"speed": 1.0},
            fetch=fetch,
            cache_dir=tmp_path,
        )
        assert result == b"WAVbytes"
        fetch.assert_awaited_once()
        # Must have written to the sharded layout.
        key = hash_key("hello", "af_heart", "kokoro", {"speed": 1.0})
        assert (tmp_path / key[:2] / f"{key}.wav").is_file()

    @pytest.mark.asyncio
    async def test_hit_skips_fetch_and_returns_cached(self, tmp_path):
        # Pre-populate.
        key = hash_key("hi", "af_heart", "kokoro", {"speed": 1.0})
        write_cached(tmp_path, key, "wav", b"cached!")
        fetch = AsyncMock()
        result = await cached_synthesize(
            text="hi",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={"speed": 1.0},
            fetch=fetch,
            cache_dir=tmp_path,
        )
        assert result == b"cached!"
        fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dict_order_consistent_lookup(self, tmp_path):
        """Pre-populate via {a, b}, look up via {b, a} — must hit."""
        key = hash_key("hi", "af_heart", "kokoro", {"pitch": 1.0, "speed": 1.0})
        write_cached(tmp_path, key, "wav", b"hit")
        fetch = AsyncMock()
        result = await cached_synthesize(
            text="hi",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={"speed": 1.0, "pitch": 1.0},  # different insertion order
            fetch=fetch,
            cache_dir=tmp_path,
        )
        assert result == b"hit"
        fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_fetch_result_not_cached(self, tmp_path):
        """If fetch returns b'' (empty synth), don't litter the cache."""
        fetch = _async_value(b"")
        result = await cached_synthesize(
            text="hi",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
        )
        assert result == b""
        # No files written.
        assert cache_size_bytes(tmp_path) == 0

    @pytest.mark.asyncio
    async def test_cacheable_false_skips_lookup_and_write(self, tmp_path):
        """``cacheable=False`` is the dynamic-content opt-out — fetch always
        runs, no read, no write. One-shot LLM responses fall here.
        """
        # Pre-populate to confirm the read path is bypassed.
        key = hash_key("hi", "af_heart", "kokoro", {})
        write_cached(tmp_path, key, "wav", b"would-hit")
        fetch = _async_value(b"fresh")
        result = await cached_synthesize(
            text="hi",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
            cacheable=False,
        )
        assert result == b"fresh"
        fetch.assert_awaited_once()
        # Pre-populated entry must still be there (we didn't write over it).
        assert read_cached(tmp_path, key, "wav") == b"would-hit"

    @pytest.mark.asyncio
    async def test_returns_data_even_when_write_fails(self, tmp_path, monkeypatch):
        """Disk-full / permissions / etc. don't fail the synth — just bypass cache."""

        def boom(*_args, **_kwargs):
            raise OSError("no space left on device")

        monkeypatch.setattr(Path, "mkdir", boom)
        fetch = _async_value(b"synth-bytes")
        result = await cached_synthesize(
            text="hi",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
        )
        assert result == b"synth-bytes"

    @pytest.mark.asyncio
    async def test_eviction_triggered_on_miss_write(self, tmp_path):
        """When a miss-write pushes total over cap, evict oldest. The just-
        written entry survives because its mtime ≈ now (newer than the
        pre-existing pool we set up below)."""
        import time

        # Pre-populate three 100-byte entries with staggered mtimes that
        # are all in the past relative to now (so the just-written "new"
        # entry will be the newest and survive eviction).
        keys = ["aa" + "0" * 62, "bb" + "1" * 62, "cc" + "2" * 62]
        for k in keys:
            write_cached(tmp_path, k, "wav", b"x" * 100)
        paths = [tmp_path / k[:2] / f"{k}.wav" for k in keys]
        now = time.time()
        os.utime(paths[0], (now - 30, now - 30))  # oldest
        os.utime(paths[1], (now - 20, now - 20))
        os.utime(paths[2], (now - 10, now - 10))  # newest pre-existing

        # New miss-write will push us to 400; cap at 200. Eviction order
        # oldest-first: aa, bb, cc, new(just-written) — stop after bb.
        fetch = _async_value(b"y" * 100)
        await cached_synthesize(
            text="new",
            voice_id="af_heart",
            model_id="kokoro",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
            size_cap_bytes=200,
        )

        # Oldest two must be gone (200-byte budget after miss-write).
        assert not paths[0].exists()
        assert not paths[1].exists()
        assert paths[2].exists()

    @pytest.mark.asyncio
    async def test_uses_custom_extension(self, tmp_path):
        """ElevenLabs uses mp3 / pcm output_formats; cache extension follows."""
        fetch = _async_value(b"mp3-bytes")
        await cached_synthesize(
            text="hi",
            voice_id="abc",
            model_id="eleven_v3",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
            extension="mp3",
        )
        key = hash_key("hi", "abc", "eleven_v3", {})
        assert (tmp_path / key[:2] / f"{key}.mp3").is_file()

    @pytest.mark.asyncio
    async def test_back_to_back_calls_use_cache(self, tmp_path):
        """First call misses + writes, second call sees the write and hits.

        This is the canonical hot-path assertion — once a synth request
        lands, subsequent identical calls return cached bytes without
        re-invoking the engine. Replaces a trickier concurrent-writers
        test that conflated AsyncMock's synchronous resolution with
        real async concurrency.
        """
        fetch = AsyncMock(side_effect=[b"A" * 100, b"B" * 100])
        first = await cached_synthesize(
            text="line",
            voice_id="v",
            model_id="m",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
        )
        second = await cached_synthesize(
            text="line",
            voice_id="v",
            model_id="m",
            voice_settings={},
            fetch=fetch,
            cache_dir=tmp_path,
        )
        assert first == b"A" * 100
        assert second == b"A" * 100  # cache hit from first call
        assert fetch.await_count == 1  # second call never reached fetch
