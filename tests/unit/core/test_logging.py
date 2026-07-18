"""Tests for structured logging and recursive redaction."""

import json
import logging

from incident_copilot.core.logging import REDACTED, JsonFormatter, redact_text, redact_value


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


def test_redact_text_handles_json_credentials_and_authorization_schemes() -> None:
    value = '{"api_key":"secret-value","Authorization":"Basic dXNlcjpwYXNz"}'

    redacted = redact_text(value)

    assert "secret-value" not in redacted
    assert "dXNlcjpwYXNz" not in redacted
    assert redacted.count(REDACTED) == 2


def test_redact_value_preserves_non_secret_token_metrics() -> None:
    value = {"input_tokens": 12, "token_usage": {"total_tokens": 20}, "session_token": "x"}

    redacted = redact_value(value)

    assert redacted == {
        "input_tokens": 12,
        "token_usage": {"total_tokens": 20},
        "session_token": REDACTED,
    }
