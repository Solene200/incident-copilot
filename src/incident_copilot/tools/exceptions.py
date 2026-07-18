"""规范化的 Provider 和工具执行失败。"""

from enum import StrEnum


class ProviderErrorCategory(StrEnum):
    """Provider Adapter 和工具调用方共享的稳定失败类别。"""

    INVALID_QUERY = "invalid_query"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    MALFORMED_RESPONSE = "malformed_response"
    INTERNAL = "internal"


class ProviderError(Exception):
    """带有重试分类和安全上下文的 Provider 基础失败。"""

    category = ProviderErrorCategory.INTERNAL
    retryable = False

    def __init__(self, message: str, *, provider_name: str, operation: str) -> None:
        super().__init__(message)
        self.message = message
        self.provider_name = provider_name
        self.operation = operation


class ProviderInvalidQueryError(ProviderError):
    """Provider 拒绝了语义无效的查询。"""

    category = ProviderErrorCategory.INVALID_QUERY


class ProviderTimeoutError(ProviderError):
    """Provider 未在有界超时内完成。"""

    category = ProviderErrorCategory.TIMEOUT
    retryable = True


class ProviderUnavailableError(ProviderError):
    """Provider 暂时不可用。"""

    category = ProviderErrorCategory.UNAVAILABLE
    retryable = True


class ProviderRateLimitedError(ProviderError):
    """Provider 因限流而暂时拒绝执行。"""

    category = ProviderErrorCategory.RATE_LIMITED
    retryable = True


class ProviderMalformedResponseError(ProviderError):
    """Provider 返回了违反证据契约的数据。"""

    category = ProviderErrorCategory.MALFORMED_RESPONSE


class ToolError(Exception):
    """工具层公开的安全失败基类。"""


class ToolRegistrationError(ToolError):
    """Registry 定义无效或与现有工具冲突。"""


class ToolNotFoundError(ToolError):
    """调用方请求了 Registry 白名单之外的工具。"""


class ToolInvalidArgumentsError(ToolError):
    """工具参数未通过严格 Schema 校验。"""


class ToolBudgetExceededError(ToolError):
    """调用方已经没有剩余工具调用预算。"""


class ToolExecutionError(ToolError):
    """在工具边界规范化后的 Provider 失败。"""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str,
        category: ProviderErrorCategory,
        attempts: int,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.tool_name = tool_name
        self.category = category
        self.attempts = attempts
        self.retryable = retryable
