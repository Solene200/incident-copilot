"""Graph 与应用层共享的人工审核值。"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from incident_copilot.domain.common import DomainModel
from incident_copilot.domain.hypothesis import VerificationQuery


class ReviewAction(StrEnum):
    """暂停中的调查可以接受的白名单决策。"""

    ACCEPT = "accept"
    REQUEST_MORE_RESEARCH = "request_more_research"


class HumanFeedback(DomainModel):
    """经过校验的恢复载荷,绝不接受任意 Graph 命令。"""

    action: ReviewAction
    comment: str | None = Field(default=None, max_length=2_000)
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

    schema_version: str = "1.0"
    report_id: str = Field(pattern=r"^rpt_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    reason: str = Field(min_length=1, max_length=500)
    high_risk_actions: tuple[str, ...] = Field(min_length=1, max_length=20)
    allowed_actions: tuple[ReviewAction, ...] = (
        ReviewAction.ACCEPT,
        ReviewAction.REQUEST_MORE_RESEARCH,
    )
