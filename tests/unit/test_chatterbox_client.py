"""Hermetic tests for ChatterboxClient — httpx.MockTransport, no live service."""

from __future__ import annotations

import json

import httpx
import pytest

from kourai_common.chatterbox_client import ChatterboxClient, ChatterboxUnavailable


def _client_with(handler) -> ChatterboxClient:
    return ChatterboxClient(base_url="http://svc:9999", transport=httpx.MockTransport(handler))


async def test_synthesize_returns_wav_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"RIFFfakewav", headers={"content-type": "audio/wav"})

    out = await _client_with(handler).synthesize("hello")
    assert out == b"RIFFfakewav"


async def test_synthesize_sends_expected_payload_without_voice_ref():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["path"] = request.url.path
        return httpx.Response(200, content=b"x")

    await _client_with(handler).synthesize("the forge is ready", exaggeration=0.7, cfg_weight=0.4)
    assert seen["path"] == "/synthesize"
    assert seen["text"] == "the forge is ready"
    assert seen["exaggeration"] == 0.7
    assert seen["cfg_weight"] == 0.4
    assert "voice_ref" not in seen  # omitted when None -> service uses built-in voice


async def test_synthesize_includes_voice_ref_when_given():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, content=b"x")

    await _client_with(handler).synthesize("hi", voice_ref="/refs/metis.wav")
    assert seen["voice_ref"] == "/refs/metis.wav"


async def test_synthesize_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"boom")

    with pytest.raises(ChatterboxUnavailable):
        await _client_with(handler).synthesize("hi")


async def test_synthesize_raises_on_connect_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ChatterboxUnavailable):
        await _client_with(handler).synthesize("hi")


async def test_health_true_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    assert await _client_with(handler).health() is True


async def test_health_false_on_503_loading():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "loading"})

    assert await _client_with(handler).health() is False


async def test_health_false_on_connect_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("service down")

    assert await _client_with(handler).health() is False


def test_base_url_from_env_and_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("KOURAI_CHATTERBOX_URL", "http://host:1234/")
    assert ChatterboxClient().base_url == "http://host:1234"


def test_explicit_base_url_overrides_env(monkeypatch):
    monkeypatch.setenv("KOURAI_CHATTERBOX_URL", "http://env:1/")
    assert ChatterboxClient(base_url="http://explicit:2").base_url == "http://explicit:2"
