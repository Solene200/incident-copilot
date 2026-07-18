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

    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    raw_query: str = Field(min_length=1, max_length=10_000)
    services: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    start_time: AwareDatetime
    end_time: AwareDatetime
    symptoms: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    severity: Severity = Severity.UNKNOWN
    environment: Environment = Environment.UNKNOWN
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    timezone_assumption: str | None = Field(default=None, max_length=64)

    @field_validator("services")
    @classmethod
    def validate_services(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="symptoms")

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self
