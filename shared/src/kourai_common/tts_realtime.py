"""RealtimeTTS-backed TTS engine — bundles Kokoro synth + PyAudio playback.

Replaces the pygame.mixer-based TTS path on the CLI and GUI hosts and the
hand-rolled KokoroBackend/EdgeTTSBackend path on the VN bridge. pygame.mixer's
documented inability to reliably resample 24 kHz mono → 44.1 kHz stereo
produced the "VHS rewind" chipmunk symptom; RealtimeTTS routes Kokoro's
native 24 kHz mono through PyAudio with no resample step in the path.

Two public surfaces:

- ``speak`` / ``speak_sync`` for CLI + GUI — synth + PyAudio playback bundled.
- ``synthesize_to_wav`` for ``agents/vn_bridge/`` — synth-only path that
  drives ``TextToAudioStream`` with ``muted=True`` and an ``on_audio_chunk``
  collector, then wraps the int16 PCM in one WAV header sized from
  ``KokoroEngine.get_stream_info()``.

The synthesis engine is selected at construction by ``KOURAI_TTS_ENGINE``
(``kokoro`` default; ``chatterbox`` opt-in for M6 expressive voice). Chatterbox
runs out-of-process in its own torch-2.6 service (``services/chatterbox``) and
is reached over HTTP via ``ChatterboxClient``; Kokoro is always the in-process
engine and the Chatterbox fallback. The seam ships dark: Kokoro stays the
default until each maiden's voice is auditioned + cast (ROADMAP M6 step 4).
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import warnings
import wave
from typing import TYPE_CHECKING

# Silence three torch warnings emitted while RealtimeTTS lazy-loads torch
# during the next import: two FutureWarnings (``weight_norm`` deprecation
# and ``LSTMCell.__init__`` argument-order shift in 2.x), plus the
# ``LSTM dropout=0.2 with num_layers=1`` UserWarning that Kokoro's
# packaged model triggers. All three are upstream concerns and the
# library still ships pinned to the older API. Filtering here (before
# the RealtimeTTS import that triggers the torch chain) keeps interactive
# CLI/GUI boot output legible — without it the user sees a noisy stderr
# burst on every startup. Scoped to ``module=torch\..*`` so genuine
# warnings from our own code are still audible.
warnings.filterwarnings("ignore", category=FutureWarning, module=r"torch\..*")
warnings.filterwarnings("ignore", category=UserWarning, module=r"torch\.nn\.modules\.rnn")

# Module-level bindings (aliased with leading underscore) so tests can
# monkeypatch them without instantiating PyAudio. RealtimeTTS is a hard
# dep in hosts/gui/pyproject.toml; importing it pulls in pyaudio, which
# requires portaudio19-dev on Linux (CI installs it via ed4d560).
# E402 is intentional — the warnings.filterwarnings call above must run
# before the RealtimeTTS import that triggers torch's lazy load.
import numpy as np  # noqa: E402
import pyaudio  # noqa: E402
from RealtimeTTS import (  # noqa: E402
    KokoroEngine as _KokoroEngine,
    TextToAudioStream as _TextToAudioStream,
)

from kourai_common.audio_env import (  # noqa: E402
    is_audio_output_available,
    silence_alsa_lib_errors,
    silence_audio_init_noise,
)
from kourai_common.chatterbox_client import ChatterboxClient, ChatterboxUnavailable  # noqa: E402
from kourai_common.ssml import strip_ssml  # noqa: E402
from kourai_common.tts_backend import (  # noqa: E402
    AGENT_VOICE_MAP,
    TTSVoiceConfig,
    get_expression_for_agent,
    get_voice_for_agent,
    get_voice_ref_for_agent,
)
from kourai_common.tts_cache import cached_synthesize  # noqa: E402

# Module-load side effect: kill libasound's stderr cascade before
# `_TextToAudioStream(...)` enumerates ALSA in `__init__` below.
silence_alsa_lib_errors()

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

# Re-exports for parity with hosts.gui.tts_engine
VoiceConfig = TTSVoiceConfig
VOICE_ROSTER = {v.voice_id: v for v in AGENT_VOICE_MAP.values()}
AGENT_VOICES = {agent: cfg.voice_id for agent, cfg in AGENT_VOICE_MAP.items()}


class _DropPhonemizerWordsCountMismatch(logging.Filter):
    """Surgical filter for the 'words count mismatch' espeak spam.

    phonemizer's espeak backend logs ``words count mismatch on N% of the
    lines (X/Y)`` at WARNING from ``_resume()`` after every batch, even
    when ``words_mismatch='ignore'`` is set (which is the default).
    Upstream confirms it's benign — espeak occasionally joins or drops a
    word and the audio is still correct. Filtering only this message
    pattern keeps any other phonemizer warnings audible.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "words count mismatch" not in record.getMessage()


