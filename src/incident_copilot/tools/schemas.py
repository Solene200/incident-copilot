"""只读调查工具使用的严格输入输出。"""

from datetime import timedelta
from typing import Self

from pydantic import Field, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    normalize_optional_service,
)
from incident_copilot.domain.evidence import Evidence

# 单次时间范围工具允许查询的最大时间跨度。
MAX_QUERY_WINDOW = timedelta(hours=24)


class QueryContext(DomainModel):
    """由编排层提供且不会泄漏 Graph State 的单次调用控制参数。"""

    # 关联一次工具调用及其日志的唯一追踪标识。
    correlation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    # 本次调用必须结束的绝对时间。
    deadline: AwareDatetime
    # Graph 在发起调用前剩余的工具调用预算。
    remaining_tool_calls: int = Field(ge=0, le=1_000)


class ToolInput(DomainModel):
    """强制执行共享规范化服务契约的输入基类。"""

    # 当前工具查询限定的服务名称。
    service: str = Field(min_length=1, max_length=128)

    @field_validator("service")
    @classmethod
    def normalize_service(cls, value: str) -> str:
        normalized = normalize_optional_service(value)
        if normalized is None:  # pragma: no cover - required field prevents this path
            raise ValueError("service is required")
        return normalized


class TimeRangeToolInput(ToolInput):
    """共享的有界时间范围和结果数量限制。"""

    # 工具查询时间窗口的起点。
    start_time: AwareDatetime
    # 工具查询时间窗口的终点。
    end_time: AwareDatetime
    # Provider 最多允许返回的 Evidence 数量。
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        if self.end_time - self.start_time > MAX_QUERY_WINDOW:
            raise ValueError("query window must not exceed 24 hours")
        return self


class SearchLogsInput(TimeRangeToolInput):
    """不依赖厂商查询语法的已校验日志搜索意图。"""

    # 日志必须匹配的可选文本条件。
    query: str | None = Field(default=None, min_length=1, max_length=256)


class QueryMetricsInput(TimeRangeToolInput):
    """针对预聚合指标序列的已校验请求。"""

    # 领域指标白名单中的名称, 不是任意 PromQL。
    metric_name: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{0,127}$")
    # 对时间序列执行的聚合方式, 例如最大值或 p95。
    aggregation: str = Field(default="max", pattern=r"^(avg|max|min|p95|rate)$")


class QueryTracesInput(TimeRangeToolInput):
    """经过校验的 Trace 搜索过滤条件。"""

    # 可选的调用操作名称, 例如 HTTP 路由或 RPC 方法。
    operation: str | None = Field(default=None, min_length=1, max_length=128)
    # 可选的 Trace 结果状态过滤条件。
    status: str | None = Field(default=None, pattern=r"^(ok|error|timeout)$")


class GetServiceTopologyInput(ToolInput):
    """经过校验的指定时间点拓扑查询。"""

    # 希望查看服务拓扑快照的时间点。
    at_time: AwareDatetime
    # 从目标服务向外展开依赖关系的最大层数。
    depth: int = Field(default=1, ge=1, le=3)
    # Provider 最多允许返回的拓扑 Evidence 数量。
    limit: int = Field(default=20, ge=1, le=50)


class GetRecentChangesInput(TimeRangeToolInput):
    """经过校验的部署和配置变更查询。"""

    # 可选的变更类型, 例如部署、配置或功能开关。
    change_type: str | None = Field(
        default=None,
        pattern=r"^(deployment|configuration|feature_flag|infrastructure)$",
    )


class SearchRunbooksInput(ToolInput):
    """经过校验的 Runbook 搜索请求。"""

    # 用于检索故障处理手册的自然语言问题。
    query: str = Field(min_length=2, max_length=256)
    # 最多返回的 Runbook Evidence 数量。
    limit: int = Field(default=5, ge=1, le=20)


class SearchSimilarIncidentsInput(ToolInput):
    """经过校验的历史事故搜索请求。"""

    # 用于检索相似历史故障的自然语言问题。
    query: str = Field(min_length=2, max_length=256)
    # 只检索这个时间点之前发生的历史故障。
    before_time: AwareDatetime
    # 从 before_time 向前回溯的天数。
    lookback_days: int = Field(default=90, ge=1, le=365)
    # 最多返回的历史故障 Evidence 数量。
    limit: int = Field(default=5, ge=1, le=20)


class ToolExecutionResult(DomainModel):
    """统一 Registry Wrapper 返回的实际测量结果。"""

    # 实际执行完成的白名单工具名称。
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    # Provider 返回并通过 Registry 校验的完整证据。
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple, max_length=50)
    # 包含第一次调用在内的实际尝试次数。
    attempts: int = Field(ge=1, le=10)
    # Registry 测量的整个工具执行耗时毫秒数。
    duration_ms: int = Field(ge=0)
