"""Unit tests for kourai_common.messaging Part / Message construction helpers.

Covers the 1.0 wire shape (member-discriminated Part with ``HasField``)
and the ``new_text_message`` / TaskUpdater lifecycle helpers.
"""

from __future__ import annotations

import base64

from a2a.types import Role

from kourai_common.messaging import (
    data_part,
    data_part_to_dict,
    file_part_from_b64,
    get_file_bytes,
    is_file_part,
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
