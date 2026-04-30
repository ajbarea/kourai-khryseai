"""Unit tests for kourai_common.messaging Part / Message construction helpers.

Centralizes A2A wire-shape construction so the eventual a2a-sdk 1.0 cutover
(M7 Phase 3) flips one helper module instead of every executor.
"""

from __future__ import annotations

from a2a.types import Role
from a2a.utils.parts import get_data_parts, get_file_parts, get_text_parts

from kourai_common.messaging import (
    data_part,
    file_part_from_b64,
    get_file_bytes,
    is_file_part,
    text_part,
    user_message,
)


def test_text_part_round_trips_input_text() -> None:
    part = text_part("hello world")
    assert get_text_parts([part]) == ["hello world"]


def test_text_part_handles_empty_string() -> None:
    part = text_part("")
    assert get_text_parts([part]) == [""]


def test_file_part_from_b64_carries_bytes_mime_and_filename() -> None:
    part = file_part_from_b64(
        b64_data="aGVsbG8=",
        media_type="text/plain",
        filename="greeting.txt",
    )
    files = get_file_parts([part])
    assert len(files) == 1
    file = files[0]
    assert file.bytes == "aGVsbG8="
    assert file.mime_type == "text/plain"
    assert file.name == "greeting.txt"


def test_file_part_from_b64_default_filename() -> None:
    part = file_part_from_b64(b64_data="AAAA", media_type="image/png")
    file = get_file_parts([part])[0]
    assert file.name == "attachment"


def test_data_part_carries_dict_payload() -> None:
    payload = {"coverage_target": 80, "framework": "pytest"}
    part = data_part(payload)
    assert get_data_parts([part]) == [payload]


def test_user_message_builds_user_role_message_with_text_body() -> None:
    message = user_message("plan a fizzbuzz module")

    assert message.role == Role.user
    assert message.message_id  # auto-assigned uuid string
    assert isinstance(message.message_id, str)
    assert len(message.parts) == 1
    assert get_text_parts(list(message.parts)) == ["plan a fizzbuzz module"]


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

    parts_list = list(message.parts)
    assert len(parts_list) == 2
    assert get_text_parts(parts_list) == ["here is the screenshot"]
    assert get_file_parts(parts_list)[0].name == "screenshot.png"


# ── Part inspection (M7 Phase 2) ──────────────────────────────────────


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
    part = file_part_from_b64(
        b64_data="aGVsbG8=",
        media_type="image/jpeg",
        filename="photo.jpg",
    )
    b64, media_type = get_file_bytes(part)
    assert b64 == "aGVsbG8="
    assert media_type == "image/jpeg"
