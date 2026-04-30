"""Unit tests for kourai_common.messaging Part / Message construction helpers.

Covers the 1.0 wire shape (member-discriminated Part with ``HasField``)
and the ``new_text_message`` / TaskUpdater lifecycle helpers.
"""

from __future__ import annotations

import base64

from a2a.types import Role

from kourai_common.messaging import (
    CONTENT_KIND_FIELD,
    KIND_CODE,
    KIND_DIALOGUE,
    KIND_SPEC,
    KIND_STATUS,
    KOURAI_STREAMING_EXT_URI,
    data_part,
    data_part_to_dict,
    file_part_from_b64,
    get_content_kind,
    get_file_bytes,
    is_file_part,
    kind_message,
    set_content_kind,
    text_part,
    user_message,
)

# ── Part / Message construction ───────────────────────────────────────


def test_text_part_round_trips_input_text() -> None:
    part = text_part("hello world")
    assert part.HasField("text")
    assert part.text == "hello world"


def test_text_part_handles_empty_string() -> None:
    part = text_part("")
    assert part.text == ""


def test_file_part_from_b64_decodes_to_raw_bytes() -> None:
    raw = b"hello"
    b64 = base64.b64encode(raw).decode("ascii")

    part = file_part_from_b64(
        b64_data=b64,
        media_type="text/plain",
        filename="greeting.txt",
    )

    assert part.HasField("raw")
    assert part.raw == raw
    assert part.media_type == "text/plain"
    assert part.filename == "greeting.txt"


def test_file_part_from_b64_default_filename() -> None:
    part = file_part_from_b64(b64_data="AAAA", media_type="image/png")
    assert part.filename == "attachment"


def test_data_part_carries_dict_payload() -> None:
    payload = {"coverage_target": "80", "framework": "pytest"}
    part = data_part(payload)
    assert part.HasField("data")
    assert data_part_to_dict(part) == payload


def test_user_message_builds_user_role_message_with_text_body() -> None:
    message = user_message("plan a fizzbuzz module")

    assert message.role == Role.ROLE_USER
    assert message.message_id  # auto-assigned uuid string
    assert isinstance(message.message_id, str)
    assert len(message.parts) == 1
    assert message.parts[0].text == "plan a fizzbuzz module"


def test_user_message_threads_context_and_task_ids() -> None:
    message = user_message(
        "follow up answer",
        context_id="ctx-abc",
        task_id="task-xyz",
    )

    assert message.context_id == "ctx-abc"
    assert message.task_id == "task-xyz"


def test_user_message_accepts_extra_parts() -> None:
    extra = file_part_from_b64(b64_data="AAAA", media_type="image/png", filename="screenshot.png")
    message = user_message("here is the screenshot", extra_parts=[extra])

    assert len(message.parts) == 2
    assert message.parts[0].text == "here is the screenshot"
    assert message.parts[1].HasField("raw")
    assert message.parts[1].filename == "screenshot.png"


# ── Part inspection ───────────────────────────────────────────────────


def test_is_file_part_recognizes_file_parts() -> None:
    part = file_part_from_b64(b64_data="aGVsbG8=", media_type="text/plain")
    assert is_file_part(part) is True


def test_is_file_part_rejects_text_parts() -> None:
    part = text_part("not a file")
    assert is_file_part(part) is False


def test_is_file_part_rejects_data_parts() -> None:
    part = data_part({"k": "v"})
    assert is_file_part(part) is False


def test_get_file_bytes_returns_b64_and_media_type() -> None:
    raw = b"hello"
    b64_in = base64.b64encode(raw).decode("ascii")
    part = file_part_from_b64(
        b64_data=b64_in,
        media_type="image/jpeg",
        filename="photo.jpg",
    )
    b64_out, media_type = get_file_bytes(part)
    assert b64_out == b64_in
    assert media_type == "image/jpeg"


# ── Content-kind metadata (M18) ───────────────────────────────────────


def test_kind_constants_serialise_to_documented_strings() -> None:
    assert KIND_DIALOGUE == "dialogue"
    assert KIND_STATUS == "status"
    assert KIND_CODE == "code"
    assert KIND_SPEC == "spec"


