"""Structured, request-aware logging for FlowPilot application code."""

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone


_request_id: ContextVar[str | None] = ContextVar("flowpilot_request_id", default=None)
_LOG_FIELDS = ("method", "path", "status_code", "duration_ms", "error_type")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        request_id = getattr(record, "request_id", None) or _request_id.get()
        if request_id:
            payload["request_id"] = request_id
        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        for field, value in record.__dict__.items():
            if field.startswith("audit_") and value is not None:
                payload[field] = value

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    """Install one JSON handler for application loggers, without changing providers."""
    app_logger = logging.getLogger("app")
    if not any(getattr(handler, "_flowpilot_json", False) for handler in app_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        handler._flowpilot_json = True
        app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


def set_request_id(request_id: str) -> Token:
    return _request_id.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)
