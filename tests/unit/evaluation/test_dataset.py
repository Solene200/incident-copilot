"""仓库内评估数据集的版本和路径安全测试。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_copilot.domain.evidence import EvidenceResolutionError
from incident_copilot.evaluation.dataset import (
    RepositoryEvidenceResolver,
    load_evaluation_dataset,
)
from incident_copilot.evaluation.schemas import EvaluationSample
from incident_copilot.rag.bootstrap import build_fixture_retriever
from incident_copilot.rag.schemas import SearchQuery
from incident_copilot.tools.providers.fixture import FixtureProvider

REPOSITORY_ROOT = Path(__file__).parents[3]


def test_default_dataset_contains_distinct_known_root_cause_samples() -> None:
    dataset = load_evaluation_dataset()

    assert dataset.version == "1.0.0"
    assert len(dataset.samples) == 3
    assert len({sample.ground_truth.failure_type for sample in dataset.samples}) == 3
    assert all(sample.ground_truth.root_cause_terms for sample in dataset.samples)


def test_dataset_rejects_fixture_path_traversal() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        EvaluationSample.model_validate(
            {
                "sample_id": "eval_escape",
                "fixture_path": "../secret.json",
                "retrieval_query": "bounded query",
                "ground_truth": {
                    "affected_services": ["payment-service"],
                    "failure_type": "test_failure",
                    "root_cause_terms": ["cause"],
                },
            }
        )


def test_repository_resolver_round_trips_fixture_evidence() -> None:
    provider = FixtureProvider.from_path(
        REPOSITORY_ROOT / "data" / "incidents" / "payment-service-pool-exhaustion.json"
    )
    evidence = provider.fixture.evidence[0]

    resolved = RepositoryEvidenceResolver(REPOSITORY_ROOT).resolve(evidence.citation)

    assert resolved == evidence.content


def test_repository_resolver_round_trips_knowledge_chunk() -> None:
    retriever, _ = build_fixture_retriever()
    hit = retriever.search(SearchQuery(query="database connection pool", top_k=1)).hits[0]

    resolved = RepositoryEvidenceResolver(REPOSITORY_ROOT).resolve(hit.chunk.citation)

    assert resolved == hit.chunk.text


def test_repository_resolver_rejects_tampered_locator_and_path_escape() -> None:
    provider = FixtureProvider.payment_service()
    citation = provider.fixture.evidence[0].citation
    resolver = RepositoryEvidenceResolver(REPOSITORY_ROOT)

    with pytest.raises(EvidenceResolutionError, match="locator"):
        resolver.resolve(citation.model_copy(update={"locator": "evidence[999]"}))
    with pytest.raises(EvidenceResolutionError, match="outside"):
        resolver.resolve(
            citation.model_copy(update={"uri": "fixture://incidents/../../../outside.json"})
        )
