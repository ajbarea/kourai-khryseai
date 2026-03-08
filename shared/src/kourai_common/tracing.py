"""OpenTelemetry tracing for Kourai Khryseai agents."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_tracer: trace.Tracer | None = None


def setup_tracing(
    service_name: str,
    otlp_endpoint: str | None = None,
) -> TracerProvider:
    """Initialize OTEL tracing. Call once at agent startup.

    Args:
        service_name: Agent name (e.g., "metis", "hephaestus").
        otlp_endpoint: OTLP HTTP endpoint (e.g., "http://localhost:4318").

    Returns:
        The configured TracerProvider.
    """
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )
    provider = TracerProvider(resource=resource)

    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    try:
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception as e:
        # Jaeger may not be running — tracing is optional
        import logging

        logging.getLogger(__name__).warning("OTEL exporter setup failed (tracing disabled): %s", e)

    trace.set_tracer_provider(provider)

    global _tracer
    _tracer = trace.get_tracer(f"kourai.{service_name}")

    return provider


def get_tracer() -> trace.Tracer:
    """Get the initialized tracer."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("kourai")
    return _tracer


@contextmanager
def create_span(
    name: str,
    attributes: dict[str, str] | None = None,
) -> Generator[trace.Span, None, None]:
    """Create an OTEL span with optional attributes.

    Args:
        name: Span name (e.g., "metis.execute", "a2a.send.techne").
        attributes: Key-value span attributes for filtering in Jaeger.
    """
    with get_tracer().start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise


def get_trace_context() -> dict[str, str]:
    """Extract current trace context for propagation via A2A message metadata."""
    headers: dict[str, str] = {}
    inject(headers)
    return headers


def extract_trace_context(headers: dict[str, str]) -> Context:
    """Restore trace context from incoming A2A message metadata."""
    return extract(headers)
