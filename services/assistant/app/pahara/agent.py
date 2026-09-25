"""পাহারা — the watch.

An agent that reads the cluster's own telemetry and says what happened. It is
given the three signals and nothing else: it can search traces, read one,
search logs and query metrics. It cannot restart a pod, scale a deployment or
change a config, for the same reason the shopping assistant can fill a cart
but not pay for it. Investigating is a model's job; deciding what to do about
it is not.

What makes an answer here useful rather than plausible is evidence. A model
asked why checkout is slow will happily write a paragraph about database
contention having looked at nothing. So the prompt insists on citation — a
trace id, a log line, a number — and the tools return identifiers precisely so
that a claim can be checked against the thing it came from.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.llm import Provider, ToolResult, ToolSpec
from app.pahara.observatory import Observatory, Unreachable

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Pahara, the watch over the Poshra cluster. পাহারা means
the keeping of watch.

You answer questions about what the system is doing by reading its telemetry:
traces in Tempo, logs in Loki, metrics in Prometheus. You have read-only access
and no way to change anything, which is deliberate — say what you found and
what you would check next, never what you have done.

The services are kong (the gateway), web (Next.js), marketplace (Django, the
catalogue and accounts), checkout (Go, orders and payment), inventory (Go, the
single authority on stock), assistant (the shopping assistant and you), and
sales-consumer (the artisan sales read model). Orders travel from checkout
through a transactional outbox into Kafka, and are consumed by inventory and by
the sales consumer.

How to work:

- Look before you answer. A guess that sounds like an explanation is worse
  than "I could not find it", because it sends somebody to fix the wrong thing.
- Cite what you looked at. Name the trace id, quote the log line, give the
  number. Every claim in your answer must be traceable to something a person
  can open.
- Start wide, then narrow. Metrics say whether it is one service or all of
  them; a trace says where the time went inside one request; logs say what the
  service thought it was doing.
- Say how confident you are, and say plainly when the telemetry does not
  answer the question. "The traces do not show this" is a useful answer.
- Be brief. An operator reading you is already having a bad morning.
- An empty result is not an answer. No lines matched usually means the label
  or the window was wrong, not that nothing happened — read what the tool says
  about it and change the query rather than asking the same thing again.

Useful queries:

- TraceQL: `{ resource.service.name = "checkout" && duration > 1s }`,
  `{ status = error }`, `{ span.http.route = "/orders" }`
- LogQL: `{service_name="checkout"} | json | level="ERROR"`,
  `{k8s_namespace_name="poshra"} |= "traceparent"`
- PromQL: RED metrics are derived from spans —
  `sum by (service) (rate(traces_spanmetrics_calls_total{span_kind="SPAN_KIND_SERVER"}[5m]))`,
  and the business counters are `poshra_orders_total` and
  `poshra_orders_value_total`.

Log lines carry the trace id, so a log line and a trace can always be joined."""

FIND_TRACES = ToolSpec(
    name="find_traces",
    description=(
        "Search traces with TraceQL and get back their ids and durations. Use this "
        "first when asked about slowness or errors in requests. Returns the matching "
        "traces, not their contents."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    'TraceQL, e.g. { resource.service.name = "checkout" && duration > 1s } '
                    "or { status = error }."
                ),
            },
            "limit": {"type": "integer", "description": "How many traces, at most 20."},
        },
        "required": ["query"],
    },
)

READ_TRACE = ToolSpec(
    name="read_trace",
    description=(
        "Read one trace: its spans, slowest first, with the service and operation for "
        "each. This is how you find where the time actually went inside a request."
    ),
    parameters={
        "type": "object",
        "properties": {"trace_id": {"type": "string", "description": "From find_traces."}},
        "required": ["trace_id"],
    },
)

SEARCH_LOGS = ToolSpec(
    name="search_logs",
    description=(
        "Search logs with LogQL. Lines from this cluster's own services are JSON and "
        "carry a trace id, so a log line can be joined to a trace."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": '{service_name="checkout"} | json | level="ERROR"',
            },
            "since": {
                "type": "string",
                "description": "A window such as 15m, 1h, 6h. Without one there are no results.",
            },
            "limit": {"type": "integer", "description": "Lines, at most 40."},
        },
        "required": ["query"],
    },
)

QUERY_METRICS = ToolSpec(
    name="query_metrics",
    description=(
        "Run an instant PromQL query. Use this to tell one service's problem from "
        "everyone's, and to see rates rather than single requests."
    ),
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "PromQL."}},
        "required": ["query"],
    },
)

