"""Structured logging.

Logs are JSON lines on stdout, one object per event. A log collector can parse
them without regular expressions, and fields can be queried directly
("show me 5xx responses for this user") instead of grepped.

Two fields matter later:

* ``request_id`` — set by the gateway's correlation-id plugin and carried here
  through a context variable, so every line from one request can be grouped.
* ``trace_id`` / ``span_id`` — filled in once OpenTelemetry is added, which is
  what links a log line to the exact span in a distributed trace.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

REQUEST_ID_HEADER = "X-Request-ID"

# Context variables follow the request through async and sync code, so the
# formatter can reach the current request without passing it around.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

# Attributes the standard library puts on every record; anything else a caller
# passes through `extra=` is application data worth keeping in the JSON.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "marketplace",
        }

        if request_id := request_id_var.get():
            payload["request_id"] = request_id
        if user_id := user_id_var.get():
            payload["user_id"] = user_id

        # OpenTelemetry's logging instrumentation adds these attributes; until
        # it is wired up they are simply absent.
        for otel_attr, field in (("otelTraceID", "trace_id"), ("otelSpanID", "span_id")):
            value = getattr(record, otel_attr, None)
            if value and value != "0" * len(value):
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


request_logger = logging.getLogger("poshra.request")


class RequestLogMiddleware(MiddlewareMixin):
    """Bind request context and log one structured line per request.

    This replaces gunicorn's text access log so that every line the service
    emits, access or application, has the same shape.
    """

    def process_request(self, request: HttpRequest) -> None:
        # Trust the gateway's id when present so one id spans every service.
        request_id_var.set(request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex)
        user_id_var.set(request.headers.get("X-User-Id", ""))
        request.start_time = time.perf_counter()

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        duration_ms = round((time.perf_counter() - getattr(request, "start_time", 0)) * 1000, 2)
        request_logger.info(
            "request",
            extra={
                "http_method": request.method,
                "http_path": request.path,
                "http_status": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR", ""),
            },
        )
        if request_id := request_id_var.get():
            response[REQUEST_ID_HEADER] = request_id
        return response
