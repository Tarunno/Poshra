"""That a request here continues the trace the gateway started.

The gap this closes was invisible from inside the service: everything worked,
the logs were right, and the trace simply stopped at Kong and resumed at a
database call nobody could attribute. These assert the two halves of the fix —
that requests are spans at all, and that they are children of what sent them.
"""

import pytest
from opentelemetry import trace
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from config.telemetry import UNTRACED

pytestmark = pytest.mark.django_db

# A traceparent as Kong sends one: version-traceid-spanid-sampled.
GATEWAY_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
GATEWAY_SPAN = "00f067aa0ba902b7"
TRACEPARENT = f"00-{GATEWAY_TRACE}-{GATEWAY_SPAN}-01"


@pytest.fixture
def spans():
    """Django instrumented for one test, and torn down again."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous = trace.get_tracer_provider()
    trace._TRACER_PROVIDER = provider  # noqa: SLF001 — the only way back afterwards

    DjangoInstrumentor().instrument(excluded_urls=UNTRACED, tracer_provider=provider)
    yield exporter
    DjangoInstrumentor().uninstrument()
    trace._TRACER_PROVIDER = previous  # noqa: SLF001


def test_a_request_continues_the_trace_the_gateway_started(client, spans):
    client.get("/crafts", headers={"traceparent": TRACEPARENT})

    recorded = spans.get_finished_spans()
    assert recorded, "the request produced no span at all"
    # The whole point: the same trace id as the gateway, not a new one. A new
    # one is two traces for one request, which is worse than none — it looks
    # like the work happened twice.
    assert f"{recorded[0].context.trace_id:032x}" == GATEWAY_TRACE
    assert f"{recorded[0].parent.span_id:016x}" == GATEWAY_SPAN


def test_the_health_checks_are_not_traced(client, spans):
    client.get("/healthz")
    client.get("/readyz")

    # kubelet asks every few seconds and the answer touches nothing. Traced,
    # these would be most of what the backend stores and none of what anyone
    # looks at.
    assert spans.get_finished_spans() == ()
