"""Tests for hypothesis evidence relationships."""

from typing import Any

import pytest
from pydantic import ValidationError

from incident_copilot.domain import Hypothesis, HypothesisStatus, SourceType, VerificationQuery


def make_hypothesis(**overrides: object) -> Hypothesis:
    values: dict[str, object] = {
        "hypothesis_id": "hyp_pool_001",
        "description": "The deployment reduced the database connection pool limit.",
        "affected_services": ["Payment-Service"],
        "supporting_evidence_ids": ["ev_log_001"],
        "contradicting_evidence_ids": [],
        "confidence": 0.7,
        "status": HypothesisStatus.INVESTIGATING,
        "verification_queries": [
            VerificationQuery(
                query="compare pool configuration before and after deployment",
                source_types=[SourceType.CHANGE, SourceType.LOG, SourceType.CHANGE],
                service="payment-service",
            )
        ],
        "reasoning_summary": "The error began immediately after a configuration change.",
        "version": 1,
    }
    values.update(overrides)
    return Hypothesis.model_validate(values)


def test_hypothesis_normalizes_services_and_query_sources() -> None:
    hypothesis = make_hypothesis()

    assert hypothesis.affected_services == ("payment-service",)
    assert hypothesis.verification_queries[0].source_types == (
        SourceType.CHANGE,
        SourceType.LOG,
    )


def test_hypothesis_rejects_evidence_overlap() -> None:
    with pytest.raises(ValidationError, match="must not overlap"):
        make_hypothesis(contradicting_evidence_ids=["ev_log_001"])


def test_hypothesis_rejects_malformed_evidence_id() -> None:
    with pytest.raises(ValidationError, match="valid evidence ids"):
        make_hypothesis(supporting_evidence_ids=["ev_"])


def test_supported_hypothesis_requires_supporting_evidence() -> None:
    with pytest.raises(ValidationError, match="requires supporting evidence"):
        make_hypothesis(status=HypothesisStatus.SUPPORTED, supporting_evidence_ids=[])


def test_hypothesis_invariants_cannot_be_bypassed_by_mutation() -> None:
    hypothesis = make_hypothesis(status=HypothesisStatus.SUPPORTED)
    mutable_view: Any = hypothesis.supporting_evidence_ids
    frozen_view: Any = hypothesis

    with pytest.raises(AttributeError):
        mutable_view.clear()
    with pytest.raises(ValidationError, match="frozen"):
        frozen_view.status = HypothesisStatus.REJECTED
