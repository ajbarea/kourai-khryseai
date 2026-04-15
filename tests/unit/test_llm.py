"""Tests for kourai_common.llm — LiteLLM wrapper and streaming logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCoerceChunkContent:
    """Pure-function coverage for _coerce_chunk_content.

    Verifies that provider-specific payloads (str, list, dict, object)
    all normalize to plain text.
    """

    def test_string_passthrough(self):
        from kourai_common.llm import _coerce_chunk_content

        assert _coerce_chunk_content("hello") == "hello"

    def test_list_of_strings(self):
        from kourai_common.llm import _coerce_chunk_content

        assert _coerce_chunk_content(["hello", " ", "world"]) == "hello world"

    def test_list_with_dict_text(self):
        from kourai_common.llm import _coerce_chunk_content

        assert _coerce_chunk_content([{"type": "text", "text": "hi"}]) == "hi"

    def test_list_with_object_text_attr(self):
        from kourai_common.llm import _coerce_chunk_content

        obj = MagicMock()
        obj.text = "from obj"
        assert _coerce_chunk_content([obj]) == "from obj"

    def test_dict_with_text_key(self):
        from kourai_common.llm import _coerce_chunk_content

        assert _coerce_chunk_content({"text": "from dict"}) == "from dict"

    def test_dict_with_nested_content(self):
        from kourai_common.llm import _coerce_chunk_content

        assert _coerce_chunk_content({"content": "nested"}) == "nested"

    def test_object_with_text_attr(self):
        from kourai_common.llm import _coerce_chunk_content

        obj = MagicMock()
        obj.text = "attr text"
        assert _coerce_chunk_content(obj) == "attr text"

    def test_none_returns_empty(self):
        from kourai_common.llm import _coerce_chunk_content

        assert _coerce_chunk_content(None) == ""

    def test_unknown_type_returns_empty(self):
        from kourai_common.llm import _coerce_chunk_content

        class NoText:
            pass

        assert _coerce_chunk_content(NoText()) == ""


class TestExtractStreamChunkText:
    """Pure-function coverage for _extract_stream_chunk_text.

    Verifies delta → message → text fallback chain.
    """

    def test_extracts_delta_content(self):
        from kourai_common.llm import _extract_stream_chunk_text

        delta = MagicMock(content="chunk text")
        choice = MagicMock(delta=delta, message=None, text=None)
        chunk = MagicMock(choices=[choice])
        assert _extract_stream_chunk_text(chunk) == "chunk text"

    def test_falls_back_to_message_content(self):
        from kourai_common.llm import _extract_stream_chunk_text

        delta = MagicMock(content=None)
        message = MagicMock(content="message text")
        choice = MagicMock(delta=delta, message=message, text=None)
        chunk = MagicMock(choices=[choice])
        assert _extract_stream_chunk_text(chunk) == "message text"

    def test_falls_back_to_choice_text(self):
        from kourai_common.llm import _extract_stream_chunk_text

        delta = MagicMock(content=None)
        message = MagicMock(content=None)
        choice = MagicMock(delta=delta, message=message, text="choice text")
        chunk = MagicMock(choices=[choice])
        assert _extract_stream_chunk_text(chunk) == "choice text"

    def test_empty_choices_returns_empty(self):
        from kourai_common.llm import _extract_stream_chunk_text

        chunk = MagicMock(choices=[])
        assert _extract_stream_chunk_text(chunk) == ""

    def test_no_choices_attr_returns_empty(self):
        from kourai_common.llm import _extract_stream_chunk_text

        assert _extract_stream_chunk_text(object()) == ""


class TestManageMemory:
    """Tests for _manage_memory — progressive summarization logic."""

    @pytest.mark.asyncio
    async def test_skips_when_below_limit(self):
        """Does not call the LLM when unsummarized message count is within the limit."""
        with (
            patch(
                "kourai_common.llm.get_unsummarized_messages",
                return_value=[{"role": "user", "content": "hi"}],
            ),
            patch("kourai_common.llm._execute_completion", new_callable=AsyncMock) as mock_exec,
        ):
            from kourai_common.llm import _manage_memory

            await _manage_memory("ctx-1", "metis")
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarizes_when_above_limit(self):
        """Calls the LLM, saves the new summary, and marks messages as summarized."""
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(8)]
        mock_state = {"semantic_summary": ""}

        async def _fake_exec(timeout_seconds, **kwargs):
            result = MagicMock()
            result.choices = [MagicMock(message=MagicMock(content="new summary"))]
            return result

        with (
            patch("kourai_common.llm.get_unsummarized_messages", return_value=msgs),
            patch("kourai_common.llm.get_max_unsummarized_idx", return_value=8),
            patch("kourai_common.llm.get_agent_state", return_value=mock_state),
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch("kourai_common.llm.save_agent_state") as mock_save,
            patch("kourai_common.llm.mark_messages_summarized") as mock_mark,
        ):
            from kourai_common.llm import _manage_memory

            await _manage_memory("ctx-1", "metis")

        assert mock_state["semantic_summary"] == "new summary"
        mock_save.assert_called_once()
        mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_integrates_existing_summary_into_prompt(self):
        """Includes the prior summary in the prompt when one already exists."""
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(8)]
        mock_state = {"semantic_summary": "prior context"}
        captured: dict = {}

        async def _fake_exec(timeout_seconds, **kwargs):
            captured["messages"] = kwargs["messages"]
            result = MagicMock()
            result.choices = [MagicMock(message=MagicMock(content="combined"))]
            return result

        with (
            patch("kourai_common.llm.get_unsummarized_messages", return_value=msgs),
            patch("kourai_common.llm.get_max_unsummarized_idx", return_value=8),
            patch("kourai_common.llm.get_agent_state", return_value=mock_state),
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch("kourai_common.llm.save_agent_state"),
            patch("kourai_common.llm.mark_messages_summarized"),
        ):
            from kourai_common.llm import _manage_memory

            await _manage_memory("ctx-1", "metis")

        user_msg = captured["messages"][-1]["content"]
        assert "prior context" in user_msg
        assert "Existing Summary" in user_msg


class TestChatStream:
    """Tests for chat_stream — streaming path, fallback, and timeout."""

    @pytest.mark.asyncio
    async def test_yields_chunks(self):
        """Chunks from the LLM stream are yielded to the caller."""
        mock_chunk = MagicMock(
            choices=[MagicMock(delta=MagicMock(content="hello"), message=None, text=None)]
        )

        async def _fake_exec(timeout_seconds, **kwargs):
            async def _gen():
                yield mock_chunk

            return _gen()

        messages = [{"role": "user", "content": "hi"}]
        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=messages,
            ),
        ):
            from kourai_common.llm import chat_stream

            chunks = [c async for c in chat_stream("metis", messages)]
        assert chunks == ["hello"]

    @pytest.mark.asyncio
    async def test_fallback_when_stream_yields_nothing(self):
        """Falls back to a non-streaming call when the stream produces no text."""
        empty_chunk = MagicMock(
            choices=[MagicMock(delta=MagicMock(content=None), message=None, text=None)]
        )
        fallback = MagicMock()
        fallback.choices = [MagicMock(message=MagicMock(content="fallback text"))]

        async def _fake_exec(timeout_seconds, **kwargs):
            if kwargs.get("stream"):

                async def _gen():
                    yield empty_chunk

                return _gen()
            return fallback

        messages = [{"role": "user", "content": "hi"}]
        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=messages,
            ),
        ):
            from kourai_common.llm import chat_stream

            chunks = [c async for c in chat_stream("metis", messages)]
        assert chunks == ["fallback text"]

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        """Converts TimeoutError to LLMTimeoutError."""

        async def _timeout(timeout_seconds, **kwargs):
            raise TimeoutError

        messages = [{"role": "user", "content": "hi"}]
        with (
            patch("kourai_common.llm._execute_completion", new=_timeout),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=messages,
            ),
        ):
            from kourai_common.llm import LLMTimeoutError, chat_stream

            with pytest.raises(LLMTimeoutError):
                async for _ in chat_stream("metis", messages):
                    pass
