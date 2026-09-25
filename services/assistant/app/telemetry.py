"""Wiring this service into the collector.

The same shape as the marketplace's, deliberately: the same W3C trace context,
so a shopper's question that starts at the gateway and ends in the catalog is
one story rather than three.

This service is the one worth seeing. It is the slowest thing in the cluster
and the only part that costs money per request, and until now it was the only
part with no telemetry at all — a thirty-second span at the gateway with
nothing inside it.

Nothing here fails a start-up. A service that will not run because it cannot
reach its telemetry backend has made observability a dependency of serving
traffic, which is exactly backwards.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# Asked every few seconds by kubelet, and they touch nothing.
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

        # Every outbound call becomes a span: the catalog, checkout — and the
        # model. The model's URL carries the model's name, so which one
        # answered, how long it took and whether it refused are all in the
        # trace without anything here having to say so.
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

        if app is not None:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app, excluded_urls=UNTRACED)

        log.info("tracing on", extra={"service": service, "collector": endpoint})
    except Exception as error:  # noqa: BLE001 — telemetry must not stop the service
        log.error("could not start tracing", extra={"error": str(error)})


def tracer():
    """The tracer for hand-made spans. Safe before configure_tracing has run."""
    from opentelemetry import trace

    return trace.get_tracer("poshra.assistant")
