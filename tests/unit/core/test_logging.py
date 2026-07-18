"""Tests for structured logging and recursive redaction."""

import json
import logging

from incident_copilot.core.logging import REDACTED, JsonFormatter, redact_value


def test_json_formatter_redacts_message_and_extra_fields() -> None:
    record = logging.makeLogRecord(
        {
            "name": "incident_copilot.test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "pathname": __file__,
            "lineno": 10,
            "msg": "request token=plain-token Authorization: Bearer another-token",
            "args": (),
            "exc_info": None,
            "context": {"api_key": "secret-value", "service": "payment-service"},
        }
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert "plain-token" not in payload["message"]
    assert "another-token" not in payload["message"]
    assert payload["context"]["api_key"] == REDACTED
    assert payload["context"]["service"] == "payment-service"


def test_redact_value_handles_nested_sequences() -> None:
    value = {"items": [{"password": "value"}, "api_key=visible"]}

    redacted = redact_value(value)

    assert redacted == {"items": [{"password": REDACTED}, f"api_key={REDACTED}"]}
