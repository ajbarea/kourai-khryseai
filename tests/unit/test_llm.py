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

    @pytest.mark.asyncio
    async def test_force_bypasses_threshold(self):
        """force=True summarizes even when below WORKING_MEMORY_LIMIT,
        which is what the player-triggered /compact slash command needs."""
        # 4 messages — well below the default 5-message threshold; without
        # force=True the auto-trigger would skip.
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(4)]
        mock_state = {"semantic_summary": ""}

        async def _fake_exec(timeout_seconds, **kwargs):
            result = MagicMock()
            result.choices = [MagicMock(message=MagicMock(content="forced summary"))]
            return result

        with (
            patch("kourai_common.llm.get_unsummarized_messages", return_value=msgs),
            patch("kourai_common.llm.get_max_unsummarized_idx", return_value=4),
            patch("kourai_common.llm.get_agent_state", return_value=mock_state),
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch("kourai_common.llm.save_agent_state") as mock_save,
            patch("kourai_common.llm.mark_messages_summarized") as mock_mark,
        ):
            from kourai_common.llm import _manage_memory

            count = await _manage_memory("ctx-1", "metis", force=True)

        # Default rule "keep last 2 unsummarized" → 4 - 2 = 2 folded
        assert count == 2
        mock_save.assert_called_once()
        mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_returns_zero_when_too_few_messages(self):
        """No-op even with force=True when there aren't enough messages
        to keep the "last 2 unsummarized" buffer plus anything to fold."""
        msgs = [{"role": "user", "content": "single"}]

        with (
            patch("kourai_common.llm.get_unsummarized_messages", return_value=msgs),
            patch("kourai_common.llm._execute_completion", new_callable=AsyncMock) as mock_exec,
        ):
            from kourai_common.llm import _manage_memory

            count = await _manage_memory("ctx-1", "metis", force=True)

        assert count == 0
        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_memory_wrapper_forces(self):
        """compact_memory is a thin wrapper that always passes force=True."""
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(3)]
        mock_state = {"semantic_summary": ""}

        async def _fake_exec(timeout_seconds, **kwargs):
            result = MagicMock()
            result.choices = [MagicMock(message=MagicMock(content="ok"))]
            return result

        with (
            patch("kourai_common.llm.get_unsummarized_messages", return_value=msgs),
            patch("kourai_common.llm.get_max_unsummarized_idx", return_value=3),
            patch("kourai_common.llm.get_agent_state", return_value=mock_state),
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch("kourai_common.llm.save_agent_state"),
            patch("kourai_common.llm.mark_messages_summarized"),
        ):
            from kourai_common.llm import compact_memory

            count = await compact_memory("ctx-1", "metis")

        # 3 - 2 (keep last 2) = 1 folded
        assert count == 1


