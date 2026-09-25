"""Pahara, without a cluster and without a model.

The backends answer from recorded shapes — taken from the real Tempo, Loki and
Prometheus rather than imagined — and the model is a script. What is asserted
is the part that decides whether an answer is worth anything: that it looked,
and that what it looked at comes back with the answer.
"""

import httpx
import pytest

from app.llm import ToolCall, Turn
from app.pahara.agent import LOOKED_ENOUGH, Pahara
from app.pahara.observatory import Observatory, Unreachable

TEMPO, LOKI, PROM = "http://tempo:3200", "http://loki:3100", "http://prom:9090"

# As Tempo answers /api/search. The field names are its, not ours.
SEARCH = {
    "traces": [
        {
            "traceID": "28f5027fec0a53d5",
            "rootServiceName": "kong",
            "rootTraceName": "kong",
            "durationMs": 930,
            "startTimeUnixNano": "1790000000000000000",
        }
    ],
    "metrics": {},
}

# As Tempo answers /api/traces/<id>: OTLP batches, not a flat list.
TRACE = {
    "batches": [
        {
            "resource": {
                "attributes": [{"key": "service.name", "value": {"stringValue": "checkout"}}]
            },
            "scopeSpans": [
                {
                    "spans": [
                        {
                            "name": "POST /orders",
                            "startTimeUnixNano": "1000000000",
                            "endTimeUnixNano": "1900000000",
                            "status": {},
                        },
                        {
                            "name": "charge",
                            "startTimeUnixNano": "1100000000",
                            "endTimeUnixNano": "1800000000",
                            "status": {"code": 2},
                        },
                    ]
                }
            ],
        }
    ]
}

LOGS = {
    "status": "success",
    "data": {
        "result": [
            {
                "stream": {"service_name": "checkout"},
                "values": [["1790000000000000000", '{"level":"ERROR","msg":"charge failed"}']],
            }
        ]
    },
}

METRICS = {
    "data": {
        "result": [
            {"metric": {"__name__": "up", "service": "checkout"}, "value": [1790000000, "0.42"]},
            {"metric": {"__name__": "up", "service": "inventory"}, "value": [1790000000, "0.01"]},
        ]
    }
}


