"""Wiring this service into the collector.

Mirrors what the Go services do, because the point is that they agree: the same
W3C trace context, so a trace that starts in a Go service and ends in this one
is a single story rather than two.

Nothing here fails a start-up. A service that will not run because it cannot
reach its telemetry backend has made observability a dependency of serving
traffic, which is exactly backwards.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def configure_tracing(service: str) -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        log.info("tracing is off", extra={"reason": "OTEL_EXPORTER_OTLP_ENDPOINT unset"})
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

        # Every query becomes a span inside whatever caused it, the same as the
        # Go services do with pgx.
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

        PsycopgInstrumentor().instrument(enable_commenter=False)

        log.info("tracing on", extra={"service": service, "collector": endpoint})
    except Exception as error:  # noqa: BLE001 — telemetry must not stop the service
        log.error("could not start tracing", extra={"error": str(error)})
