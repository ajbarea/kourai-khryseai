"""Unit tests for ``kourai_common.elicitation`` — the MCP elicitation
client capability + INPUT_REQUIRED bridge.

Tests cover four concerns:

- **Marker codec** — ``format_outbound_marker`` /
  ``parse_outbound_marker`` / ``parse_inbound_marker`` round-trip
  cleanly and reject malformed input.
- **Registry** — ``_register`` / ``_unregister`` /
  ``resolve_elicitation`` move Futures through the lifecycle
  correctly, including the cross-task resolution path that's the
  whole point of the module-level dict.
- **Callback** — ``_kourai_elicitation_callback`` returns the right
  shape (``ElicitResult`` / ``ErrorData``) for each input shape
  (form/URL/schema/missing-emitter) and respects the timeout.
- **Concurrency** — two pending elicitations don't trample each
  other's Futures.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

import pytest
from mcp.types import (
    ElicitRequestFormParams,
    ElicitRequestURLParams,
    ElicitResult,
    ErrorData,
)

from kourai_common.elicitation import (
    _PENDING_ELICITATIONS,
    ELICITATION_TIMEOUT,
    _kourai_elicitation_callback,
    _register,
    _unregister,
    format_outbound_marker,
    kourai_elicitation_emitter_var,
    kourai_elicitation_specialist_var,
    parse_inbound_marker,
    parse_outbound_marker,
    pending_count,
    resolve_elicitation,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture(autouse=True)
async def _clean_registry() -> AsyncIterator[None]:
    """Wipe the module-level registry before AND after each test.

    Module-level state survives across tests in the same process —
    without this fixture, a prior test's leftover Future shows up as
    "stale" warnings in subsequent ``resolve_elicitation`` calls and
    the ``pending_count`` assertions become non-deterministic.
    """
    _PENDING_ELICITATIONS.clear()
    yield
    _PENDING_ELICITATIONS.clear()


# ── Marker codec ────────────────────────────────────────────────────────────


class TestOutboundMarker:
    def test_format_round_trips_through_parse(self):
        marker = format_outbound_marker("abc123", "techne", "confirm delete?")
        decoded = parse_outbound_marker(marker)
        assert decoded == ("abc123", "techne", "confirm delete?")

    def test_message_with_brackets_round_trips(self):
        # Message body shouldn't be parsed for nested brackets — the
        # ``] `` partition only consumes the first occurrence.
        marker = format_outbound_marker("xyz", "kallos", "confirm [destructive] op?")
        decoded = parse_outbound_marker(marker)
        assert decoded == ("xyz", "kallos", "confirm [destructive] op?")

    def test_parse_rejects_non_marker(self):
        assert parse_outbound_marker("plain status update") is None

    def test_parse_rejects_marker_without_separator(self):
        # Missing the ``] `` separator — could be a partial render.
        assert parse_outbound_marker("[ELICIT:id:specialist no-bracket-close") is None

    def test_parse_rejects_marker_without_specialist(self):
        # Header has no ``:`` separating id and specialist.
        assert parse_outbound_marker("[ELICIT:idonly] message") is None


class TestInboundMarker:
    def test_parses_bare_marker(self):
        decoded = parse_inbound_marker("[elicit_answer:abc123:accept]")
        assert decoded == ("abc123", "accept")

    def test_parses_marker_with_trailing_text(self):
        # Player's response may include free-text after the tag.
        decoded = parse_inbound_marker("[elicit_answer:abc123:decline] no thanks")
        assert decoded == ("abc123", "decline")

    def test_parses_marker_embedded_in_message(self):
        # CLI may prepend forge tags before the answer.
        decoded = parse_inbound_marker("[project_root: /tmp/x] [elicit_answer:xyz:cancel]")
        assert decoded == ("xyz", "cancel")

    def test_rejects_unknown_action(self):
        assert parse_inbound_marker("[elicit_answer:abc:approve]") is None

    def test_rejects_message_without_tag(self):
        assert parse_inbound_marker("just a regular reply") is None

    def test_rejects_unclosed_marker(self):
        assert parse_inbound_marker("[elicit_answer:abc:accept no-close") is None


# ── Registry lifecycle ───────────────────────────────────────────────────────


class TestRegistry:
    @pytest.mark.asyncio
    async def test_register_creates_pending_future(self):
        fut = await _register("test-id-1")
        assert "test-id-1" in _PENDING_ELICITATIONS
        assert not fut.done()
        assert pending_count() == 1

    @pytest.mark.asyncio
    async def test_register_rejects_id_collision(self):
        await _register("dup-id")
        with pytest.raises(RuntimeError, match="elicitation id collision"):
            await _register("dup-id")

    @pytest.mark.asyncio
    async def test_unregister_removes_entry(self):
        await _register("test-id-2")
        assert pending_count() == 1
        await _unregister("test-id-2")
        assert pending_count() == 0

    @pytest.mark.asyncio
    async def test_unregister_unknown_id_is_idempotent(self):
        # Cleanup paths shouldn't raise when the registry is already empty.
        await _unregister("never-registered")  # no exception

    @pytest.mark.asyncio
    async def test_resolve_returns_false_for_unknown_id(self):
        result = await resolve_elicitation("never-registered", "accept", None)
        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_sets_future_with_action_and_content(self):
        fut = await _register("resolve-test")
        result = await resolve_elicitation("resolve-test", "accept", {"answer": "yes"})
        assert result is True
        assert fut.done()
        action, content = fut.result()
        assert action == "accept"
        assert content == {"answer": "yes"}

    @pytest.mark.asyncio
    async def test_resolve_returns_false_for_already_resolved(self):
        fut = await _register("double-resolve")
        await resolve_elicitation("double-resolve", "accept", None)
        # Second resolve attempt should fail gracefully — the Future
        # is already set, can't be set again.
        assert fut.done()
        second = await resolve_elicitation("double-resolve", "decline", None)
        assert second is False
        # Original answer is preserved.
        action, _ = fut.result()
        assert action == "accept"

    @pytest.mark.asyncio
    async def test_cross_task_resolution(self):
        """The whole point of the module-level registry: one task awaits,
        a different task resolves. Mirrors the
        blocked-execute()/fresh-execute() pattern in production.
        """
        fut = await _register("cross-task")

        async def resolver():
            await asyncio.sleep(0.01)
            await resolve_elicitation("cross-task", "accept", None)

        resolver_task = asyncio.create_task(resolver())
        action, _ = await asyncio.wait_for(fut, timeout=1.0)
        await resolver_task
        assert action == "accept"


# ── Callback paths ───────────────────────────────────────────────────────────


class TestCallback:
    @pytest.mark.asyncio
    async def test_returns_error_when_emitter_unset(self):
        # Default contextvar value is None — out-of-tree callers (or
        # tests not exercising the executor) hit this path.
        params = ElicitRequestFormParams(message="confirm?", requestedSchema={})
        result = await _kourai_elicitation_callback(context=cast("Any", None), params=params)
        assert isinstance(result, ErrorData)
        assert "kourai_elicitation_emitter_var" in result.message

    @pytest.mark.asyncio
    async def test_url_mode_declines(self):
        # URL mode is for OAuth / payment / out-of-band — the CLI
        # bridge can't render those in the MVP, decline cleanly.
        params = ElicitRequestURLParams(
            message="auth?",
            url="https://example.com/oauth",
            elicitationId="url-eid",
        )
        result = await _kourai_elicitation_callback(context=cast("Any", None), params=params)
        assert isinstance(result, ElicitResult)
        assert result.action == "decline"

    @pytest.mark.asyncio
    async def test_form_with_schema_returns_error(self):
        # Structured form schemas need richer rendering; reject for now
        # so the calling tool can either retry without schema or fail
        # with a clear reason.
        params = ElicitRequestFormParams(
            message="enter details",
            requestedSchema={"properties": {"name": {"type": "string"}}},  # type: ignore[arg-type]
        )
        emitter = AsyncMock()
        token = kourai_elicitation_emitter_var.set(emitter)
        try:
            result = await _kourai_elicitation_callback(context=cast("Any", None), params=params)
        finally:
            kourai_elicitation_emitter_var.reset(token)
        assert isinstance(result, ErrorData)
        assert "structured form schemas" in result.message

    @pytest.mark.asyncio
    async def test_plain_confirm_emits_marker_and_awaits_resolution(self):
        emitter = AsyncMock()
        params = ElicitRequestFormParams(message="confirm delete?", requestedSchema={})

        token_e = kourai_elicitation_emitter_var.set(emitter)
        token_s = kourai_elicitation_specialist_var.set("techne")
        try:
            # Resolver task — fires after callback registers its Future.
            async def resolver():
                # Spin until exactly one elicitation is pending, then
                # resolve it. Fast path keeps the test sub-100ms.
                for _ in range(100):
                    if pending_count() == 1:
                        elicitation_id = next(iter(_PENDING_ELICITATIONS))
                        await resolve_elicitation(elicitation_id, "accept", None)
                        return
                    await asyncio.sleep(0.005)
                pytest.fail("no elicitation registered within 0.5s")

            resolver_task = asyncio.create_task(resolver())
            result = await _kourai_elicitation_callback(context=cast("Any", None), params=params)
            await resolver_task
        finally:
            kourai_elicitation_emitter_var.reset(token_e)
            kourai_elicitation_specialist_var.reset(token_s)

        assert isinstance(result, ElicitResult)
        assert result.action == "accept"

        # The emitter was called with a properly-formatted marker.
        assert emitter.await_count == 1
        marker = emitter.await_args.args[0]
        decoded = parse_outbound_marker(marker)
        assert decoded is not None
        elicitation_id, specialist, message = decoded
        assert specialist == "techne"
        assert message == "confirm delete?"
        # Registry was cleaned up post-resolution.
        assert pending_count() == 0

    @pytest.mark.asyncio
    async def test_timeout_returns_error_and_cleans_registry(self, monkeypatch):
        # Shrink the timeout so the test doesn't actually wait 5min.
        monkeypatch.setattr("kourai_common.elicitation.ELICITATION_TIMEOUT", 0.05)

        emitter = AsyncMock()
        params = ElicitRequestFormParams(message="confirm?", requestedSchema={})
        token = kourai_elicitation_emitter_var.set(emitter)
        try:
            result = await _kourai_elicitation_callback(context=cast("Any", None), params=params)
        finally:
            kourai_elicitation_emitter_var.reset(token)

        assert isinstance(result, ErrorData)
        assert "timed out" in result.message
        # No leaked Future.
        assert pending_count() == 0


# ── Concurrency ──────────────────────────────────────────────────────────────


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_two_pending_elicitations_resolve_independently(self):
        """Two callbacks waiting on different ids resolve to their own
        answers — proves the registry's per-id keying isn't broken by
        overlap. Mirrors a player handling two concurrent forge actions
        each with their own confirmation.
        """
        fut_a = await _register("id-a")
        fut_b = await _register("id-b")

        await resolve_elicitation("id-b", "decline", None)
        await resolve_elicitation("id-a", "accept", None)

        action_a, _ = fut_a.result()
        action_b, _ = fut_b.result()
        assert action_a == "accept"
        assert action_b == "decline"


# ── Module-level constants ───────────────────────────────────────────────────


# ── HTTP route ───────────────────────────────────────────────────────────────


class TestAttachElicitationRoute:
    """The Starlette route specialists mount on their A2A app so the CLI
    can POST elicitation answers out-of-band — that's how the original
    ``execute()`` 's awaited Future gets resolved without Hephaestus
    needing to disconnect from the streaming task.
    """

    @staticmethod
    def _build_test_client():
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from kourai_common.elicitation import attach_elicitation_route

        app = Starlette()
        attach_elicitation_route(app)
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_resolves_pending_elicitation_returns_204(self):
        await _register("http-test-1")
        client = self._build_test_client()
        resp = client.post(
            "/internal/elicitation/http-test-1",
            json={"action": "accept"},
        )
        assert resp.status_code == 204
        # Future was resolved.
        fut = _PENDING_ELICITATIONS.get("http-test-1")
        # Resolve removes from registry only when the callback's
        # ``finally`` runs; the route just sets the result. The
        # future still exists in the registry until the callback's
        # cleanup. So check the result directly.
        # Actually resolve_elicitation doesn't remove; only the
        # callback's _unregister does. Fine — assert the Future is set.
        assert fut is not None
        assert fut.done()
        action, _ = fut.result()
        assert action == "accept"

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_id(self):
        client = self._build_test_client()
        resp = client.post(
            "/internal/elicitation/never-existed",
            json={"action": "accept"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_action(self):
        await _register("bad-action")
        client = self._build_test_client()
        resp = client.post(
            "/internal/elicitation/bad-action",
            json={"action": "approve"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_non_dict_body(self):
        client = self._build_test_client()
        resp = client.post(
            "/internal/elicitation/anything",
            json="not-an-object",
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_non_dict_content(self):
        await _register("bad-content")
        client = self._build_test_client()
        resp = client.post(
            "/internal/elicitation/bad-content",
            json={"action": "accept", "content": "not-a-dict"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_accepts_content_dict_alongside_action(self):
        fut = await _register("with-content")
        client = self._build_test_client()
        resp = client.post(
            "/internal/elicitation/with-content",
            json={"action": "accept", "content": {"name": "ada"}},
        )
        assert resp.status_code == 204
        action, content = fut.result()
        assert action == "accept"
        assert content == {"name": "ada"}


# ── End-to-end ───────────────────────────────────────────────────────────────


class TestEndToEnd:
    """Round-trip the entire bridge: callback emits a marker → fake CLI
    parses + POSTs to the HTTP route → callback's awaited Future resolves
    → caller receives the right ElicitResult. This is the integration
    contract the forge MCP server depends on; a regression here would
    silently break any tool that calls ``ctx.elicit()``.
    """

    @pytest.mark.asyncio
    async def test_full_round_trip_via_http_route(self):
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from kourai_common.elicitation import attach_elicitation_route

        app = Starlette()
        attach_elicitation_route(app)
        http_client = TestClient(app)

        captured_marker: list[str] = []

        async def _fake_emitter(marker: str) -> None:
            # Stand-in for ``send_working_status`` — the executor's
            # emitter would push this onto the A2A stream. Here we
            # just capture and immediately wake the resolver.
            captured_marker.append(marker)

        params = ElicitRequestFormParams(
            message="overwrite src/main.py?",
            requestedSchema={},
        )

        token_e = kourai_elicitation_emitter_var.set(_fake_emitter)
        token_s = kourai_elicitation_specialist_var.set("techne")

        async def _resolver():
            # Polls until the callback has emitted (i.e. the marker has
            # been captured), then parses + POSTs an answer. Mirrors what
            # the real CLI does on receiving the streaming marker.
            for _ in range(100):
                if captured_marker:
                    decoded = parse_outbound_marker(captured_marker[0])
                    assert decoded is not None
                    elicitation_id, _specialist, _question = decoded
                    resp = http_client.post(
                        f"/internal/elicitation/{elicitation_id}",
                        json={"action": "accept"},
                    )
                    assert resp.status_code == 204
                    return
                await asyncio.sleep(0.005)
            pytest.fail("emitter not invoked within 0.5s — callback didn't surface marker")

        try:
            resolver_task = asyncio.create_task(_resolver())
            result = await _kourai_elicitation_callback(context=cast("Any", None), params=params)
            await resolver_task
        finally:
            kourai_elicitation_emitter_var.reset(token_e)
            kourai_elicitation_specialist_var.reset(token_s)

        assert isinstance(result, ElicitResult)
        assert result.action == "accept"
        # Marker carried the right specialist + message.
        assert len(captured_marker) == 1
        decoded = parse_outbound_marker(captured_marker[0])
        assert decoded is not None
        _, specialist, question = decoded
        assert specialist == "techne"
        assert question == "overwrite src/main.py?"
        # Registry was cleaned up post-resolution.
        assert pending_count() == 0


# ── Module-level constants ───────────────────────────────────────────────────


def test_default_timeout_is_five_minutes():
    """5 minutes is documented as the default in the module docstring;
    a regression here would silently change the player-visible UX —
    pin the value in a test so any future bump is intentional.
    """
    assert ELICITATION_TIMEOUT == 300.0