def backends(handler=None):
    def route(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/search":
            return httpx.Response(200, json=SEARCH)
        if path.startswith("/api/traces/"):
            return httpx.Response(200, json=TRACE)
        if path.startswith("/loki/"):
            return httpx.Response(200, json=LOGS)
        if path.startswith("/api/v1/query"):
            return httpx.Response(200, json=METRICS)
        return httpx.Response(404, text="no such thing")

    return httpx.MockTransport(handler or route)


@pytest.fixture
def observatory(monkeypatch, request):
    transport = getattr(request, "param", None) or backends()
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        return real(*args, **{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx, "AsyncClient", client)
    return Observatory(TEMPO, LOKI, PROM, timeout=5.0)


# --- what it is allowed to see ------------------------------------------------


async def test_a_trace_comes_back_slowest_span_first(observatory):
    read = await observatory.read_trace("28f5027fec0a53d5")

    # The question asked of a trace is "what took the time", and a span list in
    # start order buries the answer in the middle.
    assert [span["name"] for span in read["slowest"]] == ["POST /orders", "charge"]
    assert read["slowest"][0]["ms"] == 900.0
    assert read["slowest"][0]["service"] == "checkout"
    # Only the failing span is marked, so an unset status is not noise on every
    # line the model has to read past.
    assert "status" not in read["slowest"][0]
    assert read["slowest"][1]["status"] == "error"


async def test_metrics_keep_their_labels(observatory):
    read = await observatory.query_metrics("up")

    # One service at 42% and another at 1% is a different incident from both at
    # 20%, and only the labels say which this is.
    assert [series["labels"]["service"] for series in read["series"]] == [
        "checkout",
        "inventory",
    ]
    assert read["series"][0]["value"] == "0.42"


async def test_a_rejected_query_says_why(monkeypatch):
    refuses = backends(lambda request: httpx.Response(400, text="parse error at line 1"))
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": refuses})
    )

    with pytest.raises(Unreachable, match="parse error"):
        await Observatory(TEMPO, LOKI, PROM, 5.0).find_traces("{ nonsense")


# --- the agent ----------------------------------------------------------------


class ScriptedModel:
    def __init__(self, turns):
        self.turns = list(turns)
        self.results_seen = []

    name = "scripted"

    def start(self, *, system, tools, messages):
        self.system = system
        self.tools = tools
        return self

    async def next_turn(self):
        return self.turns.pop(0)

    def add_tool_results(self, results):
        self.results_seen.append(results)


def call(name, arguments):
    return ToolCall(name=name, arguments=arguments, id=f"{name}-0")


async def test_an_answer_carries_what_it_looked_at(observatory):
    model = ScriptedModel(
        [
            Turn(tool_calls=(call("find_traces", {"query": "{ duration > 1s }"}),)),
            Turn(tool_calls=(call("read_trace", {"trace_id": "28f5027fec0a53d5"}),)),
            Turn(text="checkout spent 900ms in charge; trace 28f5027fec0a53d5."),
        ]
    )

    answered = await Pahara(model, observatory).explain("why is checkout slow?")

    assert "28f5027fec0a53d5" in answered["answer"]
    # The trail matters as much as the answer: an explanation that cites
    # nothing should be obvious as one, and this is what makes it obvious.
    assert [step["tool"] for step in answered["looked_at"]] == ["find_traces", "read_trace"]
    assert answered["looked_at"][0]["query"] == "{ duration > 1s }"
    assert answered["looks"] == 2


# Deliberately without the healthy fixture: it patches httpx.AsyncClient too,
# and a patch on top of a patch just wraps it — the first transport still wins.
async def test_a_backend_that_refuses_is_handed_back_not_raised(monkeypatch):
    refuses = backends(lambda request: httpx.Response(500, text="tempo is down"))
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": refuses})
    )
    model = ScriptedModel(
        [
            Turn(tool_calls=(call("find_traces", {"query": "{}"}),)),
            Turn(text="Tempo would not answer, so I cannot say."),
        ]
    )

    answered = await Pahara(model, Observatory(TEMPO, LOKI, PROM, 5.0)).explain("why?")

    # The model is told what went wrong so it can say so. A 500 to the operator
    # would hide the most interesting fact available: the backend is down.
    assert "tempo is down" in str(model.results_seen[0][0].content)
    assert "cannot say" in answered["answer"]


async def test_it_stops_looking_eventually(observatory):
    model = ScriptedModel(
        [Turn(tool_calls=(call("find_traces", {"query": "{}"}),)) for _ in range(12)]
    )

    answered = await Pahara(model, observatory, max_looks=3).explain("why?")

    # Looking costs time and the model calling itself in circles costs money.
    assert answered["answer"] == LOOKED_ENOUGH
    assert answered["looks"] == 3


# --- who is allowed to ask -----------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient

    from app.pahara.main import app

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CATALOG_URL", "http://catalog")
    monkeypatch.setenv("CHECKOUT_URL", "http://checkout")
    monkeypatch.setenv("TEMPO_URL", TEMPO)
    monkeypatch.setenv("LOKI_URL", LOKI)
    monkeypatch.setenv("PROMETHEUS_URL", PROM)

    class Answers:
        async def explain(self, question):
            return {"answer": "nothing is on fire.", "looked_at": [], "looks": 0}

    with TestClient(app, raise_server_exceptions=False) as client:
        app.state.pahara = Answers()
        yield client


QUESTION = {"question": "is anything broken?"}


def test_a_signed_out_visitor_is_turned_away(api):
    assert api.post("/explain", json=QUESTION).status_code == 401


@pytest.mark.parametrize("role", ["buyer", "artisan", "", "ADMINISTRATOR"])
def test_only_an_admin_may_read_the_cluster(api, role):
    # An artisan reading their own sales is one thing; reading the traces is
    # reading what every shopper did while they were paying.
    response = api.post(
        "/explain", json=QUESTION, headers={"X-User-Id": "someone", "X-User-Role": role}
    )
    assert response.status_code == 403
    assert "admin" in response.json()["detail"]


@pytest.mark.parametrize("role", ["admin", "ADMIN", " Admin "])
def test_an_admin_may(api, role):
    response = api.post(
        "/explain", json=QUESTION, headers={"X-User-Id": "someone", "X-User-Role": role}
    )
    assert response.status_code == 200
    assert response.json()["answer"] == "nothing is on fire."