TOOLS = [FIND_TRACES, READ_TRACE, SEARCH_LOGS, QUERY_METRICS]

# Looking costs nothing but time; the model calling itself in circles costs
# both. Higher than the shopper's budget because an investigation legitimately
# takes more steps than a search.
MAX_LOOKS = 10

RAN_LONG = (
    "I ran out of time before I could finish looking. What I found is above; "
    "ask me again and I will carry on from there."
)

LOOKED_ENOUGH = (
    "I have looked at as much as I am allowed to in one go without reaching a "
    "conclusion. Narrow the question — a service, or a window — and ask again."
)


class Pahara:
    def __init__(
        self,
        provider: Provider,
        observatory: Observatory,
        *,
        max_looks: int = MAX_LOOKS,
        budget: float = 60.0,
    ) -> None:
        self._provider = provider
        self._observatory = observatory
        self._max_looks = max_looks
        self._budget = budget

    async def explain(self, question: str) -> dict[str, Any]:
        conversation = self._provider.start(
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=[{"role": "user", "content": question}],
        )

        looks = 0
        # What it opened, in order. Returned with the answer so a reader can
        # follow the same path — and so an answer citing nothing is obvious.
        looked_at: list[dict[str, Any]] = []
        # And what it has already opened. A model that gets an empty result
        # tends to ask the same thing again in slightly different words; the
        # first real investigation spent four of its ten looks that way.
        already: dict[str, Any] = {}

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._budget

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return self._answer(RAN_LONG, looked_at, looks)

            try:
                turn = await asyncio.wait_for(conversation.next_turn(), timeout=remaining)
            except TimeoutError:
                log.warning("pahara ran out of time", extra={"looks": looks})
                return self._answer(RAN_LONG, looked_at, looks)

            if not turn.wants_tools:
                return self._answer(turn.text, looked_at, looks)

            wanted = list(turn.tool_calls)
            if looks + len(wanted) > self._max_looks:
                return self._answer(LOOKED_ENOUGH, looked_at, looks)
            looks += len(wanted)

            outputs = await asyncio.gather(
                *(self._look(call.name, call.arguments, looked_at, already) for call in wanted)
            )
            conversation.add_tool_results(
                [
                    ToolResult(call=call, content=output)
                    for call, output in zip(wanted, outputs, strict=True)
                ]
            )

    def _answer(self, text: str, looked_at: list[dict[str, Any]], looks: int) -> dict[str, Any]:
        return {"answer": text, "looked_at": looked_at, "looks": looks}

    async def _look(
        self,
        name: str,
        arguments: Any,
        looked_at: list[dict[str, Any]],
        already: dict[str, Any],
    ) -> Any:
        arguments = arguments if isinstance(arguments, dict) else {}
        looked_at.append({"tool": name, **{k: v for k, v in arguments.items() if k != "limit"}})

        # Asking the same question twice cannot produce a different answer, and
        # the budget it spends is the budget that would have reached one.
        fingerprint = f"{name}:{sorted(arguments.items())}"
        if fingerprint in already:
            return {
                "already_asked": (
                    "You ran this exact query earlier in this investigation and got the "
                    "result below. Asking again will not change it — try a different "
                    "label, a wider window, or a different signal."
                ),
                "previous_result": already[fingerprint],
            }

        try:
            result: Any
            if name == "find_traces":
                result = {
                    "traces": await self._observatory.find_traces(
                        str(arguments.get("query", "")),
                        int(arguments.get("limit") or 8),
                    )
                }
            elif name == "read_trace":
                result = await self._observatory.read_trace(str(arguments.get("trace_id", "")))
            elif name == "search_logs":
                result = await self._observatory.search_logs(
                    str(arguments.get("query", "")),
                    since=str(arguments.get("since") or "1h"),
                    limit=int(arguments.get("limit") or 20),
                )
            elif name == "query_metrics":
                result = await self._observatory.query_metrics(str(arguments.get("query", "")))
            else:
                return {"error": f"there is no tool called {name}."}

            already[fingerprint] = result
            return result
        except Unreachable as error:
            # Handed back rather than raised: a rejected query is usually a
            # syntax error the model can fix, and a backend that is down is
            # itself worth reporting rather than hiding behind a 500.
            log.warning("a look failed", extra={"tool": name, "error": str(error)})
            return {"error": f"that query did not work: {error}"}
        except Exception as error:  # noqa: BLE001
            log.error("a look broke", extra={"tool": name, "error": str(error)})
            return {"error": "that query could not be run."}
