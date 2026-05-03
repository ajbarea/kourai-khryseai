"""Unit tests for kourai_common.ssml.strip_ssml.

Specialists emit SSML; this module strips for engines (Kokoro) that
don't speak it. Tests cover the portable subset (`break`, `prosody`,
`emphasis`, `say-as`), malformed input recovery, and the no-op fast
path for plain text.
"""

from __future__ import annotations

from kourai_common.ssml import strip_ssml


class TestStripSsmlNoOp:
    def test_empty_string(self) -> None:
        assert strip_ssml("") == ""

    def test_whitespace_only(self) -> None:
        assert strip_ssml("   ") == "   "

    def test_plain_text_passes_through(self) -> None:
        assert strip_ssml("hello world") == "hello world"

    def test_text_with_lt_but_no_tag_passes_through(self) -> None:
        # `<` outside a tag is not SSML — fast path skips parsing.
        assert strip_ssml("3 < 5") == "3 < 5"


class TestStripSsmlSpeakWrapper:
    def test_bare_speak_wrapper(self) -> None:
        assert strip_ssml("<speak>hello world</speak>") == "hello world"

    def test_speak_with_attrs(self) -> None:
        ssml = '<speak version="1.1" xml:lang="en-US">hello world</speak>'
        assert strip_ssml(ssml) == "hello world"

    def test_speak_with_namespace(self) -> None:
        ssml = '<speak xmlns="http://www.w3.org/2001/10/synthesis">hi</speak>'
        assert strip_ssml(ssml) == "hi"


class TestStripSsmlPortableSubset:
    def test_break_self_closing_creates_whitespace(self) -> None:
        ssml = '<speak>first<break time="200ms"/>second</speak>'
        # Break tag injects a space so sentences don't run together.
        assert strip_ssml(ssml) == "first second"

    def test_break_open_close_creates_whitespace(self) -> None:
        ssml = "<speak>one<break></break>two</speak>"
        assert strip_ssml(ssml) == "one two"

    def test_emphasis_preserves_content(self) -> None:
        # Adjacent punctuation stays glued — emphasis is a content tag,
        # not a whitespace tag like break/p/s.
        ssml = '<speak>This is <emphasis level="strong">important</emphasis>.</speak>'
        assert strip_ssml(ssml) == "This is important."

    def test_prosody_preserves_content(self) -> None:
        ssml = '<speak><prosody rate="slow" pitch="low">heavy words</prosody></speak>'
        assert strip_ssml(ssml) == "heavy words"

    def test_say_as_preserves_content(self) -> None:
        ssml = '<speak>Call <say-as interpret-as="telephone">555-1234</say-as></speak>'
        assert strip_ssml(ssml) == "Call 555-1234"

    def test_nested_tags(self) -> None:
        ssml = (
            "<speak>"
            '<prosody rate="slow">'
            'I said <emphasis level="strong">no</emphasis> already'
            "</prosody>"
            "</speak>"
        )
        assert strip_ssml(ssml) == "I said no already"

    def test_p_and_s_inject_whitespace(self) -> None:
        ssml = "<speak><p>First paragraph.</p><p>Second paragraph.</p></speak>"
        assert strip_ssml(ssml) == "First paragraph. Second paragraph."


class TestStripSsmlBareFragment:
    def test_bare_fragment_wrapped_implicitly(self) -> None:
        # Producers may emit raw SSML without the <speak> root.
        assert strip_ssml('hello <break time="100ms"/> world') == "hello world"

    def test_bare_fragment_with_emphasis(self) -> None:
        assert strip_ssml("hello <emphasis>world</emphasis>") == "hello world"


class TestStripSsmlMalformed:
    def test_unclosed_tag_falls_back_to_regex(self) -> None:
        # `<speak>hello <emphasis>world</speak>` — emphasis never closes.
        ssml = "<speak>hello <emphasis>world</speak>"
        result = strip_ssml(ssml)
        # Regex strip: every `<...>` removed, content preserved.
        assert "hello" in result and "world" in result
        assert "<" not in result and ">" not in result

    def test_garbage_input_does_not_raise(self) -> None:
        # Producer bug shouldn't kill TTS — return *something* feedable.
        result = strip_ssml("<<<not valid >>>")
        assert isinstance(result, str)


class TestStripSsmlWhitespaceCollapse:
    def test_inner_whitespace_collapsed(self) -> None:
        ssml = "<speak>hello\n\n\tworld</speak>"
        assert strip_ssml(ssml) == "hello world"

    def test_leading_trailing_whitespace_stripped(self) -> None:
        ssml = "<speak>   padded   </speak>"
        assert strip_ssml(ssml) == "padded"
