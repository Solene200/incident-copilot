"""Graph 与应用层共享的人工审核值。"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from incident_copilot.domain.common import DomainModel
from incident_copilot.domain.hypothesis import VerificationQuery


class ReviewAction(StrEnum):
    """暂停中的调查可以接受的白名单决策。"""

    ACCEPT = "accept"  # 审核人接受当前报告和高风险建议。
    REQUEST_MORE_RESEARCH = "request_more_research"  # 审核人要求追加一轮指定调查。


class HumanFeedback(DomainModel):
    """经过校验的恢复载荷,绝不接受任意 Graph 命令。"""

    # 审核人选择的白名单决策。
    action: ReviewAction
    # 审核人提供的可选文字说明。
    comment: str | None = Field(default=None, max_length=2_000)
    # 要求追加调查时必须提供的具体验证查询。
    requested_queries: tuple[VerificationQuery, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_action_payload(self) -> Self:
        if self.action is ReviewAction.ACCEPT and self.requested_queries:
            raise ValueError("accept feedback must not include requested queries")
        if self.action is ReviewAction.REQUEST_MORE_RESEARCH and not self.requested_queries:
            raise ValueError("additional research requires at least one query")
        return self


class HumanReviewRequest(DomainModel):
    """不包含 Graph 原始 State、可安全序列化为 JSON 的小型中断载荷。"""

    # 人工审核载荷的结构版本。
    schema_version: str = "1.0"
    # 等待审核的报告唯一标识。
    report_id: str = Field(pattern=r"^rpt_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 为什么当前调查必须暂停等待人工确认。
    reason: str = Field(min_length=1, max_length=500)
    # 报告中触发审核的高风险修复动作。
    high_risk_actions: tuple[str, ...] = Field(min_length=1, max_length=20)
    # 本次暂停允许审核人提交的决策白名单。
    allowed_actions: tuple[ReviewAction, ...] = (
        ReviewAction.ACCEPT,
        ReviewAction.REQUEST_MORE_RESEARCH,
    )
