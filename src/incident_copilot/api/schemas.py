"""稳定的 API 响应 Schema。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ApiModel(BaseModel):
    """公开 API Schema 使用的严格基类。"""

    # API 输入输出遇到未声明字段时直接报错, 避免拼写错误被悄悄忽略。
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    """不探测可选基础设施的存活响应。"""

    # 固定为 ok, 表示当前 API 进程仍可响应请求。
    status: Literal["ok"] = "ok"
    # 当前应用的名称, 默认是 IncidentCopilot。
    service: str
    # 当前应用版本, 来自 incident_copilot.__version__。
    version: str
    # 当前运行环境, 例如 development 或 production。
    environment: str


class ErrorDetail(ApiModel):
    """机器可读且安全的错误说明。"""

    # 供客户端程序判断错误类型的稳定机器码。
    code: str
    # 经过脱敏、可以安全展示给用户的错误说明。
    message: str
    # 与错误有关的安全结构化信息, 不包含原始敏感输入。
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    """预期应用错误和校验错误使用的响应外层结构。"""

    # 本次请求的具体错误内容。
    error: ErrorDetail
    # 关联客户端请求、服务端日志和错误响应的请求标识。
    request_id: str
