"""Unit tests for agents.vn_bridge.__main__ helpers.

Currently focused on the M20 sub-task 2 ``_wav_duration_seconds`` parser
that powers the X-TTS-Duration-Seconds response header. The full
handle_tts endpoint needs the live RealtimeTTSEngine + Starlette
integration; that's covered indirectly by the live VN smoke (see
ROADMAP M20).
"""

from __future__ import annotations

import io
import wave

from agents.vn_bridge.__main__ import _wav_duration_seconds


def _make_wav(*, frames: int, framerate: int, channels: int = 1, sampwidth: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class TestWavDurationSeconds:
    def test_parses_simple_duration(self) -> None:
        # 24000 frames @ 24000 Hz = exactly 1.0s (matches Kokoro's default).
        wav = _make_wav(frames=24000, framerate=24000)
        assert _wav_duration_seconds(wav) == 1.0

    def test_parses_fractional_duration(self) -> None:
        # 12000 frames @ 24000 Hz = 0.5s
        wav = _make_wav(frames=12000, framerate=24000)
        assert _wav_duration_seconds(wav) == 0.5

    def test_returns_none_on_empty_bytes(self) -> None:
        assert _wav_duration_seconds(b"") is None

    def test_returns_none_on_garbage_bytes(self) -> None:
        assert _wav_duration_seconds(b"\x00\x01\x02not a wav") is None

    def test_returns_none_on_truncated_wav(self) -> None:
        # First 12 bytes of a real WAV — missing fmt + data chunks.
        wav = _make_wav(frames=100, framerate=24000)[:12]
        assert _wav_duration_seconds(wav) is None

    def test_handles_typical_kokoro_output(self) -> None:
        # Mimics ~3s of Kokoro 24kHz mono int16 — roughly the steady-state
        # synthesis size for a 50-char dialogue per the 2026-05-03 measurement.
        wav = _make_wav(frames=72000, framerate=24000)
        duration = _wav_duration_seconds(wav)
        assert duration is not None
        assert 2.99 < duration < 3.01
