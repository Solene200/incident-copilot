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


# 所有领域时间字段共用的“必须携带时区”类型。
AwareDatetime = Annotated[datetime, AfterValidator(require_timezone)]


class DomainModel(BaseModel):
    """经过校验的领域值使用的严格基类。"""

    # 拒绝未知字段、创建后不可修改, 并自动清理字符串两端空白。
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class Severity(StrEnum):
    """不依赖具体可观测性厂商的事故严重程度。"""

    UNKNOWN = "unknown"  # 调用方没有提供明确严重程度。
    SEV1 = "sev1"  # 最高等级的关键业务故障。
    SEV2 = "sev2"  # 影响较大但未达到最高等级的故障。
    SEV3 = "sev3"  # 中等影响、需要及时处理的故障。
    SEV4 = "sev4"  # 影响较低的普通故障或异常。


class Environment(StrEnum):
    """事故信息所报告的部署环境。"""

    PRODUCTION = "production"  # 面向真实用户的生产环境。
    STAGING = "staging"  # 上线前的预发布验证环境。
    DEVELOPMENT = "development"  # 本地或共享开发环境。
    UNKNOWN = "unknown"  # 故障来源没有提供环境信息。


class SourceType(StrEnum):
    """规范化的证据来源类别。"""

    LOG = "log"  # 应用或基础设施产生的日志证据。
    METRIC = "metric"  # 错误率、延迟和资源利用率等指标证据。
    TRACE = "trace"  # 一个请求跨服务传播的调用链证据。
    CHANGE = "change"  # 部署、配置和基础设施变更证据。
    TOPOLOGY = "topology"  # 服务之间依赖关系的拓扑证据。
    KNOWLEDGE = "knowledge"  # Runbook、服务文档或历史故障知识。


class HypothesisStatus(StrEnum):
    """根因假设的生命周期状态。"""

    PROPOSED = "proposed"  # 刚生成、尚未验证的根因假设。
    INVESTIGATING = "investigating"  # 正在收集更多证据验证。
    SUPPORTED = "supported"  # 已有足够支持证据的假设。
    REJECTED = "rejected"  # 已被反证排除的假设。
    INCONCLUSIVE = "inconclusive"  # 当前证据无法支持也无法排除。


class ReportDisposition(StrEnum):
    """报告陈述根因时采用的确定程度。"""

    CONFIRMED = "confirmed"  # 证据足以确认根因。
    PROBABLE = "probable"  # 根因很可能成立, 但仍有不确定性。
    INCONCLUSIVE = "inconclusive"  # 预算内无法得出可靠根因。


class RiskLevel(StrEnum):
    """修复建议附带的操作风险等级。"""

    LOW = "low"  # 风险较低的只读验证或安全操作。
    MEDIUM = "medium"  # 可能影响局部服务, 需要谨慎执行。
    HIGH = "high"  # 可能明显影响线上业务, 必须人工确认。
    CRITICAL = "critical"  # 可能造成重大中断, 必须严格审核。


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
