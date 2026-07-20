"""调查生命周期操作使用的版本化 HTTP Schema。"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.api.schemas import ApiModel
from incident_copilot.core.logging import redact_value
from incident_copilot.domain.common import (
    AwareDatetime,
    Environment,
    Severity,
    normalize_services,
    unique_non_empty,
)
from incident_copilot.domain.incident import IncidentContext
from incident_copilot.domain.report import IncidentReport
from incident_copilot.domain.review import HumanFeedback, HumanReviewRequest
from incident_copilot.graph.schemas import InvestigationOptions
from incident_copilot.investigations.models import InvestigationRecord, InvestigationStatus


class CreateInvestigationRequest(ApiModel):
    """经过校验的用户调查范围和有界执行策略。"""

    # 用户对故障现象和调查目标的原始描述。
    query: str = Field(
        min_length=1,
        max_length=10_000,
        description=(
            "Natural-language incident description. The current API does not infer the service "
            "or time window from this text."
        ),
    )
    # 调用方提供的单个 primary service,当前版本不从 query 自动提取。
    services: tuple[str, ...] = Field(
        min_length=1,
        max_length=1,
        description="Exactly one caller-supplied primary service; not inferred from query.",
    )
    # 调查时间窗口的起点, 必须携带时区。
    start_time: AwareDatetime = Field(
        description="Caller-supplied timezone-aware investigation window start."
    )
    # 调查时间窗口的终点, 必须晚于 start_time。
    end_time: AwareDatetime = Field(
        description="Caller-supplied timezone-aware investigation window end."
    )
    # 用户已经观察到的故障症状, 例如错误率上升。
    symptoms: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    # 故障严重程度, 未提供时为 unknown。
    severity: Severity = Severity.UNKNOWN
    # 故障发生的部署环境。
    environment: Environment = Environment.UNKNOWN
    # 调查轮数、调用次数和超时等受控执行预算。
    options: InvestigationOptions = Field(default_factory=InvestigationOptions)

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

    def fingerprint(self) -> str:
        """在引入服务端生成的 ID 前计算语义请求哈希。"""
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_incident(self, incident_id: str) -> IncidentContext:
        """把传输层请求转换为领域边界对象。"""
        return IncidentContext(
            incident_id=incident_id,
            raw_query=self.query,
            services=self.services,
            start_time=self.start_time,
            end_time=self.end_time,
            symptoms=self.symptoms,
            severity=self.severity,
            environment=self.environment,
            created_at=datetime.now(UTC),
        )


class ResumeInvestigationRequest(HumanFeedback):
    """复用严格领域反馈契约的公开恢复请求体。"""


class InvestigationResponse(ApiModel):
    """不包含 Graph checkpoint 原始值的公开任务投影。"""

    # 公开响应结构的版本, 便于以后兼容演进。
    schema_version: str = "1.0"
    # API 调查任务的唯一标识。
    investigation_id: str
    # 被调查故障事件的唯一标识。
    incident_id: str
    # LangGraph Checkpoint 使用的稳定线程标识。
    thread_id: str
    # 当前这次 Graph 运行的关联标识。
    run_id: str
    # 调查任务对外可见的生命周期状态。
    status: InvestigationStatus
    # 是否正暂停并等待人工审核。
    review_required: bool
    # 暂停时展示给审核人的安全审核请求。
    review_request: HumanReviewRequest | None
    # 调查完成后生成的结构化故障报告。
    report: IncidentReport | None
    # 调查失败时可以安全公开的简短错误信息。
    error_message: str | None
    # 调查任务创建时间。
    created_at: AwareDatetime
    # 调查任务最近一次状态更新时间。
    updated_at: AwareDatetime
    # 本次响应是否来自幂等键命中的已有任务。
    replayed: bool = False

    @classmethod
    def from_record(
        cls,
        record: InvestigationRecord,
        *,
        replayed: bool = False,
    ) -> "InvestigationResponse":
        """根据 Repository 元数据构造稳定响应。"""
        report = (
            IncidentReport.model_validate(redact_value(record.report.model_dump(mode="python")))
            if record.report is not None
            else None
        )
        review_request = (
            HumanReviewRequest.model_validate(
                redact_value(record.review_request.model_dump(mode="python"))
            )
            if record.review_request is not None
            else None
        )
        return cls(
            investigation_id=record.investigation_id,
            incident_id=record.incident_id,
            thread_id=record.thread_id,
            run_id=record.run_id,
            status=record.status,
            review_required=record.status is InvestigationStatus.WAITING_REVIEW,
            review_request=review_request,
            report=report,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
            replayed=replayed,
        )
