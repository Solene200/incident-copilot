"""不依赖框架的事故诊断领域模型。"""

from incident_copilot.domain.common import (
    Environment,
    HypothesisStatus,
    ReportDisposition,
    RiskLevel,
    Severity,
    SourceType,
)
from incident_copilot.domain.evidence import (
    CONTENT_HASH_ALGORITHM,
    Citation,
    ContentHashAlgorithm,
    Evidence,
    EvidenceRef,
    EvidenceResolutionError,
    EvidenceResolver,
    canonical_content_bytes,
    content_sha256,
)
from incident_copilot.domain.hypothesis import Hypothesis, VerificationQuery
from incident_copilot.domain.incident import IncidentContext
from incident_copilot.domain.report import (
    IncidentReport,
    InvestigationStats,
    RejectedHypothesis,
    RemediationStep,
    TimelineEvent,
)

__all__ = [
    "CONTENT_HASH_ALGORITHM",
    "Citation",
    "ContentHashAlgorithm",
    "Environment",
    "Evidence",
    "EvidenceRef",
    "EvidenceResolutionError",
    "EvidenceResolver",
    "Hypothesis",
    "HypothesisStatus",
    "IncidentContext",
    "IncidentReport",
    "InvestigationStats",
    "RejectedHypothesis",
    "RemediationStep",
    "ReportDisposition",
    "RiskLevel",
    "Severity",
    "SourceType",
    "TimelineEvent",
    "VerificationQuery",
    "canonical_content_bytes",
    "content_sha256",
]
