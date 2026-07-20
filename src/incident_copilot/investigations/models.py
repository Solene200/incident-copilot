"""任务元数据和安全流式事件契约。"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, JsonValue

from incident_copilot.domain.common import AwareDatetime, DomainModel
from incident_copilot.domain.incident import IncidentContext
from incident_copilot.domain.report import IncidentReport
from incident_copilot.domain.review import HumanReviewRequest
from incident_copilot.graph.schemas import InvestigationOptions


class InvestigationStatus(StrEnum):
    """一个调查任务对外可观察的生命周期。"""

    PENDING = "pending"  # 任务已创建, 后台 Graph 尚未开始。
    RUNNING = "running"  # Graph 正在调查或恢复执行。
    WAITING_REVIEW = "waiting_review"  # Graph 已暂停并等待人工审核。
    COMPLETED = "completed"  # 调查和必要审核已完成。
    FAILED = "failed"  # 调查因无法恢复的错误终止。


class EventType(StrEnum):
    """可安全提供给公开 SSE 消费者的版本化事件名称。"""

    INVESTIGATION_QUEUED = "investigation.queued"  # 调查任务已进入后台执行队列。
    INVESTIGATION_STARTED = "investigation.started"  # 后台 Graph 已开始执行。
    NODE_COMPLETED = "node.completed"  # 一个 Graph 节点完成并产生更新。
    TOOL_COMPLETED = "tool.completed"  # 一个工具步骤成功完成。
    TOOL_FAILED = "tool.failed"  # 一个工具步骤失败但调查可能降级继续。
    EVIDENCE_ADDED = "evidence.added"  # 新 EvidenceRef 已写入调查结果。
    HYPOTHESIS_UPDATED = "hypothesis.updated"  # 根因假设集合发生变化。
    BUDGET_UPDATED = "budget.updated"  # 调用次数、轮数或 Token 用量发生变化。
    REVIEW_REQUIRED = "review.required"  # 高风险报告已暂停等待人工审核。
    REPORT_COMPLETED = "report.completed"  # 最终报告已经完成。
    INVESTIGATION_FAILED = "investigation.failed"  # 整个调查任务失败。


class InvestigationRecord(DomainModel):
    """应用元数据,完整 Graph State 仍保存在 Checkpointer 中。"""

    # API 调查任务的唯一标识, 统一使用 inv_ 前缀。
    investigation_id: str = Field(pattern=r"^inv_[a-f0-9]{32}$")
    # 任务正在调查的故障事件标识。
    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # LangGraph Checkpoint 用于暂停恢复的稳定线程标识。
    thread_id: str = Field(pattern=r"^thread_[a-f0-9]{32}$")
    # 当前这次 Graph 运行的关联标识。
    run_id: str = Field(pattern=r"^run_[a-f0-9]{32}$")
    # 任务对 API 调用方公开的生命周期状态。
    status: InvestigationStatus = InvestigationStatus.PENDING
    # 创建任务时已经规范化的故障上下文。
    incident: IncidentContext
    # 创建任务时固定的调查预算选项。
    options: InvestigationOptions
    # 请求规范 JSON 的 SHA-256, 用于验证幂等键语义一致。
    request_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    # 调用方提供的可选幂等键。
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    # 调查完成后的最终报告投影。
    report: IncidentReport | None = None
    # 暂停等待审核时的安全审核请求投影。
    review_request: HumanReviewRequest | None = None
    # 任务失败时可以公开的脱敏错误说明。
    error_message: str | None = Field(default=None, max_length=500)
    # 任务最初创建时间。
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    # 任务最近一次状态更新时间。
    updated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    # Repository 乐观锁使用的递增版本号。
    version: int = Field(default=1, ge=1)


class InvestigationEvent(DomainModel):
    """单调递增且可重放、绝不包含 checkpoint 原始 State 的事件。"""

    # SSE 事件结构的版本。
    schema_version: str = "1.0"
    # 事件唯一标识, 包含任务随机部分和顺序号。
    event_id: str = Field(pattern=r"^evt_[a-f0-9]{32}_[0-9]+$")
    # 同一任务内严格从 1 递增的事件顺序号。
    sequence: int = Field(ge=1)
    # 前端和 API 客户端用于分支处理的事件类型。
    event_type: EventType
    # 产生事件的 API 调查任务标识。
    investigation_id: str = Field(pattern=r"^inv_[a-f0-9]{32}$")
    # 产生事件的故障事件标识。
    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 产生事件的 Graph Checkpoint 线程标识。
    thread_id: str = Field(pattern=r"^thread_[a-f0-9]{32}$")
    # 产生事件的 Graph 运行标识。
    run_id: str = Field(pattern=r"^run_[a-f0-9]{32}$")
    # 事件实际发生的 UTC 时间。
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    # 已裁剪、可以安全通过 SSE 公开的事件数据。
    data: dict[str, JsonValue] = Field(default_factory=dict)