class TestChatTierKwarg:
    """``tier`` kwarg on ``chat()`` / ``chat_stream()`` / ``chat_with_tools()``
    overrides the env-set MODEL_TIER for that single call."""

    @pytest.mark.asyncio
    async def test_tier_kwarg_passed_to_get_model(self):
        from kourai_common import llm

        captured: dict = {}

        def fake_get_model(agent_name, tier=None):
            captured["agent_name"] = agent_name
            captured["tier"] = tier
            return "fake-model-id"

        async def fake_execute(**kwargs):
            captured["model"] = kwargs.get("model")
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="ok"))],
                usage=None,
            )

        with (
            patch.object(llm, "get_model", side_effect=fake_get_model),
            patch.object(llm, "_execute_completion", side_effect=fake_execute),
            patch.object(
                llm, "_build_contextual_messages", new_callable=AsyncMock, return_value=[]
            ),
        ):
            await llm.chat("metis", [{"role": "user", "content": "x"}], tier="cheap")

        assert captured["agent_name"] == "metis"
        assert captured["tier"] == "cheap"
        assert captured["model"] == "fake-model-id"

    @pytest.mark.asyncio
    async def test_default_tier_none_preserves_existing_callers(self):
        # Backward-compat: callers that don't pass tier get the env behavior
        # (None → get_model uses MODEL_TIER). Regression guard.
        from kourai_common import llm

        captured: dict = {}

        def fake_get_model(agent_name, tier=None):
            captured["tier"] = tier
            return "fake"

        async def fake_execute(**kwargs):
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="ok"))],
                usage=None,
            )

        with (
            patch.object(llm, "get_model", side_effect=fake_get_model),
            patch.object(llm, "_execute_completion", side_effect=fake_execute),
            patch.object(
                llm, "_build_contextual_messages", new_callable=AsyncMock, return_value=[]
            ),
        ):
            await llm.chat("metis", [{"role": "user", "content": "x"}])

        assert captured["tier"] is None

    @pytest.mark.asyncio
    async def test_chat_stream_tier_kwarg_passed_to_get_model(self):
        # Symmetry with chat() — chat_stream takes the same kwarg so a
        # caller can pin a streaming call to cheap without switching APIs.
        from kourai_common import llm

        captured: dict = {}

        def fake_get_model(agent_name, tier=None):
            captured["agent_name"] = agent_name
            captured["tier"] = tier
            return "fake-model-id"

        # chat_stream calls _execute_completion(stream=True) which returns
        # an async iterator of chunks. Mirror the existing
        # TestChatStream::test_yields_chunks pattern.
        chunk = MagicMock(
            choices=[MagicMock(delta=MagicMock(content="hi"), message=None, text=None)]
        )

        async def fake_execute(timeout_seconds, **kwargs):
            captured["model"] = kwargs.get("model")

            async def _gen():
                yield chunk

            return _gen()

        with (
            patch.object(llm, "get_model", side_effect=fake_get_model),
            patch.object(llm, "_execute_completion", side_effect=fake_execute),
            patch.object(
                llm, "_build_contextual_messages", new_callable=AsyncMock, return_value=[]
            ),
        ):
            async for _ in llm.chat_stream(
                "metis", [{"role": "user", "content": "x"}], tier="cheap"
            ):
                pass

        assert captured["agent_name"] == "metis"
        assert captured["tier"] == "cheap"
        assert captured["model"] == "fake-model-id"

    @pytest.mark.asyncio
    async def test_chat_stream_default_tier_preserves_callers(self):
        # Backward-compat regression guard for chat_stream.
        from kourai_common import llm

        captured: dict = {}

        def fake_get_model(agent_name, tier=None):
            captured["tier"] = tier
            return "fake"

        chunk = MagicMock(
            choices=[MagicMock(delta=MagicMock(content="hi"), message=None, text=None)]
        )

        async def fake_execute(timeout_seconds, **kwargs):
            async def _gen():
                yield chunk

            return _gen()

        with (
            patch.object(llm, "get_model", side_effect=fake_get_model),
            patch.object(llm, "_execute_completion", side_effect=fake_execute),
            patch.object(
                llm, "_build_contextual_messages", new_callable=AsyncMock, return_value=[]
            ),
        ):
            async for _ in llm.chat_stream("metis", [{"role": "user", "content": "x"}]):
                pass

        assert captured["tier"] is None

    @pytest.mark.asyncio
    async def test_chat_with_tools_tier_kwarg_passed_to_get_model(self):
        # Same symmetry on the agentic-loop driver. Future caller might
        # pin a low-stakes lint-fix loop to cheap; the kwarg is ready.
        from kourai_common import llm

        captured: dict = {}

        def fake_get_model(agent_name, tier=None):
            captured["agent_name"] = agent_name
            captured["tier"] = tier
            return "fake-model-id"

        async def fake_execute(**kwargs):
            captured["model"] = kwargs.get("model")
            # Return a response with no tool_calls so the loop exits
            # after one iteration.
            choice = MagicMock()
            choice.message = MagicMock(content="done", tool_calls=None)
            choice.message.role = "assistant"
            return MagicMock(choices=[choice], usage=None)

        with (
            patch.object(llm, "get_model", side_effect=fake_get_model),
            patch.object(llm, "_execute_completion", side_effect=fake_execute),
            patch.object(
                llm, "_build_contextual_messages", new_callable=AsyncMock, return_value=[]
            ),
        ):
            await llm.chat_with_tools(
                "kallos",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={},
                tier="cheap",
            )

        assert captured["agent_name"] == "kallos"
        assert captured["tier"] == "cheap"

    @pytest.mark.asyncio
    async def test_chat_with_tools_default_tier_preserves_callers(self):
        # Backward-compat regression guard for chat_with_tools.
        from kourai_common import llm

        captured: dict = {}

        def fake_get_model(agent_name, tier=None):
            captured["tier"] = tier
            return "fake"

        async def fake_execute(**kwargs):
            choice = MagicMock()
            choice.message = MagicMock(content="done", tool_calls=None)
            choice.message.role = "assistant"
            return MagicMock(choices=[choice], usage=None)

        with (
            patch.object(llm, "get_model", side_effect=fake_get_model),
            patch.object(llm, "_execute_completion", side_effect=fake_execute),
            patch.object(
                llm, "_build_contextual_messages", new_callable=AsyncMock, return_value=[]
            ),
        ):
            await llm.chat_with_tools(
                "kallos",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={},
            )

        assert captured["tier"] is None


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


def _mk_tool_call(call_id: str, name: str, arguments: str) -> MagicMock:
    """Build an OpenAI-shape tool_call mock as LiteLLM exposes it."""
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    tc = MagicMock()
    tc.id = call_id
    tc.function = fn
    return tc


