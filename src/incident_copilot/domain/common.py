"""共享领域类型和校验辅助函数。"""

import re
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def require_timezone(value: datetime) -> datetime:
    """在所有领域边界拒绝不带时区的时间。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include timezone information")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(require_timezone)]


class DomainModel(BaseModel):
    """经过校验的领域值使用的严格基类。"""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class Severity(StrEnum):
    """不依赖具体可观测性厂商的事故严重程度。"""

    UNKNOWN = "unknown"
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class Environment(StrEnum):
    """事故信息所报告的部署环境。"""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """规范化的证据来源类别。"""

    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    CHANGE = "change"
    TOPOLOGY = "topology"
    KNOWLEDGE = "knowledge"


class HypothesisStatus(StrEnum):
    """根因假设的生命周期状态。"""

    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ReportDisposition(StrEnum):
    """报告陈述根因时采用的确定程度。"""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    INCONCLUSIVE = "inconclusive"


class RiskLevel(StrEnum):
    """修复建议附带的操作风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def normalize_services(values: Sequence[str]) -> tuple[str, ...]:
    """按输入顺序规范化、校验并去重服务名称。"""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip().lower()
        if not value or len(value) > 128:
            raise ValueError("service name must contain 1 to 128 characters")
        if not value[0].isalnum() or any(
            not (character.isalnum() or character in "._-") for character in value
        ):
            raise ValueError(f"invalid service name: {raw_value!r}")
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    return tuple(normalized)


def normalize_optional_service(value: str | None) -> str | None:
    """使用共享服务名契约规范化一个可选服务名称。"""
    if value is None:
        return None
    return normalize_services((value,))[0]


def unique_non_empty(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    """清理并去重有界字符串集合。"""
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{field_name} must not contain empty values")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def unique_evidence_ids(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    """校验并去重对证据领域对象的引用。"""
    result = unique_non_empty(values, field_name=field_name)
    for value in result:
        if re.fullmatch(r"ev_[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value) is None:
            raise ValueError(f"{field_name} must contain valid evidence ids")
    return result
