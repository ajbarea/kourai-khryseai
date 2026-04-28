"""Elicitation client capability — bridges MCP ``elicitation/create``
into kourai's INPUT_REQUIRED rendering layer.

MCP's ``elicitation/create`` is a synchronous server-to-client request:
a tool calls ``ctx.elicit(...)`` mid-execution, the server sends the
request to the client, and awaits a single ``ElicitResult``. A2A's
``INPUT_REQUIRED`` is a return-then-resume pause: the executor must
return for the player's response to come back as a new task message.
The two don't compose without bridging machinery — this module is that
bridge.

How it works end-to-end:

1. A forge tool calls ``ctx.elicit(message="confirm delete?")``.
2. The kourai-mcp-forge server sends ``elicitation/create`` to the
   specialist's MCP client session.
3. ``_kourai_elicitation_callback`` (wired by ``mcp_client``) fires.
4. The callback generates a UUID elicitation id, registers an
   ``asyncio.Future`` in the module-level ``_PENDING_ELICITATIONS``
   registry, and surfaces the question via the active specialist's
   A2A stream as ``[ELICIT:{id}:{specialist}] {message}``.
5. The callback awaits the Future (5-min default timeout).
6. Hephaestus's relay sees the marker, surfaces as ``INPUT_REQUIRED``
   to the CLI; the CLI renders an inline yes/no prompt.
7. The CLI sends the player's answer as a follow-up A2A message
   tagged ``[elicit_answer:{id}:{action}]``. Hephaestus dispatches a
   fresh A2A task to the originating specialist with the same tag.
8. The specialist's NEW ``execute()`` call detects the tag at entry
   and calls ``resolve_elicitation``, which sets the Future via the
   module-level registry. The fresh task returns immediately.
9. The original ``execute()`` 's awaited Future resolves; the
   callback returns ``ElicitResult`` to the MCP server; the forge
   tool gets its answer and continues.

Why module-level registry rather than a per-router instance: the
fresh ``execute()`` call (step 8) runs in a different task than the
blocked one (step 5). Per-call state can't be shared across tasks
without a process-level lookup keyed by ``elicitation_id``. The
registry is the lookup.

URL-mode and form-mode-with-schema elicitations are out of scope for
the MVP CLI bridge — the callback returns ``decline`` with a reason
in those cases. The forge MCP server itself doesn't currently call
``ctx.elicit()`` from any tool; the first real caller will land in a
follow-on PR (e.g., ``delete_file`` confirming destructive deletes
against uncommitted changes).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Literal, cast

from mcp.types import (
    ElicitRequestFormParams,
    ElicitResult,
    ErrorData,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from mcp.shared.context import RequestContext
    from mcp.types import ElicitRequestParams
    from starlette.requests import Request

log = logging.getLogger(__name__)

type ElicitAction = Literal["accept", "decline", "cancel"]
type ElicitContent = dict[str, Any] | None
type EmitterFn = "Callable[[str], Awaitable[None]]"

# ── Module-level state ───────────────────────────────────────────────────────
#
# Keyed by elicitation id. The Future is set by ``resolve_elicitation``
# from a different asyncio task than the one awaiting it (see module
# docstring: the "fresh execute()" path resolves; the "blocked execute()"
# path awaits). Guarded by ``_REGISTRY_LOCK`` so the
# register/resolve/cleanup operations can't race.
type _PendingFuture = "asyncio.Future[tuple[ElicitAction, ElicitContent]]"
_PENDING_ELICITATIONS: dict[str, _PendingFuture] = {}
_REGISTRY_LOCK = asyncio.Lock()

# Surface emitter — the executor sets this before driving the LLM
# loop. The callback uses it to push the elicitation marker into the
# A2A stream that Hephaestus is consuming. ``None`` when no executor
# context (out-of-tree caller, unit tests that aren't exercising the
# round-trip) — the callback returns ``ErrorData`` rather than
# silently dropping the question.
kourai_elicitation_emitter_var: ContextVar[EmitterFn | None] = ContextVar(
    "kourai_elicitation_emitter", default=None
)

# Specialist agent name (e.g., "techne"). Embedded in the marker so
# Hephaestus's resume path knows which specialist to route the answer
# back to. Set by the executor; ``None`` in non-executor contexts.
kourai_elicitation_specialist_var: ContextVar[str | None] = ContextVar(
    "kourai_elicitation_specialist", default=None
)

# Default elicitation timeout. Long enough for a player to read the
# question and respond at the CLI; short enough that a forgotten
# prompt doesn't pin the executor forever. Override via env var so
# tests can shrink it without monkey-patching module state.
ELICITATION_TIMEOUT = float(os.getenv("KOURAI_ELICITATION_TIMEOUT", "300"))

# ── Marker format ────────────────────────────────────────────────────────────
#
# Outbound (specialist → CLI via Hephaestus):
#   [ELICIT:{id}:{specialist}] {message}
#
# Inbound (CLI → Hephaestus → specialist):
#   [elicit_answer:{id}:{action}] {optional content json}
#
# Capitalisation is asymmetric so a misrouted message is obvious in
# logs. The message body is plain text — form-mode schemas aren't
# round-tripped through the marker; the CLI renders only plain text
# confirms in this MVP.

_OUTBOUND_PREFIX = "[ELICIT:"
_INBOUND_PREFIX = "[elicit_answer:"


def format_outbound_marker(elicitation_id: str, specialist: str, message: str) -> str:
    """Render the streaming-status line that Hephaestus relays to the CLI."""
    return f"{_OUTBOUND_PREFIX}{elicitation_id}:{specialist}] {message}"


def parse_outbound_marker(line: str) -> tuple[str, str, str] | None:
    """Decode ``[ELICIT:{id}:{specialist}] {message}``.

    Returns ``(elicitation_id, specialist, message)`` or ``None`` if
    the line isn't shaped as an elicitation marker.
    """
    if not line.startswith(_OUTBOUND_PREFIX):
        return None
    rest = line[len(_OUTBOUND_PREFIX) :]
    head, sep, message = rest.partition("] ")
    if not sep:
        return None
    parts = head.split(":", 1)
    if len(parts) != 2:
        return None
    elicitation_id, specialist = parts
    return elicitation_id, specialist, message


def parse_inbound_marker(text: str) -> tuple[str, ElicitAction] | None:
    """Decode ``[elicit_answer:{id}:{action}]`` from the player's reply.

    Tolerates trailing message body — the CLI may append a free-text
    rationale after the tag. Returns ``None`` if no answer marker is
    present or the action isn't one of the three valid values.
    """
    idx = text.find(_INBOUND_PREFIX)
    if idx == -1:
        return None
    rest = text[idx + len(_INBOUND_PREFIX) :]
    end = rest.find("]")
    if end == -1:
        return None
    body = rest[:end]
    parts = body.split(":", 1)
    if len(parts) != 2:
        return None
    elicitation_id, action = parts
    if action not in ("accept", "decline", "cancel"):
        return None
    # ty doesn't propagate the ``not in`` membership check to a Literal
    # narrowing without an explicit ``assert``; cast keeps the public
    # signature precise without the runtime cost of the assert.
    return elicitation_id, cast("ElicitAction", action)


# ── Registry API ─────────────────────────────────────────────────────────────


async def _register(elicitation_id: str) -> _PendingFuture:
    """Create a Future for the given id and register it. Caller awaits."""
    fut: _PendingFuture = asyncio.get_event_loop().create_future()
    async with _REGISTRY_LOCK:
        if elicitation_id in _PENDING_ELICITATIONS:
            # UUID4 collision is astronomically unlikely; if we see one
            # the calling code is reusing ids, which is a bug — surface
            # rather than silently overwrite.
            raise RuntimeError(f"elicitation id collision: {elicitation_id}")
        _PENDING_ELICITATIONS[elicitation_id] = fut
    return fut


async def _unregister(elicitation_id: str) -> None:
    """Drop a Future from the registry. Idempotent."""
    async with _REGISTRY_LOCK:
        _PENDING_ELICITATIONS.pop(elicitation_id, None)


async def resolve_elicitation(
    elicitation_id: str,
    action: ElicitAction,
    content: ElicitContent = None,
) -> bool:
    """Set the Future for ``elicitation_id`` from an external task.

    Called by the specialist's executor when it sees an
    ``[elicit_answer:` tag on a fresh A2A message. Returns ``True``
    if a matching Future was found and set, ``False`` otherwise — a
    stale answer (Future already cancelled by timeout, or never
    registered) is logged but not raised.
    """
    async with _REGISTRY_LOCK:
        fut = _PENDING_ELICITATIONS.get(elicitation_id)
    if fut is None:
        log.warning(
            "resolve_elicitation: no pending Future for id=%s (stale or never registered)",
            elicitation_id,
        )
        return False
    if fut.done():
        log.warning(
            "resolve_elicitation: Future for id=%s already resolved/cancelled",
            elicitation_id,
        )
        return False
    fut.set_result((action, content))
    return True


def pending_count() -> int:
    """Return the number of in-flight elicitations. Test introspection."""
    return len(_PENDING_ELICITATIONS)


# ── SDK callback ─────────────────────────────────────────────────────────────


def attach_elicitation_route(app: Any, route_path: str = "/internal/elicitation/{eid}") -> None:
    """Mount the elicitation answer-receiver onto a Starlette app.

    Each specialist's HTTP server (Techne / Kallos / Dokimasia) calls
    this from its ``__main__`` after ``A2AStarletteApplication.build()``
    so a CLI POST to ``{specialist_url}{route_path}`` can resolve the
    Future the elicitation callback is awaiting.

    Body shape: ``{"action": "accept" | "decline" | "cancel",
    "content": <optional dict matching requestedSchema>}``.

    Returns:
        - ``204 No Content`` on successful resolve (matched a pending Future).
        - ``404 Not Found`` if the elicitation id is unknown (already
          resolved, never registered, or timed out and cleaned up).
        - ``400 Bad Request`` if the body is malformed or the action
          isn't one of the three valid values.
    """
    from starlette.responses import JSONResponse, Response

    async def _handler(request: Request) -> Response:
        eid = request.path_params["eid"]
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        action = body.get("action")
        if action not in ("accept", "decline", "cancel"):
            return JSONResponse(
                {"error": "action must be 'accept', 'decline', or 'cancel'"},
                status_code=400,
            )
        content = body.get("content")
        if content is not None and not isinstance(content, dict):
            return JSONResponse(
                {"error": "content must be an object or omitted"},
                status_code=400,
            )
        resolved = await resolve_elicitation(eid, action, content)
        if not resolved:
            return JSONResponse(
                {"error": f"no pending elicitation for id {eid}"},
                status_code=404,
            )
        return Response(status_code=204)

    app.add_route(route_path, _handler, methods=["POST"])


async def _kourai_elicitation_callback(
    context: RequestContext[Any, Any],
    params: ElicitRequestParams,
) -> ElicitResult | ErrorData:
    """SDK-shaped callback. Bridges MCP ``elicitation/create`` to the
    specialist's A2A stream + the registry-resolved Future.

    Returns ``ErrorData`` (rather than raising) for the legible-error
    paths the SDK propagates back to the server unchanged.
    """
    # URL mode is for OAuth / payment / out-of-band flows. The CLI
    # bridge can't render those in this MVP — decline cleanly.
    if not isinstance(params, ElicitRequestFormParams):
        return ElicitResult(action="decline")

    # Form mode with a structured schema needs richer rendering than
    # the MVP CLI offers (it handles plain confirm only). Decline with
    # a reason so the server-side tool can handle gracefully.
    requested_schema = getattr(params, "requestedSchema", None)
    if requested_schema:
        properties = (
            requested_schema.get("properties", {}) if isinstance(requested_schema, dict) else {}
        )
        if properties:
            return ErrorData(
                code=-32601,
                message=(
                    "kourai elicitation MVP: structured form schemas are not yet "
                    "supported; this client handles plain-text confirms only. "
                    "Re-issue with empty requestedSchema for a yes/no prompt."
                ),
            )

    emitter = kourai_elicitation_emitter_var.get()
    if emitter is None:
        return ErrorData(
            code=-32601,
            message=(
                "kourai elicitation requires kourai_elicitation_emitter_var "
                "to be set by the calling specialist executor; out-of-tree "
                "callers cannot route to a player."
            ),
        )

    specialist = kourai_elicitation_specialist_var.get() or "unknown"
    elicitation_id = uuid.uuid4().hex
    marker = format_outbound_marker(elicitation_id, specialist, params.message)

    fut = await _register(elicitation_id)
    try:
        await emitter(marker)
        try:
            action, content = await asyncio.wait_for(fut, timeout=ELICITATION_TIMEOUT)
        except TimeoutError:
            log.warning(
                "elicitation %s timed out after %.0fs (specialist=%s)",
                elicitation_id,
                ELICITATION_TIMEOUT,
                specialist,
            )
            return ErrorData(
                code=-32000,
                message=(
                    f"elicitation timed out after {ELICITATION_TIMEOUT:.0f}s "
                    "with no player response"
                ),
            )
    finally:
        await _unregister(elicitation_id)

    return ElicitResult(action=action, content=content)