def _mk_response(text: str = "", tool_calls: list | None = None) -> MagicMock:
    """Build a LiteLLM-style completion response."""
    message = MagicMock()
    message.content = text
    message.tool_calls = tool_calls or []
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


class TestNormalizeToolCalls:
    """Pure-function coverage for _normalize_tool_calls."""

    def test_extracts_attribute_style_calls(self):
        from kourai_common.llm import _normalize_tool_calls

        message = MagicMock()
        message.tool_calls = [_mk_tool_call("c1", "write_file", '{"path": "a.py"}')]
        result = _normalize_tool_calls(message)
        assert result == [{"id": "c1", "name": "write_file", "arguments": '{"path": "a.py"}'}]

    def test_extracts_dict_style_calls(self):
        from kourai_common.llm import _normalize_tool_calls

        message = MagicMock()
        message.tool_calls = [
            {"id": "c2", "function": {"name": "edit_file", "arguments": "{}"}},
        ]
        result = _normalize_tool_calls(message)
        assert result == [{"id": "c2", "name": "edit_file", "arguments": "{}"}]

    def test_skips_calls_without_function_or_name(self):
        from kourai_common.llm import _normalize_tool_calls

        bad_no_fn = MagicMock(spec=["id"])
        bad_no_fn.id = "c3"
        no_name_fn = MagicMock()
        no_name_fn.name = None
        no_name_fn.arguments = "{}"
        bad_no_name = MagicMock()
        bad_no_name.id = "c4"
        bad_no_name.function = no_name_fn
        message = MagicMock()
        message.tool_calls = [bad_no_fn, bad_no_name]
        assert _normalize_tool_calls(message) == []

    def test_no_tool_calls_returns_empty(self):
        from kourai_common.llm import _normalize_tool_calls

        message = MagicMock()
        message.tool_calls = None
        assert _normalize_tool_calls(message) == []


