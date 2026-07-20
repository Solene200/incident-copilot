"""调查 Graph 节点之间交换的已校验值。"""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    SourceType,
    unique_evidence_ids,
)
from incident_copilot.domain.hypothesis import Hypothesis, VerificationQuery
from incident_copilot.domain.review import HumanFeedback


def stable_query_key(tool_name: str, arguments: Mapping[str, object]) -> str:
    """在可信代码中计算查询标识,而不接受模型提供的标识。"""
    canonical = json.dumps(
        {"tool_name": tool_name, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class StepStatus(StrEnum):
    """一个只读调查工具步骤的终止状态。"""

    COMPLETED = "completed"  # 工具步骤成功执行, 即使结果可以为空。
    FAILED = "failed"  # 工具步骤执行失败并关联 InvestigationError。
    SKIPPED = "skipped"  # 因去重或预算等原因没有实际执行。


class ErrorCategory(StrEnum):
    """可以安全暴露在报告中的稳定 Graph 级错误类别。"""

    VALIDATION = "validation"  # 参数或模型输出没有通过 Schema 校验。
    TIMEOUT = "timeout"  # 操作未在截止时间内完成。
    UNAVAILABLE = "unavailable"  # Provider 或外部依赖暂时不可用。
    MALFORMED_RESPONSE = "malformed_response"  # 外部响应违反预期数据契约。
    BUDGET = "budget"  # 调查轮数、调用数或 Token 预算不足。
    INTERNAL = "internal"  # 无法归入其他类别的内部失败。


class StopReason(StrEnum):
    """明确且可审计的调查循环结束原因。"""

    EVIDENCE_SUFFICIENT = "evidence_sufficient"  # 已收集证据足以生成报告。
    MAX_RESEARCH_ROUNDS = "max_research_rounds"  # 已达到允许的最大研究轮数。
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"  # 工具调用总预算已耗尽。
    MODEL_BUDGET_EXHAUSTED = "model_budget_exhausted"  # 模型调用总预算已耗尽。
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"  # 估算 Token 总预算已耗尽。
    DEADLINE_EXCEEDED = "deadline_exceeded"  # 整次调查超过绝对截止时间。


class InvestigationOptions(DomainModel):
    """由应用代码控制且模型永远不能修改的不可变调用预算。"""

    # 最多允许执行的调查研究轮数。
    max_research_rounds: int = Field(default=2, ge=1, le=5)
    # 整次调查最多允许终止的逻辑工具步骤数。
    max_tool_calls: int = Field(default=14, ge=1, le=100)
    # 整次调查最多允许的物理 Provider 尝试数,包括 retry。
    max_tool_attempts: int = Field(default=28, ge=1, le=400)
    # 一个批次最多同时运行的工具步骤数。
    max_parallel_tools: int = Field(default=7, ge=1, le=20)
    # 整次调查最多允许调用模型 Provider 的次数。
    max_model_calls: int = Field(default=20, ge=1, le=50)
    # 模型输入与输出 Token 的总估算上限。
    max_estimated_tokens: int = Field(default=20_000, ge=1, le=1_000_000)
    # 整次调查从开始到截止允许的秒数。
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)


class ModelTask(StrEnum):
    """Phase 4 使用的白名单结构化模型操作。"""

    PLAN = "plan"  # 生成初始或细化后的工具调查计划。
    HYPOTHESES = "hypotheses"  # 根据证据生成根因假设。
    JUDGE = "judge"  # 判断当前证据是否充分。
    REPORT = "report"  # 生成不含自由引用的报告叙事草稿。


class InvestigationStep(DomainModel):
    """为一轮调查生成的已校验白名单工具请求。"""

    # 工具步骤的唯一标识, 统一使用 step_ 前缀。
    step_id: str = Field(pattern=r"^step_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 根据工具名和参数计算的稳定查询哈希, 用于跨轮次去重。
    query_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    # ToolRegistry 白名单中的工具名称。
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    # 该工具步骤预期产生的 Evidence 来源类别。
    source_type: SourceType
    # 为什么本轮调查需要执行这个步骤。
    purpose: str = Field(min_length=1, max_length=1_000)
    # 提交给工具输入 Pydantic Schema 的 JSON 参数。
    arguments: dict[str, JsonValue]
    # 步骤调度优先级, 数字越大越先进入批次。
    priority: int = Field(default=50, ge=1, le=100)
    # 该步骤所属的研究轮次, 从 1 开始。
    round_number: int = Field(ge=1)


class InvestigationPlan(DomainModel):
    """步骤会由 Tool Registry 再次校验的有界计划。"""

    # 调查计划的唯一标识, 统一使用 plan_ 前缀。
    plan_id: str = Field(pattern=r"^plan_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 该计划对应的研究轮次。
    round_number: int = Field(ge=1)
    # 本轮调查希望解决的核心目标。
    objective: str = Field(min_length=1, max_length=1_000)
    # 本轮准备执行的有界工具步骤集合。
    steps: tuple[InvestigationStep, ...] = Field(default_factory=tuple, max_length=20)
    # 本轮计划希望覆盖的证据来源类别。
    coverage_targets: tuple[SourceType, ...] = Field(default_factory=tuple, max_length=6)
    # 模型为什么选择这些步骤和来源的解释。
    rationale: str = Field(min_length=1, max_length=2_000)

    @field_validator("coverage_targets")
    @classmethod
    def unique_sources(cls, values: tuple[SourceType, ...]) -> tuple[SourceType, ...]:
        return tuple(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_steps(self) -> Self:
        if any(step.round_number != self.round_number for step in self.steps):
            raise ValueError("plan steps must belong to the plan round")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("plan step ids must be unique")
        query_keys = [step.query_key for step in self.steps]
        if len(query_keys) != len(set(query_keys)):
            raise ValueError("plan queries must be unique")
        return self


class StepResult(DomainModel):
    """不包含原始证据载荷的工具步骤紧凑终止记录。"""

    # 对应 InvestigationStep 的唯一标识。
    step_id: str = Field(pattern=r"^step_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 对应步骤的稳定查询哈希。
    query_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    # 实际执行的工具名称。
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    # 实际提交给工具的安全 JSON 参数。
    arguments: dict[str, JsonValue] = Field(default_factory=dict, max_length=20)
    # 步骤最终是完成、失败还是跳过。
    status: StepStatus
    # 本步骤收集到的 Evidence ID, 不包含完整证据载荷。
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    # 失败步骤对应的 InvestigationError ID。
    error_id: str | None = Field(default=None, pattern=r"^err_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 本逻辑步骤消耗的物理 Provider 尝试次数, 包括第一次调用。
    attempts: int = Field(ge=0, le=10)
    # 工具步骤开始执行的时间。
    started_at: AwareDatetime
    # 工具步骤结束执行的时间。
    completed_at: AwareDatetime

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="step evidence ids")

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("step completion must not precede start")
        if self.status is StepStatus.FAILED and self.error_id is None:
            raise ValueError("failed step requires an error id")
        if self.status is StepStatus.COMPLETED and self.error_id is not None:
            raise ValueError("completed step must not reference an error")
        return self


class InvestigationError(DomainModel):
    """保存在有界 Graph State 中、经过脱敏的一等失败对象。"""

    # 调查错误的唯一标识, 统一使用 err_ 前缀。
    error_id: str = Field(pattern=r"^err_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 经过归一化的稳定错误类别。
    category: ErrorCategory
    # 发生错误的模块或组件名称。
    component: str = Field(min_length=1, max_length=128)
    # 失败时正在执行的具体操作名称。
    operation: str = Field(min_length=1, max_length=128)
    # 已脱敏、可以进入 State 和报告的错误说明。
    message: str = Field(min_length=1, max_length=1_000)
    # 相同操作在预算允许时是否值得重试。
    retryable: bool = False
    # 错误发生的 UTC 时间。
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    # 错误关联的工具步骤 ID, 非工具错误可以为 None。
    step_id: str | None = Field(default=None, pattern=r"^step_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 第几次尝试时发生该错误。
    attempt: int = Field(default=1, ge=1, le=10)


class ModelUsage(DomainModel):
    """单次调用用量,Fake Model 数值会明确标记为估算值。"""

    # 一次模型调用使用的输入 Token 数。
    input_tokens: int = Field(default=0, ge=0)
    # 一次模型调用生成的输出 Token 数。
    output_tokens: int = Field(default=0, ge=0)
    # Token 数是否由 Fake Model 估算。
    estimated: bool = False


class ModelResponse(DomainModel):
    """需要使用任务专属 Schema 再次校验的不可信 Provider 响应。"""

    # 尚未通过任务专属 Schema 校验的模型 JSON 载荷。
    payload: dict[str, JsonValue]
    # 本次模型调用报告或估算的 Token 用量。
    usage: ModelUsage = Field(default_factory=ModelUsage)


class PlanOutput(DomainModel):
    """初始或细化调查计划使用的结构化模型输出。"""

    # 模型为本轮调查给出的目标。
    objective: str = Field(min_length=1, max_length=1_000)
    # 模型建议、但仍需 ToolRegistry 校验的工具步骤。
    steps: tuple[InvestigationStep, ...] = Field(default_factory=tuple, max_length=20)
    # 模型选择当前计划的原因说明。
    rationale: str = Field(min_length=1, max_length=2_000)


class HypothesesOutput(DomainModel):
    """包含有界可证伪假设的结构化模型输出。"""

    # 模型生成并通过领域校验的根因假设集合。
    hypotheses: tuple[Hypothesis, ...] = Field(min_length=1, max_length=10)


class SufficiencyOutput(DomainModel):
    """结构化模型判断,最终路由仍由代码策略控制。"""

    # 模型认为当前证据是否足够生成可靠报告。
    sufficient: bool
    # 模型对充分或不充分判断的解释。
    reason: str = Field(min_length=1, max_length=2_000)
    # 证据不足时建议下一轮验证的问题。
    next_queries: tuple[VerificationQuery, ...] = Field(default_factory=tuple, max_length=10)


class ReportDraftOutput(DomainModel):
    """仅包含叙事的报告输出,由代码附加已验证 Evidence 引用。"""

    # 模型生成的报告摘要草稿。
    summary: str = Field(min_length=1, max_length=4_000)
    # 模型生成的根因草稿, 无结论时可以为 None。
    root_cause: str | None = Field(default=None, max_length=4_000)
    # 模型对当前结论可信程度的文字解释。
    confidence_rationale: str = Field(min_length=1, max_length=2_000)
    # 模型建议的修复动作文字, 代码随后附加风险和审核约束。
    remediation_actions: tuple[str, ...] = Field(min_length=1, max_length=10)
    # 模型识别出的风险说明。
    risks: tuple[str, ...] = Field(default_factory=tuple, max_length=10)


class ModelContext(DomainModel):
    """传给模型 Provider 的有界证据包。"""

    # 本次要求模型完成的白名单任务类型。
    task: ModelTask
    # 当前故障事件标识。
    incident_id: str = Field(pattern=r"^inc_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 当前模型调用主要关注的服务。
    service: str = Field(min_length=1, max_length=128)
    # 用户提交的原始调查问题。
    raw_query: str = Field(min_length=1, max_length=10_000)
    # 用户已经观察到的症状; Planner 只能使用公开调查上下文和已收集证据。
    symptoms: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    # 调查证据时间窗口起点。
    start_time: AwareDatetime
    # 调查证据时间窗口终点。
    end_time: AwareDatetime
    # 当前研究轮次。
    research_round: int = Field(ge=1)
    # 发送给模型的有界证据摘要, 不包含完整原始载荷。
    evidence_summaries: tuple[dict[str, JsonValue], ...] = Field(
        default_factory=tuple, max_length=100
    )
    # 当前已经生成并验证过的根因假设。
    hypotheses: tuple[Hypothesis, ...] = Field(default_factory=tuple, max_length=10)
    # 证据不足或人工反馈提出的下一步查询。
    next_investigation_queries: tuple[VerificationQuery, ...] = Field(
        default_factory=tuple, max_length=10
    )
    # 恢复调查时经过校验的人工反馈。
    human_feedback: HumanFeedback | None = None
    # 当前调查已记录的错误数量, 帮助模型诚实描述覆盖缺口。
    error_count: int = Field(default=0, ge=0)


class RouteTarget(StrEnum):
    """判断后路由唯一允许选择的目标。"""

    REFINE = "refine_investigation"  # 证据不足且预算允许时细化下一轮计划。
    REPORT = "generate_report"  # 证据充分或必须停止时生成报告。


# 报告生成内部状态, complete 表示完整, limited 表示受数据或预算限制。
ReportStatus = Literal["complete", "limited"]
