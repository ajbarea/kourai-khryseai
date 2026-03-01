"""Tracing utilities: create_span, get_tracer, context propagation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from kourai_common.tracing import (
    create_span,
    extract_trace_context,
    get_trace_context,
    get_tracer,
    setup_tracing,
)


class TestGetTracer:
    """Tracer initialization and lazy creation."""

    def test_returns_tracer(self):
        tracer = get_tracer()
        assert tracer is not None

    def test_returns_same_tracer(self):
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2


class TestCreateSpan:
    """Span creation with attributes and error recording."""

    def test_span_yields_span_object(self):
        with create_span("test.span") as span:
            assert span is not None

    def test_span_with_attributes(self):
        with create_span("test.span", {"key": "value"}) as span:
            assert span is not None

    def test_span_records_exception(self):
        with pytest.raises(ValueError, match="boom"), create_span("test.error"):
            raise ValueError("boom")


class TestTraceContext:
    """Trace context injection and extraction."""

    def test_get_trace_context_returns_dict(self):
        ctx = get_trace_context()
        assert isinstance(ctx, dict)

    def test_extract_trace_context_returns_context(self):
        ctx = extract_trace_context({"traceparent": "00-abc-def-01"})
        assert ctx is not None


class TestSetupTracing:
    """TracerProvider initialization."""

    def test_setup_returns_provider(self):
        with patch("kourai_common.tracing.BatchSpanProcessor"):
            provider = setup_tracing("test-agent")
            assert provider is not None

    def test_setup_with_custom_endpoint(self):
        with patch("kourai_common.tracing.BatchSpanProcessor"):
            provider = setup_tracing("test-agent", "http://localhost:4318")
            assert provider is not None