class TestChatWithTools:
    """Tests for chat_with_tools — agentic tool-use loop."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_text_immediately(self):
        """When the model returns plain text on the first turn, return it unchanged."""
        responses = [_mk_response(text="just an answer")]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        messages = [{"role": "user", "content": "hi"}]
        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=list(messages),
            ),
        ):
            from kourai_common.llm import chat_with_tools

            text, log = await chat_with_tools("techne", messages, tools=[], tool_handlers={})
        assert text == "just an answer"
        assert log == []

    @pytest.mark.asyncio
    async def test_executes_handler_then_returns_text(self):
        """Standard agentic loop: tool_call → handler runs → second turn returns text."""
        responses = [
            _mk_response(tool_calls=[_mk_tool_call("c1", "write_file", '{"path": "a.py"}')]),
            _mk_response(text="done"),
        ]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        async def _write_file(path: str, project_root: str = "") -> str:
            return f"wrote {path} in {project_root}"

        messages = [{"role": "user", "content": "make a file"}]
        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=list(messages),
            ),
        ):
            from kourai_common.llm import chat_with_tools

            text, log = await chat_with_tools(
                "techne",
                messages,
                tools=[{"type": "function", "function": {"name": "write_file"}}],
                tool_handlers={"write_file": _write_file},
                handler_context={"project_root": "/work"},
            )
        assert text == "done"
        assert log == [
            {
                "name": "write_file",
                "args": {"path": "a.py"},
                "result": "wrote a.py in /work",
            }
        ]

    @pytest.mark.asyncio
    async def test_handler_context_overrides_model_args(self):
        """Server-injected handler_context wins so the model can't override project_root."""
        responses = [
            _mk_response(
                tool_calls=[
                    _mk_tool_call("c1", "write_file", '{"path": "a.py", "project_root": "/evil"}')
                ]
            ),
            _mk_response(text="done"),
        ]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        captured: dict = {}

        async def _write_file(path: str, project_root: str) -> str:
            captured["project_root"] = project_root
            return "ok"

        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import chat_with_tools

            await chat_with_tools(
                "techne",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={"write_file": _write_file},
                handler_context={"project_root": "/safe"},
            )
        assert captured["project_root"] == "/safe"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_result(self):
        """An unknown tool name produces an ERROR result and the loop continues."""
        responses = [
            _mk_response(tool_calls=[_mk_tool_call("c1", "nope", "{}")]),
            _mk_response(text="recovered"),
        ]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import chat_with_tools

            text, log = await chat_with_tools(
                "techne",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={},
            )
        assert text == "recovered"
        assert log[0]["result"].startswith("ERROR: unknown tool 'nope'")

    @pytest.mark.asyncio
    async def test_handler_exception_captured_as_error(self):
        """A handler raising an exception becomes an ERROR result without crashing the loop."""
        responses = [
            _mk_response(tool_calls=[_mk_tool_call("c1", "boom", "{}")]),
            _mk_response(text="ok"),
        ]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        async def _boom() -> str:
            raise RuntimeError("kaboom")

        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import chat_with_tools

            text, log = await chat_with_tools(
                "techne",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={"boom": _boom},
            )
        assert text == "ok"
        assert log[0]["result"] == "ERROR: RuntimeError: kaboom"

    @pytest.mark.asyncio
    async def test_invalid_json_args_captured_as_error(self):
        """Malformed JSON in tool arguments yields an ERROR without invoking the handler."""
        responses = [
            _mk_response(tool_calls=[_mk_tool_call("c1", "write_file", "{not json")]),
            _mk_response(text="ok"),
        ]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        called = False

        async def _write_file(**kwargs) -> str:
            nonlocal called
            called = True
            return "wrote"

        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import chat_with_tools

            _, log = await chat_with_tools(
                "techne",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={"write_file": _write_file},
            )
        assert called is False
        assert log[0]["result"].startswith("ERROR: invalid tool arguments")

    @pytest.mark.asyncio
    async def test_max_iters_caps_runaway_loops(self):
        """Loop terminates at max_iters when the model never stops calling tools."""

        async def _fake_exec(timeout_seconds, **kwargs):
            return _mk_response(tool_calls=[_mk_tool_call("c1", "noop", "{}")])

        async def _noop() -> str:
            return "noop"

        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import chat_with_tools

            _, log = await chat_with_tools(
                "techne",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={"noop": _noop},
                max_iters=3,
            )
        assert len(log) == 3

    @pytest.mark.asyncio
    async def test_on_tool_call_callback_fires_per_call(self):
        """The on_tool_call hook is invoked for every executed tool, in order."""
        responses = [
            _mk_response(tool_calls=[_mk_tool_call("c1", "f", '{"a": 1}')]),
            _mk_response(tool_calls=[_mk_tool_call("c2", "f", '{"a": 2}')]),
            _mk_response(text="bye"),
        ]

        async def _fake_exec(timeout_seconds, **kwargs):
            return responses.pop(0)

        async def _f(a: int) -> str:
            return f"a={a}"

        events: list = []

        async def _hook(name: str, args: dict, result: str) -> None:
            events.append((name, args, result))

        with (
            patch("kourai_common.llm._execute_completion", new=_fake_exec),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import chat_with_tools

            await chat_with_tools(
                "techne",
                [{"role": "user", "content": "x"}],
                tools=[],
                tool_handlers={"f": _f},
                on_tool_call=_hook,
            )
        assert events == [("f", {"a": 1}, "a=1"), ("f", {"a": 2}, "a=2")]

    @pytest.mark.asyncio
    async def test_timeout_converts_to_llm_timeout_error(self):
        """A TimeoutError from the underlying call surfaces as LLMTimeoutError."""

        async def _timeout(timeout_seconds, **kwargs):
            raise TimeoutError

        with (
            patch("kourai_common.llm._execute_completion", new=_timeout),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "x"}],
            ),
        ):
            from kourai_common.llm import LLMTimeoutError, chat_with_tools

            with pytest.raises(LLMTimeoutError):
                await chat_with_tools(
                    "techne",
                    [{"role": "user", "content": "x"}],
                    tools=[],
                    tool_handlers={},
                )


