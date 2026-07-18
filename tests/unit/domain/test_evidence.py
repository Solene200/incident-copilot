"""证据、引用和有界引用测试。"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from incident_copilot.domain import Citation, Evidence, EvidenceRef, SourceType

CONTENT_HASH = "a" * 64


def make_citation(**overrides: object) -> Citation:
    values: dict[str, object] = {
        "citation_id": "cit_log_001",
        "uri": "fixture://logs/payment.jsonl",
        "locator": "line=1",
        "display_name": "Fixture payment logs",
        "retrieved_at": datetime(2026, 7, 18, 2, 45, tzinfo=UTC),
        "content_hash": CONTENT_HASH,
    }
    values.update(overrides)
    return Citation.model_validate(values)


def make_evidence(**overrides: object) -> Evidence:
    values: dict[str, object] = {
        "evidence_id": "ev_log_001",
        "source_type": SourceType.LOG,
        "source_name": "fixture-logs",
        "title": "Connection timeout",
        "content": "sanitized connection timeout",
        "summary": "Database connection acquisition timed out.",
        "timestamp": datetime(2026, 7, 18, 2, 25, tzinfo=UTC),
        "service": "PAYMENT-SERVICE",
        "relevance_score": 0.9,
        "reliability_score": 0.8,
        "metadata": {"fixture": True},
        "citation": make_citation(),
        "content_hash": CONTENT_HASH,
        "collected_at": datetime(2026, 7, 18, 2, 45, tzinfo=UTC),
    }
    values.update(overrides)
    return Evidence.model_validate(values)


def test_evidence_builds_bounded_reference() -> None:
    evidence = make_evidence()

    reference = EvidenceRef.from_evidence(evidence)

    assert reference.evidence_id == evidence.evidence_id
    assert reference.service == "payment-service"
    assert "content" not in reference.model_dump()
    assert "content_hash" not in reference.model_dump()


def test_evidence_reference_normalizes_service() -> None:
    payload = EvidenceRef.from_evidence(make_evidence()).model_dump()
    payload["service"] = "PAYMENT-SERVICE"

    reference = EvidenceRef.model_validate(payload)

    assert reference.service == "payment-service"


@pytest.mark.parametrize("field", ["relevance_score", "reliability_score"])
def test_evidence_rejects_scores_outside_unit_interval(field: str) -> None:
    with pytest.raises(ValidationError):
        make_evidence(**{field: 1.1})


def test_evidence_rejects_mismatched_citation_hash() -> None:
    with pytest.raises(ValidationError, match="hashes must match"):
        make_evidence(citation=make_citation(content_hash="b" * 64))


def test_citation_rejects_unsafe_scheme() -> None:
    with pytest.raises(ValidationError, match="scheme"):
        make_citation(uri="file:///private/path")


@pytest.mark.parametrize(
    "uri",
    ["https:///missing-host", "https://user:password@example.com/source"],
)
def test_citation_rejects_unresolvable_or_sensitive_http_uri(uri: str) -> None:
    with pytest.raises(ValidationError, match=r"host|credentials"):
        make_citation(uri=uri)


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [
        (datetime(2026, 7, 18, 2, 20, tzinfo=UTC), None),
        (
            datetime(2026, 7, 18, 2, 40, tzinfo=UTC),
            datetime(2026, 7, 18, 2, 20, tzinfo=UTC),
        ),
    ],
)
def test_evidence_reference_rejects_invalid_time_window(
    start_time: datetime,
    end_time: datetime | None,
) -> None:
    payload = EvidenceRef.from_evidence(make_evidence()).model_dump()
    payload.update({"start_time": start_time, "end_time": end_time})

    with pytest.raises(ValidationError, match=r"provided together|earlier"):
        EvidenceRef.model_validate(payload)
