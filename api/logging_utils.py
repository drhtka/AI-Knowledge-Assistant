from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonLogFormatter(logging.Formatter):
    """Render log records as compact JSON for easier machine parsing later."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "event"):
            payload["event"] = record.event

        if hasattr(record, "context") and isinstance(record.context, dict):
            payload.update(record.context)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    """Set a predictable root logger configuration for the app process."""
    root_logger = logging.getLogger()
    if getattr(configure_logging, "_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    configure_logging._configured = True