class TestCacheControlMarkers:
    """Pure-function coverage for the prompt-caching helpers (M4).

    LiteLLM forwards `cache_control` to Anthropic / Gemini / Vertex and drops
    it on other providers, so the markers are safe everywhere.
    """

    def test_mark_system_string_becomes_one_text_block(self):
        from kourai_common.llm import _mark_system_cacheable

        out = _mark_system_cacheable(
            [
                {"role": "system", "content": "hello"},
                {"role": "user", "content": "hi"},
            ]
        )
        assert out[0]["content"] == [
            {"type": "text", "text": "hello", "cache_control": {"type": "ephemeral"}}
        ]
        assert out[1] == {"role": "user", "content": "hi"}

    def test_mark_system_no_system_message_returns_unchanged(self):
        from kourai_common.llm import _mark_system_cacheable

        msgs = [{"role": "user", "content": "hi"}]
        assert _mark_system_cacheable(msgs) is msgs

    def test_mark_system_empty_list_returns_unchanged(self):
        from kourai_common.llm import _mark_system_cacheable

        assert _mark_system_cacheable([]) == []

    def test_mark_system_already_block_content_is_left_alone(self):
        from kourai_common.llm import _mark_system_cacheable

        existing = [{"type": "text", "text": "pre"}, {"type": "text", "text": "post"}]
        msgs = [{"role": "system", "content": existing}]
        out = _mark_system_cacheable(msgs)
        assert out is msgs

    def test_mark_first_user_string_becomes_text_block(self):
        from kourai_common.llm import _mark_first_user_cacheable

        out = _mark_first_user_cacheable(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "task"},
            ]
        )
        assert out[1]["content"] == [
            {"type": "text", "text": "task", "cache_control": {"type": "ephemeral"}}
        ]
        assert out[0] == {"role": "system", "content": "sys"}

    def test_mark_first_user_only_marks_first(self):
        from kourai_common.llm import _mark_first_user_cacheable

        out = _mark_first_user_cacheable(
            [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "second"},
            ]
        )
        assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
        assert out[2] == {"role": "user", "content": "second"}

    def test_mark_first_user_multimodal_marks_last_text_block(self):
        from kourai_common.llm import _mark_first_user_cacheable

        content = [
            {"type": "text", "text": "look at this"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            {"type": "text", "text": "and tell me what you see"},
        ]
        out = _mark_first_user_cacheable([{"role": "user", "content": content}])
        marked = out[0]["content"]
        assert marked[0] == {"type": "text", "text": "look at this"}
        assert marked[1] == {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,..."},
        }
        assert marked[2] == {
            "type": "text",
            "text": "and tell me what you see",
            "cache_control": {"type": "ephemeral"},
        }

    def test_mark_first_user_no_user_returns_unchanged(self):
        from kourai_common.llm import _mark_first_user_cacheable

        msgs = [{"role": "system", "content": "sys"}]
        assert _mark_first_user_cacheable(msgs) == msgs

    def test_mark_last_tool_marks_function_dict(self):
        from kourai_common.llm import _mark_last_tool_cacheable

        tools = [
            {"type": "function", "function": {"name": "a"}},
            {"type": "function", "function": {"name": "b"}},
        ]
        out = _mark_last_tool_cacheable(tools)
        assert out[0]["function"] == {"name": "a"}
        assert out[1]["function"] == {
            "name": "b",
            "cache_control": {"type": "ephemeral"},
        }

    def test_mark_last_tool_empty_returns_unchanged(self):
        from kourai_common.llm import _mark_last_tool_cacheable

        assert _mark_last_tool_cacheable([]) == []

    def test_mark_last_tool_idempotent(self):
        from kourai_common.llm import _mark_last_tool_cacheable

        tools = [
            {
                "type": "function",
                "function": {"name": "a", "cache_control": {"type": "ephemeral"}},
            }
        ]
        assert _mark_last_tool_cacheable(tools) == tools


class TestCachedTextBlocks:
    """Pure-function coverage for cached_text_blocks — the public helper that
    callers (player_context, hephaestus's manual routing path) use to wrap
    static + dynamic chunks as cache-marked text blocks.

    research(2026-05): Anthropic prompt caching supports up to 4
    cache_control breakpoints per request, in increasing prefix order.
    Splitting truly-static from player-dynamic chunks keeps the static
    block always-cacheable while the dynamic block resets only on player
    state shifts. Source:
    platform.claude.com/docs/en/build-with-claude/prompt-caching.
    """

    def test_single_chunk_yields_one_block_with_1h_ttl(self):
        from kourai_common.llm import cached_text_blocks

        # Default static_ttl="1h" — the first (truly-static) block opts into
        # the 1h TTL because Forge Party sessions routinely span >5min.
        out = cached_text_blocks("static prompt only")
        assert out == [
            {
                "type": "text",
                "text": "static prompt only",
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ]

    def test_two_chunks_split_ttls_static_1h_dynamic_5m(self):
        from kourai_common.llm import cached_text_blocks

        out = cached_text_blocks("static", "dynamic")
        assert len(out) == 2
        assert out[0]["text"] == "static"
        assert out[1]["text"] == "dynamic"
        # Block 0 (static) — 1h TTL because it's truly static for the session.
        assert out[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        # Block 1 (dynamic) — 5min default because it churns sub-hourly anyway.
        assert out[1]["cache_control"] == {"type": "ephemeral"}

    def test_empty_chunks_dropped(self):
        from kourai_common.llm import cached_text_blocks

        out = cached_text_blocks("static", "", "dynamic", "")
        assert len(out) == 2
        assert out[0]["text"] == "static"
        assert out[1]["text"] == "dynamic"

    def test_first_nonempty_chunk_gets_1h_ttl_when_leading_chunks_empty(self):
        """If callers pass empty leading chunks (common when an optional
        static suffix is unset), the FIRST NON-EMPTY chunk still gets the 1h
        TTL — not the literal first array index."""
        from kourai_common.llm import cached_text_blocks

        out = cached_text_blocks("", "actually static", "dynamic")
        assert len(out) == 2
        assert out[0]["text"] == "actually static"
        assert out[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert out[1]["cache_control"] == {"type": "ephemeral"}

    def test_no_chunks_yields_empty_list(self):
        from kourai_common.llm import cached_text_blocks

        assert cached_text_blocks() == []

    def test_all_empty_chunks_yields_empty_list(self):
        from kourai_common.llm import cached_text_blocks

        assert cached_text_blocks("", "", "") == []

    def test_static_ttl_5m_override_disables_1h_upgrade(self):
        """Pass static_ttl="5m" to opt out of the 1h default — both blocks
        use the 5min default. For tests / call sites where the 5min behavior
        is genuinely correct (e.g., short-lived auxiliary calls)."""
        from kourai_common.llm import cached_text_blocks

        out = cached_text_blocks("static", "dynamic", static_ttl="5m")
        assert out[0]["cache_control"] == {"type": "ephemeral"}
        assert out[1]["cache_control"] == {"type": "ephemeral"}


class TestBuildContextualMessagesCacheStructure:
    """Verify _build_contextual_messages places semantic_summary in its own
    cache-control block so the static system prefix stays cacheable across
    Mneme summarizations.

    research(2026-05): Anthropic prompt caching cuts cost by up to 90 % on
    repeat turns. Pre-2026-05-06 shape concatenated the dynamic summary onto
    the static system content as a string — every summarization invalidated
    the entire prefix. The fix splits the system content into two
    cache_control text blocks; only the summary block resets when the
    summary changes.
    """

    @pytest.mark.asyncio
    async def test_summary_present_yields_two_cache_blocks(self):
        from kourai_common.llm import _build_contextual_messages

        with (
            patch("kourai_common.llm._manage_memory", new=AsyncMock(return_value=0)),
            patch(
                "kourai_common.llm.get_agent_state",
                return_value={"semantic_summary": "prior context"},
            ),
            patch("kourai_common.llm.get_unsummarized_messages", return_value=[]),
            patch("kourai_common.llm.add_message"),
        ):
            out = await _build_contextual_messages(
                "metis",
                [
                    {"role": "system", "content": "static maiden personality"},
                    {"role": "user", "content": "hi"},
                ],
                "ctx-1",
            )
        # System content is now a list of two cache-marked text blocks.
        sys_content = out[0]["content"]
        assert isinstance(sys_content, list)
        assert len(sys_content) == 2
        # Block 0 = static prefix, block 1 = dynamic summary, both cached.
        assert sys_content[0]["text"] == "static maiden personality"
        assert sys_content[0]["cache_control"] == {"type": "ephemeral"}
        assert "prior context" in sys_content[1]["text"]
        assert sys_content[1]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_no_summary_leaves_system_content_string(self):
        """Without a summary, the system stays a plain string so the existing
        single-block _mark_system_cacheable path still adds one breakpoint
        downstream — no behavior change for new sessions."""
        from kourai_common.llm import _build_contextual_messages

        with (
            patch("kourai_common.llm._manage_memory", new=AsyncMock(return_value=0)),
            patch(
                "kourai_common.llm.get_agent_state",
                return_value={"semantic_summary": ""},
            ),
            patch("kourai_common.llm.get_unsummarized_messages", return_value=[]),
            patch("kourai_common.llm.add_message"),
        ):
            out = await _build_contextual_messages(
                "metis",
                [
                    {"role": "system", "content": "static maiden personality"},
                    {"role": "user", "content": "hi"},
                ],
                "ctx-1",
            )
        # No summary → system stays a string. _mark_system_cacheable
        # downstream wraps it into a single-block list.
        assert out[0]["content"] == "static maiden personality"

    @pytest.mark.asyncio
    async def test_no_context_id_returns_messages_unchanged(self):
        """No context_id (e.g., one-off ad-hoc call) bypasses memory entirely;
        no summary injection, no cache structure change."""
        from kourai_common.llm import _build_contextual_messages

        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "ad-hoc"},
        ]
        out = await _build_contextual_messages("metis", msgs, None)
        # Same content references; nothing got wrapped.
        assert out[0]["content"] == "sys"
        assert out[1]["content"] == "ad-hoc"

    @pytest.mark.asyncio
    async def test_summary_block_text_is_self_describing(self):
        """The summary block's text carries the SEMANTIC MEMORY header so a
        debugging human reading a request payload can spot what the block is."""
        from kourai_common.llm import _build_contextual_messages

        with (
            patch("kourai_common.llm._manage_memory", new=AsyncMock(return_value=0)),
            patch(
                "kourai_common.llm.get_agent_state",
                return_value={"semantic_summary": "prior context"},
            ),
            patch("kourai_common.llm.get_unsummarized_messages", return_value=[]),
            patch("kourai_common.llm.add_message"),
        ):
            out = await _build_contextual_messages(
                "metis",
                [{"role": "system", "content": "sys"}],
                "ctx-1",
            )
        block_text = out[0]["content"][1]["text"]
        assert "SEMANTIC MEMORY" in block_text
        assert "PREVIOUS CONTEXT" in block_text

    @pytest.mark.asyncio
    async def test_static_block_unchanged_when_summary_changes(self):
        """The whole point: vary the summary, the static block stays bytewise
        identical so the prefix-cache machinery hits the static block on
        every call regardless of summary churn."""
        from kourai_common.llm import _build_contextual_messages

        async def _build_with_summary(summary: str):
            with (
                patch("kourai_common.llm._manage_memory", new=AsyncMock(return_value=0)),
                patch(
                    "kourai_common.llm.get_agent_state",
                    return_value={"semantic_summary": summary},
                ),
                patch("kourai_common.llm.get_unsummarized_messages", return_value=[]),
                patch("kourai_common.llm.add_message"),
            ):
                return await _build_contextual_messages(
                    "metis",
                    [{"role": "system", "content": "STATIC PERSONALITY"}],
                    "ctx-1",
                )

        out_a = await _build_with_summary("summary version A")
        out_b = await _build_with_summary("summary version B")
        # Static block (index 0) must be byte-identical across summaries.
        assert out_a[0]["content"][0]["text"] == out_b[0]["content"][0]["text"]
        # Summary block (index 1) must differ.
        assert out_a[0]["content"][1]["text"] != out_b[0]["content"][1]["text"]

    @pytest.mark.asyncio
    async def test_list_content_summary_appended_as_third_block(self):
        """When the caller pre-supplies cache-marked blocks (truly-static +
        player-dynamic), the summary block APPENDS to that list rather than
        replacing it — yielding three breakpoints (static / dynamic / summary)
        that all chain through the prefix-cache.

        This is the post-#177 follow-on path: get_enriched_system_blocks
        returns a list[dict]; _build_contextual_messages must preserve the
        upstream split rather than collapsing it back into a string."""
        from kourai_common.llm import _build_contextual_messages, cached_text_blocks

        upstream_blocks = cached_text_blocks(
            "TRULY STATIC SYSTEM PROMPT",
            "PLAYER DYNAMIC CONTEXT (memories + alignment)",
        )
        with (
            patch("kourai_common.llm._manage_memory", new=AsyncMock(return_value=0)),
            patch(
                "kourai_common.llm.get_agent_state",
                return_value={"semantic_summary": "summary text"},
            ),
            patch("kourai_common.llm.get_unsummarized_messages", return_value=[]),
            patch("kourai_common.llm.add_message"),
        ):
            out = await _build_contextual_messages(
                "metis",
                [{"role": "system", "content": upstream_blocks}],
                "ctx-1",
            )
        sys_content = out[0]["content"]
        assert isinstance(sys_content, list)
        assert len(sys_content) == 3
        # Original two blocks preserved bytewise.
        assert sys_content[0]["text"] == "TRULY STATIC SYSTEM PROMPT"
        assert sys_content[1]["text"] == "PLAYER DYNAMIC CONTEXT (memories + alignment)"
        # Summary appended as the third block, with its own breakpoint.
        assert "summary text" in sys_content[2]["text"]
        assert sys_content[2]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_list_content_no_summary_left_alone(self):
        """When the caller supplies cache-marked blocks AND there's no summary,
        the system content stays exactly as the caller provided it. No mutation,
        no re-wrapping — the upstream cache structure passes through cleanly."""
        from kourai_common.llm import _build_contextual_messages, cached_text_blocks

        upstream_blocks = cached_text_blocks("STATIC", "DYNAMIC")
        with (
            patch("kourai_common.llm._manage_memory", new=AsyncMock(return_value=0)),
            patch(
                "kourai_common.llm.get_agent_state",
                return_value={"semantic_summary": ""},
            ),
            patch("kourai_common.llm.get_unsummarized_messages", return_value=[]),
            patch("kourai_common.llm.add_message"),
        ):
            out = await _build_contextual_messages(
                "metis",
                [{"role": "system", "content": upstream_blocks}],
                "ctx-1",
            )
        # Unchanged: caller's two blocks pass through.
        assert out[0]["content"] == upstream_blocks


class TestLogCacheUsage:
    """_log_cache_usage emits a debug line only when real cache numbers exist."""

    def test_logs_cache_read_and_write(self, caplog):
        import logging

        from kourai_common.llm import _log_cache_usage

        usage = MagicMock()
        usage.prompt_tokens_details.cached_tokens = 1500
        usage.cache_creation_input_tokens = 0
        response = MagicMock(usage=usage)
        with caplog.at_level(logging.DEBUG, logger="kourai_common.llm"):
            _log_cache_usage("techne", response)
        assert any("cache techne read=1500 write=0" in r.message for r in caplog.records)

    def test_silent_when_no_usage_attr(self, caplog):
        import logging

        from kourai_common.llm import _log_cache_usage

        with caplog.at_level(logging.DEBUG, logger="kourai_common.llm"):
            _log_cache_usage("techne", MagicMock(usage=None))
        assert not any("cache" in r.message for r in caplog.records)

    def test_silent_when_counts_are_not_ints(self, caplog):
        """MagicMock attribute access returns a Mock, which must NOT log."""
        import logging

        from kourai_common.llm import _log_cache_usage

        with caplog.at_level(logging.DEBUG, logger="kourai_common.llm"):
            _log_cache_usage("techne", MagicMock())
        assert not any("cache techne" in r.message for r in caplog.records)


class TestChatWithToolsCachesPrefix:
    """Integration: chat_with_tools must hand cache-marked prefix to LiteLLM."""

    @pytest.mark.asyncio
    async def test_marks_system_user_and_last_tool(self):
        seen_kwargs: dict = {}

        async def _capture(timeout_seconds, **kwargs):
            seen_kwargs.update(kwargs)
            return _mk_response(text="done")

        messages = [
            {"role": "system", "content": "you are techne"},
            {"role": "user", "content": "make a file"},
        ]
        tools = [
            {"type": "function", "function": {"name": "write_file"}},
            {"type": "function", "function": {"name": "edit_file"}},
        ]
        with (
            patch("kourai_common.llm._execute_completion", new=_capture),
            patch(
                "kourai_common.llm._build_contextual_messages",
                new_callable=AsyncMock,
                return_value=list(messages),
            ),
        ):
            from kourai_common.llm import chat_with_tools

            await chat_with_tools("techne", messages, tools=tools, tool_handlers={})

        sent_messages = seen_kwargs["messages"]
        assert sent_messages[0]["content"] == [
            {
                "type": "text",
                "text": "you are techne",
                "cache_control": {"type": "ephemeral"},
            }
        ]
        assert sent_messages[1]["content"] == [
            {
                "type": "text",
                "text": "make a file",
                "cache_control": {"type": "ephemeral"},
            }
        ]
        sent_tools = seen_kwargs["tools"]
        assert sent_tools[0]["function"] == {"name": "write_file"}
        assert sent_tools[1]["function"] == {
            "name": "edit_file",
            "cache_control": {"type": "ephemeral"},
        }


class TestExecuteCompletionForwardsRequestTimeout:
    """Regression-guard for the `request_timeout=` kwarg on the LiteLLM call.

    Without this, the only deadline enforcement is the outer
    `asyncio.timeout(...)` wrapper — which works for normal request
    completion paths but doesn't always cancel a stuck TCP connect
    cleanly on older aiohttp transports. Forwarding the deadline as
    `request_timeout` propagates into LiteLLM's httpx/aiohttp transport
    so the connect-stage failure surfaces as a real Timeout instead of
    burning the whole 120s budget on each retry attempt.
    """

    @pytest.mark.asyncio
    async def test_request_timeout_passed_to_acompletion(self):
        from kourai_common.llm import _execute_completion

        seen_kwargs: dict = {}

        async def _fake_acompletion(**kwargs):
            seen_kwargs.update(kwargs)
            return MagicMock()

        with patch("kourai_common.llm.litellm.acompletion", side_effect=_fake_acompletion):
            await _execute_completion(
                timeout_seconds=42.0,
                model="anthropic/claude-haiku-4-5-20251001",
                messages=[{"role": "user", "content": "hi"}],
            )

        assert seen_kwargs["request_timeout"] == 42.0

    @pytest.mark.asyncio
    async def test_request_timeout_does_not_clobber_explicit_caller_value(self):
        """`setdefault` semantics — if a caller passes their own
        `request_timeout`, the wrapper respects it. Future-proofs against
        callers (e.g. a streaming-aware path) that want a tighter
        first-chunk deadline than the agent-level timeout.
        """
        from kourai_common.llm import _execute_completion

        seen_kwargs: dict = {}

        async def _fake_acompletion(**kwargs):
            seen_kwargs.update(kwargs)
            return MagicMock()

        with patch("kourai_common.llm.litellm.acompletion", side_effect=_fake_acompletion):
            await _execute_completion(
                timeout_seconds=120.0,
                model="anthropic/claude-haiku-4-5-20251001",
                messages=[{"role": "user", "content": "hi"}],
                request_timeout=15.0,
            )

        assert seen_kwargs["request_timeout"] == 15.0
