"""不依赖传输框架的应用异常层次。"""

from enum import StrEnum
from typing import ClassVar

from pydantic import JsonValue


class ErrorCode(StrEnum):
    """传输 Adapter 对外公开的稳定错误码。"""

    DOMAIN_VALIDATION = "domain_validation_error"  # 输入违反领域业务规则。
    CONFIGURATION = "configuration_error"  # 运行配置缺失或组合不合法。
    NOT_FOUND = "resource_not_found"  # 请求的任务或资源不存在。
    CONFLICT = "resource_conflict"  # 当前状态或幂等键与操作冲突。
    INTERNAL = "internal_error"  # 不应向外暴露细节的内部错误。


class IncidentCopilotError(Exception):
    """携带安全公开消息和结构化详情的基础异常。"""

    # 子类覆盖的稳定公开错误码。
    code: ClassVar[ErrorCode] = ErrorCode.INTERNAL
    # API Adapter 映射使用的默认 HTTP 状态码。
    status_code: ClassVar[int] = 500

    def __init__(self, message: str, *, details: dict[str, JsonValue] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DomainValidationError(IncidentCopilotError):
    """传输请求格式有效但违反领域规则时抛出。"""

    # 对外表示领域规则校验失败。
    code: ClassVar[ErrorCode] = ErrorCode.DOMAIN_VALIDATION
    # 请求格式合法但业务语义错误时返回 400。
    status_code: ClassVar[int] = 400


class ConfigurationError(IncidentCopilotError):
    """运行时配置无法支持某项操作时抛出。"""

    # 对外表示服务端配置无法支持当前操作。
    code: ClassVar[ErrorCode] = ErrorCode.CONFIGURATION
    # 配置错误属于服务端问题。
    status_code: ClassVar[int] = 500


class ResourceNotFoundError(IncidentCopilotError):
    """请求的应用资源不存在时抛出。"""

    # 对外表示目标资源不存在。
    code: ClassVar[ErrorCode] = ErrorCode.NOT_FOUND
    # 不存在的资源映射为 404。
    status_code: ClassVar[int] = 404


class ResourceConflictError(IncidentCopilotError):
    """状态转换或幂等键无法应用时抛出。"""

    # 对外表示资源当前状态不允许执行操作。
    code: ClassVar[ErrorCode] = ErrorCode.CONFLICT
    # 幂等冲突和重复恢复等情况映射为 409。
    status_code: ClassVar[int] = 409
