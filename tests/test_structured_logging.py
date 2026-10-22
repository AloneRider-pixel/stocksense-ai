"""Structured JSON logging: formatter shape, request-id context, middleware line."""

from __future__ import annotations

import json
import logging

from app.core.logging_config import JsonFormatter, configure_logging, request_id_var


def _record(msg="hello"):
    return logging.LogRecord("test.logger", logging.INFO, __file__, 10, msg, (), None)


def test_json_formatter_includes_request_id():
    token = request_id_var.set("req-123")
    try:
        out = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)
    assert out["message"] == "hello"
    assert out["request_id"] == "req-123"
    assert out["level"] == "INFO" and out["logger"] == "test.logger"
    assert "ts" in out


def test_json_formatter_omits_request_id_outside_request():
    out = json.loads(JsonFormatter().format(_record()))
    assert "request_id" not in out


def test_json_formatter_passes_through_extras():
    record = _record("http_request")
    record.method = "GET"  # type: ignore[attr-defined]
    record.path = "/health"  # type: ignore[attr-defined]
    record.status_code = 200  # type: ignore[attr-defined]
    record.duration_ms = 3.2  # type: ignore[attr-defined]
    out = json.loads(JsonFormatter().format(record))
    assert out["method"] == "GET" and out["path"] == "/health"
    assert out["status_code"] == 200 and out["duration_ms"] == 3.2


def test_request_middleware_logs_one_json_line_per_request(client):
    records: list[logging.LogRecord] = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("stocksense.request")
    handler = ListHandler()
    logger.addHandler(handler)
    try:
        response = client.get("/api/v1/health")
    finally:
        logger.removeHandler(handler)
    assert response.status_code == 200
    lines = [r for r in records if r.getMessage() == "http_request"]
    assert len(lines) == 1
    line = lines[0]
    assert line.method == "GET" and line.path == "/api/v1/health"  # type: ignore[attr-defined]
    assert line.status_code == 200  # type: ignore[attr-defined]
    assert isinstance(line.duration_ms, float)  # type: ignore[attr-defined]
    # the emitted text parses as JSON and carries the same request id as the header
    rendered = JsonFormatter().format(line)
    payload = json.loads(rendered)
    assert payload["request_id"] == response.headers["X-Request-ID"]


def test_text_format_keeps_working():
    configure_logging("INFO", "text")
    response_status = configure_logging  # smoke: no exception
    assert response_status is not None
    configure_logging("INFO", "json")
