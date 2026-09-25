"""That a turn is a span, and that it says what the turn did.

The question this service gets asked is "why did that take thirty seconds",
and the answer is always some combination of how many tools it called and
which model answered. Both belong on the span; neither is guessable from a
duration.
"""

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.main import app
from tests.test_http import CONFIG, StubAssistant, StubDrafter


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous = trace.get_tracer_provider()
    trace._TRACER_PROVIDER = provider  # noqa: SLF001 — the only way back afterwards

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CATALOG_URL", CONFIG.catalog_url)
    monkeypatch.setenv("CHECKOUT_URL", CONFIG.checkout_url)

    with TestClient(app, raise_server_exceptions=False) as client:
        app.state.assistant = StubAssistant()
        app.state.drafter = StubDrafter()
        yield client, exporter

    trace._TRACER_PROVIDER = previous  # noqa: SLF001


def named(exporter, name):
    return [span for span in exporter.get_finished_spans() if span.name == name]


def test_a_turn_carries_what_it_cost(spans):
    client, exporter = spans

    client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "show me a kantha"}]},
        headers={"X-User-Id": "user-1"},
    )

    turn = named(exporter, "assistant.turn")
    assert turn, "the turn produced no span"
    assert turn[0].attributes["poshra.tool_calls"] == 1
    assert turn[0].attributes["poshra.checkout_ready"] is False


def test_a_draft_says_what_it_was_given(spans):
    client, exporter = spans

    client.post(
        "/draft-listing",
        data={"notes": "পাটের পাটি"},
        files={"voice": ("note.webm", b"\x1aE\xdf\xa3", "audio/webm;codecs=opus")},
        headers={"X-User-Id": "artisan-1"},
    )

    draft = named(exporter, "assistant.draft_listing")
    assert draft, "the draft produced no span"
    # A photograph and a recording are most of what a draft costs and most of
    # how long it takes, so the span has to say which arrived.
    assert draft[0].attributes["poshra.had_voice"] is True
    assert draft[0].attributes["poshra.had_photo"] is False
    assert draft[0].attributes["poshra.confidence"] == "high"