def test_kind_message_tags_outbound_message() -> None:
    msg = kind_message("Analyzing request...", KIND_STATUS)

    assert msg.role == Role.ROLE_AGENT
    assert msg.parts[0].text == "Analyzing request..."
    assert get_content_kind(msg) == KIND_STATUS


def test_kind_message_with_dialogue_kind() -> None:
    msg = kind_message('"What sort of fizzbuzz?"', KIND_DIALOGUE)
    assert get_content_kind(msg) == KIND_DIALOGUE


def test_kind_message_threads_context_and_task_ids() -> None:
    msg = kind_message(
        "still working",
        KIND_STATUS,
        context_id="ctx-1",
        task_id="task-1",
    )
    assert msg.context_id == "ctx-1"
    assert msg.task_id == "task-1"


def test_kind_message_coexists_with_extra_metadata() -> None:
    msg = kind_message(
        "narrating",
        KIND_DIALOGUE,
        metadata={"project_id": "abc123", "yolo": True},
    )
    assert get_content_kind(msg) == KIND_DIALOGUE
    assert msg.metadata["project_id"] == "abc123"
    assert msg.metadata["yolo"] is True


def test_set_content_kind_overrides_existing_tag() -> None:
    msg = kind_message("text", KIND_DIALOGUE)
    set_content_kind(msg, KIND_STATUS)
    assert get_content_kind(msg) == KIND_STATUS


def test_get_content_kind_returns_none_for_untagged_message() -> None:
    msg = user_message("plain user message")
    assert get_content_kind(msg) is None


def test_get_content_kind_returns_none_for_unknown_kind_value() -> None:
    """Forward-compat: unknown kind strings route through legacy path, not raise."""
    msg = user_message("foo")
    msg.metadata[KOURAI_STREAMING_EXT_URI] = {CONTENT_KIND_FIELD: "future_kind_we_havent_added_yet"}
    assert get_content_kind(msg) is None


def test_get_content_kind_handles_none_message() -> None:
    """Guard for hosts that may receive a status update with no inner message."""
    assert get_content_kind(None) is None


def test_streaming_extension_uri_is_a2a_spec_namespaced() -> None:
    """Pin the on-the-wire extension URI — protocol contract.

    A2A 1.0 spec mandates URI-namespaced top-level extension keys
    with nested object values. The URI is stable; sibling fields can
    join the existing nested object without colliding with other
    extensions on the same Message.
    """
    assert KOURAI_STREAMING_EXT_URI == "https://kourai.khryseai/ext/streaming/v1"
    assert CONTENT_KIND_FIELD == "content_kind"


def test_set_content_kind_uses_nested_object_under_uri_key() -> None:
    """Wire shape regression: ``metadata[URI] = {"content_kind": kind}``.

    Pins the canonical A2A extension shape. If a future field
    (priority, subkind, ssml_version) joins the streaming extension,
    it lives in the same nested object — no second URI key needed.
    """
    msg = user_message("foo")
    set_content_kind(msg, KIND_STATUS)
    ext = msg.metadata[KOURAI_STREAMING_EXT_URI]
    assert ext[CONTENT_KIND_FIELD] == "status"


def test_get_content_kind_reads_through_task_status_update_event() -> None:
    """Wire-shape regression: hosts read kind via ``event.status.message``.

    The host-side routing path in ``hosts/cli/streaming.py`` reads the kind
    off ``event.status.message`` (a Message proto inside the
    TaskStatusUpdateEvent's TaskStatus). Verify the metadata round-trips
    through that nested-proto shape, not just on a bare Message.
    """
    from a2a.types import TaskState, TaskStatus, TaskStatusUpdateEvent

    msg = kind_message("Analyzing request...", KIND_STATUS)
    status = TaskStatus(state=TaskState.TASK_STATE_WORKING, message=msg)
    event = TaskStatusUpdateEvent(task_id="t1", context_id="c1", status=status)

    assert get_content_kind(event.status.message) == KIND_STATUS
