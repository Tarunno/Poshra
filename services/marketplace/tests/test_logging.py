import json
import logging

from config.observability import REQUEST_ID_HEADER, JsonFormatter, request_id_var


def record(**extra) -> logging.LogRecord:
    rec = logging.LogRecord("poshra.test", logging.INFO, __file__, 10, "hello", None, None)
    rec.__dict__.update(extra)
    return rec


def test_formatter_emits_one_json_object_with_the_core_fields():
    line = JsonFormatter().format(record())
    payload = json.loads(line)

    assert "\n" not in line  # one event per line, or collectors split it wrongly
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
    assert payload["service"] == "marketplace"
    assert payload["timestamp"].endswith("Z")


def test_formatter_keeps_application_fields_as_real_keys():
    payload = json.loads(JsonFormatter().format(record(http_status=404, duration_ms=12.5)))
    # Queryable fields, not text baked into the message.
    assert payload["http_status"] == 404
    assert payload["duration_ms"] == 12.5


def test_formatter_includes_the_request_id_when_one_is_bound():
    token = request_id_var.set("abc-123")
    try:
        payload = json.loads(JsonFormatter().format(record()))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "abc-123"


def test_formatter_serialises_exceptions():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        rec = record()
        rec.exc_info = sys.exc_info()
        payload = json.loads(JsonFormatter().format(rec))
    assert "ValueError: boom" in payload["exception"]


def test_middleware_reuses_the_gateway_request_id(client):
    response = client.get("/healthz", headers={"x-request-id": "from-gateway"})
    assert response[REQUEST_ID_HEADER] == "from-gateway"


def test_middleware_generates_a_request_id_when_the_gateway_sends_none(client):
    response = client.get("/healthz")
    assert response[REQUEST_ID_HEADER]
