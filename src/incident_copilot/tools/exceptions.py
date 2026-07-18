"""Normalized provider and tool execution failures."""

from enum import StrEnum


class ProviderErrorCategory(StrEnum):
    """Stable failure categories shared by provider adapters and tool callers."""

    INVALID_QUERY = "invalid_query"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    MALFORMED_RESPONSE = "malformed_response"
    INTERNAL = "internal"


class ProviderError(Exception):
    """Base provider failure with retry classification and safe context."""

    category = ProviderErrorCategory.INTERNAL
    retryable = False

    def __init__(self, message: str, *, provider_name: str, operation: str) -> None:
        super().__init__(message)
        self.message = message
        self.provider_name = provider_name
        self.operation = operation


class ProviderInvalidQueryError(ProviderError):
    """A provider rejected a semantically invalid query."""

    category = ProviderErrorCategory.INVALID_QUERY


class ProviderTimeoutError(ProviderError):
    """A provider did not complete inside its bounded timeout."""

    category = ProviderErrorCategory.TIMEOUT
    retryable = True


class ProviderUnavailableError(ProviderError):
    """A provider is temporarily unavailable."""

    category = ProviderErrorCategory.UNAVAILABLE
    retryable = True


class ProviderRateLimitedError(ProviderError):
    """A provider temporarily rejected work due to rate limiting."""

    category = ProviderErrorCategory.RATE_LIMITED
    retryable = True


class ProviderMalformedResponseError(ProviderError):
    """A provider returned data that violates the evidence contract."""

    category = ProviderErrorCategory.MALFORMED_RESPONSE


class ToolError(Exception):
    """Base class for safe failures exposed by the tool layer."""


class ToolRegistrationError(ToolError):
    """A registry definition is invalid or conflicts with an existing tool."""


class ToolNotFoundError(ToolError):
    """A caller requested a tool outside the registry allow-list."""


class ToolInvalidArgumentsError(ToolError):
    """Tool arguments failed strict schema validation."""


class ToolBudgetExceededError(ToolError):
    """The caller has no remaining tool-call budget."""


class ToolExecutionError(ToolError):
    """A provider failure normalized at the tool boundary."""

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