_phonemizer_filter_installed = False


def _install_phonemizer_word_count_filter() -> None:
    """Idempotently attach the words-count-mismatch filter to phonemizer's logger."""
    global _phonemizer_filter_installed
    if _phonemizer_filter_installed:
        return
    logging.getLogger("phonemizer").addFilter(_DropPhonemizerWordsCountMismatch())
    _phonemizer_filter_installed = True


def _pcm_to_wav(pcm: bytes, *, channels: int, sample_rate: int, sample_width: int) -> bytes:
    """Wrap raw signed PCM bytes in a canonical WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


_DEFAULT_TTS_ENGINE = "kokoro"
_SUPPORTED_TTS_ENGINES = frozenset({"kokoro", "chatterbox"})


def _resolve_engine_name() -> str:
    """Read ``KOURAI_TTS_ENGINE`` (default ``kokoro``). Unknown values fall
    back to ``kokoro`` with a warning so a typo never strands a host silent.
    """
    raw = os.environ.get("KOURAI_TTS_ENGINE", _DEFAULT_TTS_ENGINE).strip().lower()
    if raw not in _SUPPORTED_TTS_ENGINES:
        logger.warning(
            "Unknown KOURAI_TTS_ENGINE=%r; falling back to %s. Supported: %s",
            raw,
            _DEFAULT_TTS_ENGINE,
            ", ".join(sorted(_SUPPORTED_TTS_ENGINES)),
        )
        return _DEFAULT_TTS_ENGINE
    return raw


class RealtimeTTSEngine:
    """TTS engine wrapping RealtimeTTS's KokoroEngine + TextToAudioStream.

    PyAudio-backed playback at native 24 kHz mono — no pygame mixer in
    the path, so the resample "VHS rewind" failure mode is gone by
    construction. Mirrors ``TTSEngine``'s ABI for drop-in replacement.
    """

    def __init__(
        self,
        master_volume: float = 0.8,
        enable_effects: bool = True,
        muted: bool | None = None,
        on_word: Callable[[object], None] | None = None,
        cache_dir: Path | None = None,
    ):
        # research(2026-05): muted=None means auto-detect via PortAudio's
        # paNoDevice signal — degrades to silent text-only on Docker
        # without /dev/snd, WSL2 without WSLg, headless servers, CI.
        # Explicit muted=True/False overrides (vn_bridge passes True;
        # tests can pin False to assert playback paths).
        if muted is None:
            muted = not is_audio_output_available()
            if muted:
                logger.warning(
                    "TTS auto-muted: no audio output device detected. "
                    "Set KOURAI_TTS=off to silence; enable WSLg (WSL2), "
                    "pass --device /dev/snd (Docker), or install audio "
                    "drivers to play voice."
                )
        # Install before engine init so misaki's first phonemize() call
        # (which can happen during KokoroEngine warmup) is already filtered.
        _install_phonemizer_word_count_filter()
        self._muted = muted
        self._engine_name = _resolve_engine_name()
        # Kokoro is always the in-process engine: the default synth path AND the
        # fallback when Chatterbox is selected but its service is unreachable.
        self._engine = self._build_engine()
        # Chatterbox (M6) runs out-of-process; the client is created only when
        # selected. None for Kokoro-only installs (CI / WSL default).
        self._chatterbox_client = ChatterboxClient() if self._engine_name == "chatterbox" else None
        # M20 sub-task 2: per-call audio-start (Tier 2) + on_word (Tier 1)
        # callbacks dispatched via stable trampolines. RealtimeTTS only
        # accepts these handlers at TextToAudioStream construction; each
        # trampoline reads its `_*_current` slot (mutated by `speak()`
        # per call) so each utterance can attach its own display
        # callbacks without rebuilding the stream. The constructor-time
        # `on_word=` argument (engine-wide static handler) layers under
        # the per-call trampoline — both fire if both are set.
        self._on_audio_start_current: Callable[[], None] | None = None
        self._on_word_current: Callable[[object], None] | None = None
        self._on_word_static: Callable[[object], None] | None = on_word
        # PyAudio probes JACK after ALSA inside `_TextToAudioStream`;
        # wrap only that call so torch / HF Hub warnings stay visible.
        with silence_audio_init_noise():
            self._stream = _TextToAudioStream(
                engine=self._engine,
                on_word=self._dispatch_on_word,
                on_audio_stream_start=self._dispatch_audio_start,
                muted=muted,
                level=logging.WARNING,
            )

        self.master_volume = max(0.0, min(1.0, master_volume))
        self.enable_effects = enable_effects
        self.is_playing = False
        self._on_complete: Callable[[], None] | None = None
        # Opt-in TTS cache for synthesize_to_wav. None = uncached (default
        # so existing tests stay green); vn_bridge passes
        # tts_cache.default_cache_dir() at construction. M6 sub-task 2.
        self._cache_dir = cache_dir

        self._stream.set_volume(self._effective_volume())

        # Eat the Kokoro cold-start window upfront: pipelines per language
        # (#23), then voice tensors per agent (M20 sub-task 1). Kokoro-only —
        # Chatterbox has no KPipeline; its warmup is an M6 step-2 concern.
        if self._engine_name == "kokoro":
            self._prewarm_agent_languages()
            self._prewarm_agent_voices()

        logger.info(
            "RealtimeTTSEngine initialized: engine=%s, volume=%s, effects=%s",
            self._engine_name,
            self.master_volume,
            self.enable_effects,
        )

    def _build_engine(self):
        """Construct the underlying RealtimeTTS engine — always ``KokoroEngine``.

        Kokoro backs both the default path and the Chatterbox fallback; the
        expressive engine runs out-of-process (see ``_chatterbox_client``).
        """
        return _KokoroEngine(voice="af_heart", default_speed=1.0, debug=False)

    def _apply_voice(self, voice_cfg: TTSVoiceConfig, effective_speed: float) -> None:
        """Push the resolved Kokoro voice + speed onto the engine.

        Chatterbox doesn't route through here — its per-maiden expression
        (exaggeration / cfg_weight) is sent per-request to the out-of-process
        service (see ``_chatterbox_client_synth``).
        """
        self._engine.set_voice(voice_cfg.voice_id)
        self._engine.set_speed(effective_speed)

    async def _chatterbox_client_synth(self, text: str, agent_name: str | None) -> bytes:
        """Synthesize one line via the out-of-process Chatterbox service.

        Sends the maiden's expression (``AGENT_EXPRESSION_MAP``) + her reference
        clip (``AGENT_VOICE_REF_MAP``, empty until the audition → built-in voice).
        Raises :class:`ChatterboxUnavailable` so callers can fall back to Kokoro.
        """
        client = self._chatterbox_client
        if client is None:  # defensive: only reached in chatterbox mode
            raise ChatterboxUnavailable("Chatterbox client not initialized")
        expr = get_expression_for_agent(agent_name)
        return await client.synthesize(
            text,
            voice_ref=get_voice_ref_for_agent(agent_name),
            exaggeration=expr.exaggeration,
            cfg_weight=expr.cfg_weight,
        )

    async def _try_speak_chatterbox(self, text: str, agent_name: str | None) -> bool:
        """Synthesize via Chatterbox and play the WAV. Returns ``False`` (caller
        falls back to the Kokoro stream) when the service is unavailable.

        Chatterbox has no word timing, so only the Tier-2 ``on_audio_start``
        callback fires (as playback begins); ``on_word`` (Tier-1 karaoke reveal)
        stays Kokoro-only.
        """
        try:
            wav = await self._chatterbox_client_synth(text, agent_name)
        except ChatterboxUnavailable as exc:
            logger.warning("Chatterbox unavailable; Kokoro fallback for speak (%s)", exc)
            return False
        self.is_playing = True
        self._dispatch_audio_start()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._play_wav_bytes(wav))
        return True

    def _play_wav_bytes(self, wav_bytes: bytes) -> None:
        """Play WAV bytes through PyAudio at the engine's effective volume.

        Used for Chatterbox output (a complete WAV from the service), which
        doesn't flow through RealtimeTTS's text-fed stream. No-op when muted.
        """
        if self._muted:
            return
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            width = wf.getsampwidth()
            channels = wf.getnchannels()
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        vol = self._effective_volume()
        if vol < 1.0 and width == 2:
            scaled = np.frombuffer(frames, dtype=np.int16).astype(np.float32) * vol
            frames = np.clip(scaled, -32768, 32767).astype(np.int16).tobytes()
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=pa.get_format_from_width(width),
                channels=channels,
                rate=rate,
                output=True,
            )
            try:
                stream.write(frames)
            finally:
                stream.stop_stream()
                stream.close()
        finally:
            pa.terminate()

    def _prewarm_agent_languages(self) -> None:
        """Build a KPipeline for every unique ``AGENT_VOICE_MAP`` lang_code.

        Failures are non-fatal — the lazy path still works if pre-warm misses.
        """
        t_start = time.monotonic()
        seen: set[str] = set()
        loaded: list[str] = []
        for cfg in AGENT_VOICE_MAP.values():
            lang_code = getattr(cfg, "lang_code", "a")
            if lang_code in seen:
                continue
            seen.add(lang_code)
            try:
                self._engine._get_pipeline(lang_code)
                loaded.append(lang_code)
            except Exception as exc:
                logger.debug(
                    "Kokoro pre-warm skipped for lang_code=%s (%s: %s)",
                    lang_code,
                    type(exc).__name__,
                    exc,
                )
        logger.info(
            "Kokoro language pre-warm: %d/%d langs (%s) elapsed=%.2fs",
            len(loaded),
            len(seen),
            ",".join(sorted(loaded)) or "none",
            time.monotonic() - t_start,
        )

    def _prewarm_agent_voices(self) -> None:
        """Materialize each agent's voice tensor (.pt) into KPipeline's voice cache.

        Failures are non-fatal — single-voice failure falls back to the lazy path.
        """
        t_start = time.monotonic()
        loaded: list[str] = []
        for cfg in AGENT_VOICE_MAP.values():
            lang_code = getattr(cfg, "lang_code", "a")
            try:
                pipeline = self._engine._get_pipeline(lang_code)
                pipeline.load_single_voice(cfg.voice_id)
                loaded.append(cfg.voice_id)
            except Exception as exc:
                logger.debug(
                    "Kokoro voice pre-warm skipped for voice=%s lang=%s (%s: %s)",
                    cfg.voice_id,
                    lang_code,
                    type(exc).__name__,
                    exc,
                )
        logger.info(
            "Kokoro voice pre-warm: %d/%d voices elapsed=%.2fs",
            len(loaded),
            len(AGENT_VOICE_MAP),
            time.monotonic() - t_start,
        )

    def _effective_volume(self) -> float:
        return self.master_volume * (0.85 if self.enable_effects else 1.0)

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        self._stream.set_volume(self._effective_volume())
        logger.debug("Master volume set to %s", self.master_volume)

    def set_on_complete(self, callback: Callable[[], None]) -> None:
        """Set callback to fire when playback completes."""
        self._on_complete = callback

    def _dispatch_audio_start(self) -> None:
        """Trampoline for the per-call ``on_audio_start`` callback that
        :meth:`speak` attaches. Stable callback wired into RealtimeTTS at
        construction; per-utterance handler comes from
        ``_on_audio_start_current``.
        """
        cb = self._on_audio_start_current
        if cb is None:
            return
        try:
            cb()
        except Exception as e:
            logger.warning("on_audio_start callback raised (%s: %s)", type(e).__name__, e)

    def _dispatch_on_word(self, word: object) -> None:
        """Trampoline for ``on_word`` — fires both the static (constructor)
        handler and the per-call (speak) handler if either is set. Per-call
        handler is mutated by :meth:`speak` and cleared in finally.

        ``word`` is a ``RealtimeTTS.engines.base_engine.TimingInfo`` instance
        with at least a ``.word`` attribute (string). Per the RealtimeTTS
        docs, fires AT PLAYBACK TIME for English voices of ``KokoroEngine``
        — the karaoke-reveal primitive for Tier 1.
        """
        for cb in (self._on_word_static, self._on_word_current):
            if cb is None:
                continue
            try:
                cb(word)
            except Exception as e:
                logger.warning("on_word callback raised (%s: %s)", type(e).__name__, e)

    async def speak(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
        on_audio_start: Callable[[], None] | None = None,
        on_word: Callable[[object], None] | None = None,
    ) -> None:
        """Generate and play speech asynchronously.

        ``pitch`` is accepted for ABI parity with ``TTSEngine.speak`` but
        ignored — KokoroEngine has no pitch control (the legacy
        ``KokoroBackend`` also dropped it for the same reason).

        ``on_audio_start`` (M20 sub-task 2 Tier 2) fires once playback
        begins, after synthesis has produced a playable chunk. Used by
        the CLI / GUI / VN to defer text rendering until the audio is
        actually about to be heard, eliminating the "text precedes
        audio" disconnect on slow synthesis.

        ``on_word`` (M20 sub-task 2 Tier 1) fires once per word AT
        PLAYBACK TIME with a ``TimingInfo`` object (``.word``,
        ``.start_time``, ``.end_time``). Supported on English voices of
        ``KokoroEngine``. Used by the CLI for karaoke-style word-by-word
        reveal in lockstep with audio. Stacks under any constructor-
        time ``on_word`` (both fire if both set).

        Both per-call handlers save/restore around the await so nested
        ``speak()`` calls stay safe even though current code paths only
        call sequentially.
        """
        if not text.strip():
            logger.debug("Empty text, skipping TTS")
            return

        # Defensive strip — guards against future LLM output that wraps
        # text in `<speak>` or other XML-shaped markup (Kokoro would
        # phonemize the angle brackets literally). See
        # kourai_common.ssml docstring for the walked-back M18 Phase 2
        # SSML producer plan and why this stays defensive-only.
        text = strip_ssml(text)
        if not text.strip():
            logger.debug("Stripped to empty, skipping TTS")
            return

        # Resolve voice
        if voice_key is not None:
            voice_cfg = VOICE_ROSTER.get(voice_key, get_voice_for_agent(None))
        else:
            voice_cfg = get_voice_for_agent(agent_name)

        effective_speed = speed if speed is not None else voice_cfg.speed

        prior_on_audio_start = self._on_audio_start_current
        prior_on_word = self._on_word_current
        if on_audio_start is not None:
            self._on_audio_start_current = on_audio_start
        if on_word is not None:
            self._on_word_current = on_word

        t_start = time.monotonic()
        try:
            # Chatterbox: synth out-of-process + play the WAV (Tier-2
            # on_audio_start only). Returns False → fall through to Kokoro.
            if self._engine_name == "chatterbox" and await self._try_speak_chatterbox(
                text, agent_name
            ):
                return

            logger.info(
                "TTS: starting RealtimeTTS speech — agent=%s, voice=%s, speed=%.2f, text=%r",
                agent_name,
                voice_cfg.voice_id,
                effective_speed,
                text,
            )

            self._apply_voice(voice_cfg, effective_speed)

            self.is_playing = True
            self._stream.feed(text)

            # Bridge RealtimeTTS's blocking play() into the async loop.
            # play() runs synthesis + playback to completion on a worker
            # thread, returning when the audio stream stops.
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._stream.play)

            logger.info(
                "TTS: playback complete agent=%s voice=%s elapsed=%.2fs chars=%d",
                agent_name,
                voice_cfg.voice_id,
                time.monotonic() - t_start,
                len(text),
            )
        except (Exception, SystemExit) as e:
            # research(2026-05): SystemExit (not Exception) bubbles from
            # RealtimeTTS's stream_player.open_stream when an audio device
            # disappears mid-session or PortAudio reports a phantom NULL
            # default sink. Auto-mute at construction normally prevents
            # this; widening the catch keeps the CLI alive on edge cases
            # the init probe can't see.
            logger.warning("TTS playback skipped (%s: %s)", type(e).__name__, e)
            logger.debug("TTS playback error detail", exc_info=True)
        finally:
            self.is_playing = False
            self._on_audio_start_current = prior_on_audio_start
            self._on_word_current = prior_on_word
            if self._on_complete:
                self._on_complete()

    def speak_sync(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
        on_audio_start: Callable[[], None] | None = None,
        on_word: Callable[[object], None] | None = None,
    ) -> None:
        """Synchronous wrapper for speak (blocks until complete).

        ``on_audio_start`` and ``on_word`` forward to :meth:`speak` for
        the GUI host's pygame typewriter — same M20 sub-task 2 plumbing
        as the CLI, just dispatched from a daemon thread instead of
        the asyncio event loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.speak(
                    text,
                    agent_name=agent_name,
                    voice_key=voice_key,
                    speed=speed,
                    pitch=pitch,
                    on_audio_start=on_audio_start,
                    on_word=on_word,
                )
            )
        finally:
            loop.close()

    async def synthesize_to_wav(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
    ) -> bytes:
        """Generate speech as a self-contained WAV without playback.

        Drives ``TextToAudioStream`` with ``muted=True`` and an
        ``on_audio_chunk`` collector, then wraps the int16 PCM in one
        WAV header sized from ``KokoroEngine.get_stream_info()``. Used by
        ``agents/vn_bridge/`` which feeds WAV bytes into Ren'Py's audio
        system rather than playing them itself.

        For headless callers (no audio device — Docker, CI, server
        deployments), construct the engine with ``muted=True`` so the
        underlying StreamPlayer skips ``open_stream()`` entirely. The
        runtime ``muted=True`` here only stops audio frame writes; it
        does not prevent the device-open probe inside RealtimeTTS.

        When the engine was constructed with ``cache_dir=...`` (M6
        sub-task 2), identical (text, voice_id, speed) requests return
        cached WAV bytes from disk without re-invoking Kokoro. Empty
        synth results are not cached.
        """
        if not text.strip():
            return b""

        # Defensive strip mirrors speak() — same defense-in-depth boundary
        # against future LLM-emitted markup. See kourai_common.ssml docstring.
        text = strip_ssml(text)
        if not text.strip():
            return b""

        # Voice resolution mirrors speak() so vn_bridge and the CLI/GUI
        # hosts dispatch through the same precedence rules.
        if voice_key is not None:
            voice_cfg = VOICE_ROSTER.get(voice_key, get_voice_for_agent(None))
        else:
            voice_cfg = get_voice_for_agent(agent_name)
        effective_speed = speed if speed is not None else voice_cfg.speed

        # Chatterbox (M6): synth out-of-process. On service failure fall through
        # to Kokoro — cached_synthesize writes only after a successful fetch, so
        # the fallback is never cached under a Chatterbox key.
        if self._engine_name == "chatterbox":
            try:
                return await self._chatterbox_synthesize_to_wav(text, agent_name)
            except ChatterboxUnavailable as exc:
                logger.warning("Chatterbox unavailable; Kokoro fallback for synth (%s)", exc)

        return await self._kokoro_synthesize_to_wav_cached(
            text, voice_cfg, effective_speed, agent_name
        )

    async def _chatterbox_synthesize_to_wav(self, text: str, agent_name: str | None) -> bytes:
        """Cached Chatterbox synth (M6). Cache key = chatterbox model + the
        maiden's voice_ref + expression, so it never collides with Kokoro's.
        Raises :class:`ChatterboxUnavailable` (caller falls back to Kokoro).
        """
        if self._cache_dir is None:
            return await self._chatterbox_client_synth(text, agent_name)
        expr = get_expression_for_agent(agent_name)
        voice_ref = get_voice_ref_for_agent(agent_name)
        return await cached_synthesize(
            text=text,
            voice_id=voice_ref or "_builtin",
            model_id="chatterbox",
            voice_settings={"exaggeration": expr.exaggeration, "cfg_weight": expr.cfg_weight},
            fetch=lambda: self._chatterbox_client_synth(text, agent_name),
            cache_dir=self._cache_dir,
            extension="wav",
        )

    async def _kokoro_synthesize_to_wav_cached(
        self,
        text: str,
        voice_cfg: TTSVoiceConfig,
        effective_speed: float,
        agent_name: str | None,
    ) -> bytes:
        """Kokoro synth with the optional disk cache — the default + fallback path."""
        if self._cache_dir is None:
            return await self._kokoro_synthesize_to_wav(
                text, voice_cfg, effective_speed, agent_name
            )
        # voice_settings keyed on the surface that actually shapes Kokoro
        # output. lang_code is locked per voice_id, so it's redundant in the hash.
        return await cached_synthesize(
            text=text,
            voice_id=voice_cfg.voice_id,
            model_id="kokoro",
            voice_settings={
                "speed": effective_speed,
                "pitch": voice_cfg.pitch,
            },
            fetch=lambda: self._kokoro_synthesize_to_wav(
                text, voice_cfg, effective_speed, agent_name
            ),
            cache_dir=self._cache_dir,
            extension="wav",
        )

    async def _kokoro_synthesize_to_wav(
        self,
        text: str,
        voice_cfg: TTSVoiceConfig,
        effective_speed: float,
        agent_name: str | None,
    ) -> bytes:
        """The pre-cache body of synthesize_to_wav — drives KokoroEngine
        directly. Split out so :func:`cached_synthesize` can wrap it as
        the cache-miss fetch.
        """
        chunks: list[bytes] = []
        t_start = time.monotonic()

        self._apply_voice(voice_cfg, effective_speed)
        self._stream.feed(text)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._stream.play(muted=True, on_audio_chunk=chunks.append),
        )

        synth_elapsed = time.monotonic() - t_start

        if not chunks:
            logger.info(
                "TTS: synthesize_to_wav produced no audio agent=%s voice=%s elapsed=%.2fs",
                agent_name,
                voice_cfg.voice_id,
                synth_elapsed,
            )
            return b""

        fmt, channels, sample_rate = self._engine.get_stream_info()
        wav = _pcm_to_wav(
            b"".join(chunks),
            channels=channels,
            sample_rate=sample_rate,
            sample_width=pyaudio.get_sample_size(fmt),
        )
        logger.info(
            "TTS: synthesize_to_wav agent=%s voice=%s elapsed=%.2fs chars=%d bytes=%d",
            agent_name,
            voice_cfg.voice_id,
            synth_elapsed,
            len(text),
            len(wav),
        )
        return wav

    def stop(self) -> None:
        """Stop current playback gracefully."""
        try:
            self._stream.stop()
        except Exception as e:
            logger.debug("RealtimeTTS stop ignored (%s: %s)", type(e).__name__, e)
        self.is_playing = False

    def cleanup(self) -> None:
        """Stop playback and shut the KokoroEngine down."""
        self.stop()
        try:
            self._engine.shutdown()
        except Exception as e:
            logger.debug("KokoroEngine shutdown ignored (%s: %s)", type(e).__name__, e)
        logger.debug("RealtimeTTSEngine cleanup complete")
