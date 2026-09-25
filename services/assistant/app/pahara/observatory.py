"""What Pahara is allowed to look at.

Three read-only clients over the three signals. Nothing here can change
anything in the cluster: the agent can ask why a thing broke, and cannot
restart it. That is the same rule the shopping assistant follows about money —
the model investigates, a person decides what to do about it.

The queries are written by the model, which is the point: TraceQL, LogQL and
PromQL are how these questions are actually asked, and a set of fixed canned
queries would only answer the questions somebody thought of in advance.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Enough of a trace to reason about, not so much that reading it costs more
# than the incident. A trace with two thousand spans is answered by its shape.
MAX_SPANS = 60
MAX_LOG_LINES = 40
MAX_LINE_CHARS = 400


class Unreachable(RuntimeError):
    """A backend did not answer. Said plainly, because a silent empty result
    reads as 'nothing is wrong'."""


class Observatory:
    def __init__(self, tempo: str, loki: str, prometheus: str, timeout: float) -> None:
        self._tempo = tempo.rstrip("/")
        self._loki = loki.rstrip("/")
        self._prometheus = prometheus.rstrip("/")
        self._timeout = timeout
        # Fetched once, when an empty result needs explaining.
        self._known_labels: list[str] | None = None

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as error:
            # The body carries the reason a query was rejected — a TraceQL
            # syntax error, usually — and the model can correct itself if it
            # is told what was wrong rather than that something was.
            detail = error.response.text[:300]
            raise Unreachable(f"{error.response.status_code}: {detail}") from error
        except httpx.HTTPError as error:
            raise Unreachable(str(error)) from error

    async def find_traces(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """TraceQL, e.g. `{ resource.service.name = "checkout" && duration > 1s }`."""
        body = await self._get(
            f"{self._tempo}/api/search", {"q": query, "limit": max(1, min(limit, 20))}
        )
        found: list[dict[str, Any]] = []
        for trace in body.get("traces") or []:
            service = trace.get("rootServiceName", "?")
            name = trace.get("rootTraceName", "")
            found.append(
                {
                    "trace_id": trace.get("traceID"),
                    "root": f"{service} {name}".strip(),
                    "duration_ms": trace.get("durationMs"),
                    "started": trace.get("startTimeUnixNano"),
                }
            )
        if found:
            return found
        log.info("a trace search matched nothing", extra={"query": query})
        return []

    async def read_trace(self, trace_id: str) -> dict[str, Any]:
        """One trace, flattened to the spans and their durations.

        Returned sorted by duration rather than by time: the question asked of
        a trace is almost always "what took the time", and a span list in
        start order buries the answer in the middle.
        """
        body = await self._get(f"{self._tempo}/api/traces/{trace_id}", {})

        spans: list[dict[str, Any]] = []
        for batch in body.get("batches") or []:
            service = "?"
            for attribute in (batch.get("resource") or {}).get("attributes") or []:
                if attribute.get("key") == "service.name":
                    service = (attribute.get("value") or {}).get("stringValue", "?")
            for scope in batch.get("scopeSpans") or []:
                for span in scope.get("spans") or []:
                    start = int(span.get("startTimeUnixNano") or 0)
                    end = int(span.get("endTimeUnixNano") or 0)
                    spans.append(
                        {
                            "service": service,
                            "name": span.get("name"),
                            "ms": round((end - start) / 1_000_000, 2),
                            # Only when set: an unset status on every span is
                            # noise the model has to read past.
                            **(
                                {"status": "error"}
                                if (span.get("status") or {}).get("code") == 2
                                else {}
                            ),
                        }
                    )

        spans.sort(key=lambda span: span["ms"], reverse=True)
        return {
            "trace_id": trace_id,
            "span_count": len(spans),
            "slowest": spans[:MAX_SPANS],
            "truncated": len(spans) > MAX_SPANS,
        }

    async def search_logs(self, query: str, since: str = "1h", limit: int = 20) -> dict[str, Any]:
        """LogQL, e.g. `{service_name="checkout"} | json | level="ERROR"`.

        `since` is mandatory in practice: Loki answers a query with no window
        by returning nothing, which reads exactly like "there were no errors".
        """
        body = await self._get(
            f"{self._loki}/loki/api/v1/query_range",
            {"query": query, "since": since, "limit": max(1, min(limit, MAX_LOG_LINES))},
        )

        lines: list[dict[str, Any]] = []
        for stream in (body.get("data") or {}).get("result") or []:
            service = (stream.get("stream") or {}).get("service_name", "?")
            for timestamp, line in stream.get("values") or []:
                lines.append({"service": service, "at": timestamp, "line": line[:MAX_LINE_CHARS]})
        lines.sort(key=lambda entry: entry["at"], reverse=True)
        if lines:
            return {"count": len(lines), "lines": lines[:MAX_LOG_LINES]}

        # Nothing matched — and nothing matched reads exactly like nothing is
        # wrong. The usual cause is a label that does not exist here, so the
        # answer names the ones that do rather than leaving the model to guess
        # again, which is what it does: four of ten looks in the first real
        # investigation were the same search with a made-up label.
        return {
            "count": 0,
            "lines": [],
            "nothing_matched": (
                "No lines matched. This means the selector found nothing, which is not "
                "the same as there being no errors. Check the label names and the window "
                f"before concluding. Labels that exist here: {', '.join(await self.labels())}."
            ),
        }

    async def labels(self) -> list[str]:
        """The label names Loki actually has. Cached: they change with the
        collector's configuration, not with the question."""
        if self._known_labels is None:
            try:
                body = await self._get(f"{self._loki}/loki/api/v1/labels", {})
                self._known_labels = sorted(body.get("data") or [])
            except Unreachable:
                self._known_labels = []
        return self._known_labels

    async def query_metrics(self, query: str) -> dict[str, Any]:
        """PromQL, instant. For "is this one service or all of them"."""
        body = await self._get(f"{self._prometheus}/api/v1/query", {"query": query})
        result = (body.get("data") or {}).get("result") or []
        return {
            "series": [
                {
                    # The labels are the answer as often as the number is: one
                    # service at 40% errors and every service at 2% are
                    # different incidents with the same total.
                    "labels": {
                        k: v for k, v in (series.get("metric") or {}).items() if k != "__name__"
                    },
                    "value": (series.get("value") or [None, None])[1],
                }
                for series in result[:20]
            ],
            "series_count": len(result),
        }
