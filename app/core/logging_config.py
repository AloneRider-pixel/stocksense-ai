"""Structured logging: one JSON object per line, request-id aware.

Every log record carries ts (UTC ISO-8601), level, logger, message, and -
when set by the request middleware - request_id, method, path, status_code,
and duration_ms. LOG_FORMAT=json (default) emits single-line JSON for log
aggregators; LOG_FORMAT=text emits a human-friendly line for local dev.
"""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_EXTRA_KEYS = ("method", "path", "status_code", "duration_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Emit-time attribute wins (survives queued/async handlers); the
        # contextvar is the fallback for inline formatting.
        request_id = getattr(record, "request_id", None) or request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        for key in _EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get()
        rid = f" [{request_id[:8]}]" if request_id else ""
        return (
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
            f"{record.levelname:<7} {record.name}{rid} {record.getMessage()}"
        )


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure the root logger once; safe to call repeatedly."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())

    # Third-party HTTP clients log full request URLs (including the Twelve
    # Data apikey query parameter) at INFO; keep them at WARNING or above.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
