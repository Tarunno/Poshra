"""Wiring this service into the collector.

Same shape as the other services', so an agent's search and the catalog query
it causes are one trace rather than two. The MCP client sends W3C trace
headers on its HTTP POST like any other caller, so the agent's turn and the
marketplace query underneath it join up without anything here saying so.

Nothing here fails a start-up: a service that will not run because it cannot
reach its telemetry backend has made observability a dependency of serving
traffic, which is backwards.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

UNTRACED = "healthz,readyz"


def configure_tracing(service: str, app=None) -> None:
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

        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

        if app is not None:
            # Starlette rather than FastAPI: the MCP transport is a Starlette
            # app, and this service has no reason to add a framework on top of
            # it just to serve one health check.
            from opentelemetry.instrumentation.starlette import StarletteInstrumentor

            StarletteInstrumentor.instrument_app(app, excluded_urls=UNTRACED)

        log.info("tracing on", extra={"service": service, "collector": endpoint})
    except Exception as error:  # noqa: BLE001 — telemetry must not stop the service
        log.error("could not start tracing", extra={"error": str(error)})
