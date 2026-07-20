"""事故上下文领域模型。"""

from datetime import UTC, datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    Environment,
    Severity,
    normalize_services,
    unique_non_empty,
)


class IncidentContext(DomainModel):
    """从用户事故描述中提取并规范化的调查范围。"""

    # 故障事件的唯一标识, 统一使用 inc_ 前缀。
    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 用户提交的原始故障描述和调查问题。
    raw_query: str = Field(min_length=1, max_length=10_000)
    # 当前版本只接受一个由调用方明确提供的 primary service。
    services: tuple[str, ...]
    # 故障调查时间窗口的起点。
    start_time: AwareDatetime
    # 故障调查时间窗口的终点。
    end_time: AwareDatetime
    # 用户已经观察到的故障症状。
    symptoms: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    # 故障严重程度。
    severity: Severity = Severity.UNKNOWN
    # 故障发生的部署环境。
    environment: Environment = Environment.UNKNOWN
    # 系统创建该事故上下文的 UTC 时间。
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    # 输入缺少时区时使用的假设说明, 当前严格 API 通常不需要。
    timezone_assumption: str | None = Field(default=None, max_length=64)

    @field_validator("services")
    @classmethod
    def validate_services(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = normalize_services(values)
        if len(normalized) != 1:
            raise ValueError("current version requires exactly one primary service")
        return normalized

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="symptoms")

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self
