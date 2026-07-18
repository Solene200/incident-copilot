"""Tests for incident context invariants."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from incident_copilot.domain import Environment, IncidentContext, Severity


def make_incident(**overrides: object) -> IncidentContext:
    values: dict[str, object] = {
        "incident_id": "inc_payment_001",
        "raw_query": "payment errors increased",
        "services": ["Payment-Service", "payment-service"],
        "start_time": datetime(2026, 7, 18, 2, 20, tzinfo=UTC),
        "end_time": datetime(2026, 7, 18, 2, 40, tzinfo=UTC),
        "symptoms": ["timeouts", "timeouts"],
        "severity": Severity.SEV2,
        "environment": Environment.PRODUCTION,
    }
    values.update(overrides)
    return IncidentContext.model_validate(values)


def test_incident_normalizes_and_deduplicates_values() -> None:
    incident = make_incident()

    assert incident.services == ("payment-service",)
    assert incident.symptoms == ("timeouts",)


def test_incident_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        make_incident(start_time=datetime(2026, 7, 18, 2, 20))


def test_incident_rejects_invalid_time_window() -> None:
    start = datetime(2026, 7, 18, 2, 40, tzinfo=UTC)
    end = datetime(2026, 7, 18, 2, 20, tzinfo=UTC)

    with pytest.raises(ValidationError, match="earlier"):
        make_incident(start_time=start, end_time=end)


def test_incident_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        make_incident(untrusted_field="value")
