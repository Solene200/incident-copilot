"""Structured JSON logging with conservative secret redaction."""

import json
import logging
import logging.config
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final

from incident_copilot.core.config import LogLevel

REDACTED: Final = "***REDACTED***"
_SENSITIVE_KEYS: Final = ("api_key", "apikey", "authorization", "password", "secret", "token")
_KEY_VALUE_PATTERN: Final = re.compile(
    r"(?i)\b(api[_-]?key|password|secret|token)\s*([=:])\s*([^\s,;]+)"
)
_BEARER_PATTERN: Final = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
_STANDARD_LOG_RECORD_FIELDS: Final = frozenset(logging.makeLogRecord({}).__dict__)


def redact_text(value: str) -> str:
    """Redact common inline credential formats from a string."""
    value = _BEARER_PATTERN.sub(rf"\1{REDACTED}", value)
    return _KEY_VALUE_PATTERN.sub(rf"\1\2{REDACTED}", value)


def redact_value(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact values whose keys or contents look sensitive."""
    if key is not None and any(fragment in key.casefold() for fragment in _SENSITIVE_KEYS):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_value(item, key=str(item_key)) for item_key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Serialize standard log records and safe extras as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS and key not in {"message", "asctime"}:
                payload[key] = redact_value(value, key=key)
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: LogLevel | str = LogLevel.INFO) -> None:
    """Configure process logging idempotently using a JSON console handler."""
    resolved_level = level.value if isinstance(level, LogLevel) else level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "level": resolved_level,
                }
            },
            "root": {"handlers": ["console"], "level": resolved_level},
        }
    )
