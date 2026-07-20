"""报告一致性和实际测量调查统计测试。"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from incident_copilot.domain import (
    IncidentReport,
    InvestigationStats,
    ReportDisposition,
    SourceType,
    TimelineEvent,
)


def make_stats(**overrides: object) -> InvestigationStats:
    started = datetime(2026, 7, 18, 2, 20, tzinfo=UTC)
    values: dict[str, object] = {
        "research_rounds": 1,
        "tool_call_count": 2,
        "tool_attempt_count": 3,
        "tool_success_count": 2,
        "tool_failure_count": 0,
        "model_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "token_usage_estimated": False,
        "started_at": started,
        "completed_at": started + timedelta(seconds=1),
        "duration_ms": 1_000,
        "evidence_count_by_source": {SourceType.LOG: 1},
        "stop_reason": "evidence_sufficient",
    }
    values.update(overrides)
    return InvestigationStats.model_validate(values)


def make_report(**overrides: object) -> IncidentReport:
    values: dict[str, object] = {
        "report_id": "rpt_payment_001",
        "incident_id": "inc_payment_001",
        "summary": "Payment requests timed out.",
        "root_cause": "A connection pool configuration changed.",
        "disposition": ReportDisposition.PROBABLE,
        "confidence": 0.75,
        "confidence_rationale": "Two independent signals align in time.",
        "affected_services": ["payment-service"],
        "timeline": [
            TimelineEvent(
                timestamp=datetime(2026, 7, 18, 2, 20, tzinfo=UTC),
                description="Errors began.",
            )
        ],
        "investigation_summary": "One bounded investigation round completed.",
        "investigation_stats": make_stats(),
    }
    values.update(overrides)
    return IncidentReport.model_validate(values)


def test_report_accepts_consistent_measured_values() -> None:
    report = make_report()

    assert report.schema_version == "1.0"
    assert report.investigation_stats.duration_ms == 1_000
    assert report.model_dump(mode="json")["investigation_stats"]["evidence_count_by_source"] == {
        "log": 1
    }


def test_report_rejects_unsorted_timeline() -> None:
    later = TimelineEvent(
        timestamp=datetime(2026, 7, 18, 2, 30, tzinfo=UTC),
        description="Later event.",
    )
    earlier = TimelineEvent(
        timestamp=datetime(2026, 7, 18, 2, 20, tzinfo=UTC),
        description="Earlier event.",
    )

    with pytest.raises(ValidationError, match="sorted"):
        make_report(timeline=[later, earlier])


def test_report_requires_root_cause_for_probable_disposition() -> None:
    with pytest.raises(ValidationError, match="require a root_cause"):
        make_report(root_cause=None)


def test_stats_reject_invented_token_total() -> None:
    with pytest.raises(ValidationError, match="total_tokens"):
        make_stats(input_tokens=2, output_tokens=3, total_tokens=99)


def test_stats_reject_physical_attempts_below_logical_steps() -> None:
    with pytest.raises(ValidationError, match="tool_attempt_count"):
        make_stats(tool_attempt_count=1)


def test_stats_reject_negative_evidence_count() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        make_stats(evidence_count_by_source={SourceType.LOG: -1})


def test_stats_evidence_counts_cannot_be_mutated_after_validation() -> None:
    stats = make_stats()
    mutable_view: Any = stats.evidence_count_by_source

    with pytest.raises(TypeError):
        mutable_view[SourceType.LOG] = -1


@pytest.mark.parametrize(
    ("completed_at", "duration_ms"),
    [
        (None, 1_000),
        (datetime(2026, 7, 18, 2, 21, tzinfo=UTC), None),
    ],
)
def test_stats_requires_completion_time_and_duration_together(
    completed_at: datetime | None,
    duration_ms: int | None,
) -> None:
    with pytest.raises(ValidationError, match="provided together"):
        make_stats(completed_at=completed_at, duration_ms=duration_ms)
