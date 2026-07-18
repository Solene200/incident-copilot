"""Allow-listed tool registry with validation, timeout, retry, and telemetry."""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Generic, TypeVar, cast

from pydantic import ValidationError

from incident_copilot.domain.common import SourceType
from incident_copilot.domain.evidence import Evidence
from incident_copilot.tools.exceptions import (
    ProviderError,
    ProviderMalformedResponseError,
    ProviderTimeoutError,
    ToolBudgetExceededError,
    ToolExecutionError,
    ToolInvalidArgumentsError,
    ToolNotFoundError,
    ToolRegistrationError,
)
from incident_copilot.tools.schemas import QueryContext, ToolExecutionResult, ToolInput

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=ToolInput)
ToolHandler = Callable[[InputT, QueryContext], Awaitable[Sequence[Evidence]]]


@dataclass(frozen=True, slots=True)
class ToolDefinition(Generic[InputT]):
    """One allow-listed tool and the policy applied to its provider call."""

    name: str
    input_model: type[InputT]
    handler: ToolHandler[InputT]
    expected_sources: frozenset[SourceType]
    timeout_seconds: float = 2.0
    max_retries: int = 1

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.name) is None:
            raise ValueError("tool name must contain lowercase letters, digits, and underscores")
        if not self.expected_sources:
            raise ValueError("tool must declare at least one expected evidence source")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 30:
            raise ValueError("tool timeout must be greater than 0 and at most 30 seconds")
        if self.max_retries < 0 or self.max_retries > 3:
            raise ValueError("tool max_retries must be between 0 and 3")


class ToolRegistry:
    """Execute only registered tools through one policy and error boundary."""

    def __init__(self, *, retry_backoff_seconds: float = 0.01) -> None:
        if retry_backoff_seconds < 0 or retry_backoff_seconds > 1:
            raise ValueError("retry_backoff_seconds must be between 0 and 1")
        self._retry_backoff_seconds = retry_backoff_seconds
        self._tools: dict[str, ToolDefinition[ToolInput]] = {}

    @property
    def tool_names(self) -> tuple[str, ...]:
        """Return a stable discovery list without exposing provider instances."""
        return tuple(sorted(self._tools))

    def register(self, definition: ToolDefinition[InputT]) -> None:
        """Register one definition and reject accidental name replacement."""
        if definition.name in self._tools:
            raise ToolRegistrationError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = cast(ToolDefinition[ToolInput], definition)

    async def execute(
        self,
        name: str,
        arguments: Mapping[str, object],
        context: QueryContext,
    ) -> ToolExecutionResult:
        """Validate and execute a tool within budget, timeout, and retry limits."""
        definition = self._tools.get(name)
        if definition is None:
            raise ToolNotFoundError(f"unknown tool: {name}")
        if context.remaining_tool_calls < 1:
            raise ToolBudgetExceededError("tool call budget exhausted")

        try:
            tool_input = definition.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolInvalidArgumentsError(f"invalid arguments for tool: {name}") from exc

        started = perf_counter()
        logger.info(
            "tool.started",
            extra={"tool_name": name, "correlation_id": context.correlation_id},
        )

        attempts = 0
        while attempts <= definition.max_retries:
            attempts += 1
            remaining_seconds = (context.deadline - datetime.now(UTC)).total_seconds()
            if remaining_seconds <= 0:
                failure: ProviderError = ProviderTimeoutError(
                    "tool deadline exceeded",
                    provider_name="tool-registry",
                    operation=name,
                )
            else:
                attempt_timeout = min(definition.timeout_seconds, remaining_seconds)
                try:
                    evidence = await asyncio.wait_for(
                        definition.handler(tool_input, context),
                        timeout=attempt_timeout,
                    )
                    checked_evidence = self._validate_evidence(definition, evidence)
                except TimeoutError as exc:
                    failure = ProviderTimeoutError(
                        "provider call timed out",
                        provider_name="tool-registry",
                        operation=name,
                    )
                    failure.__cause__ = exc
                except ProviderError as exc:
                    failure = exc
                except Exception as exc:
                    failure = ProviderError(
                        "provider raised an unexpected error",
                        provider_name="tool-registry",
                        operation=name,
                    )
                    failure.__cause__ = exc
                else:
                    duration_ms = int((perf_counter() - started) * 1_000)
                    result = ToolExecutionResult(
                        tool_name=name,
                        evidence=checked_evidence,
                        attempts=attempts,
                        duration_ms=duration_ms,
                    )
                    logger.info(
                        "tool.completed",
                        extra={
                            "tool_name": name,
                            "correlation_id": context.correlation_id,
                            "attempts": attempts,
                            "result_count": len(checked_evidence),
                            "duration_ms": duration_ms,
                        },
                    )
                    return result

            if failure.retryable and attempts <= definition.max_retries:
                backoff = self._retry_backoff_seconds * (2 ** (attempts - 1))
                remaining_seconds = (context.deadline - datetime.now(UTC)).total_seconds()
                if backoff < remaining_seconds:
                    await asyncio.sleep(backoff)
                    continue

            duration_ms = int((perf_counter() - started) * 1_000)
            logger.warning(
                "tool.failed",
                extra={
                    "tool_name": name,
                    "correlation_id": context.correlation_id,
                    "attempts": attempts,
                    "duration_ms": duration_ms,
                    "error_category": failure.category.value,
                },
            )
            raise ToolExecutionError(
                f"tool execution failed: {name}",
                tool_name=name,
                category=failure.category,
                attempts=attempts,
                retryable=failure.retryable,
            ) from failure

        raise AssertionError("bounded retry loop exited unexpectedly")  # pragma: no cover

    @staticmethod
    def _validate_evidence(
        definition: ToolDefinition[ToolInput], evidence: Sequence[Evidence]
    ) -> tuple[Evidence, ...]:
        checked: list[Evidence] = []
        for item in evidence:
            if not isinstance(item, Evidence):
                raise ProviderMalformedResponseError(
                    "provider returned a non-Evidence value",
                    provider_name="tool-registry",
                    operation=definition.name,
                )
            if item.source_type not in definition.expected_sources:
                raise ProviderMalformedResponseError(
                    "provider returned an unexpected evidence source",
                    provider_name=item.source_name,
                    operation=definition.name,
                )
            if item.service is None:
                raise ProviderMalformedResponseError(
                    "provider evidence must identify a service",
                    provider_name=item.source_name,
                    operation=definition.name,
                )
            if item.timestamp is None and item.start_time is None:
                raise ProviderMalformedResponseError(
                    "provider evidence must include a timestamp or time window",
                    provider_name=item.source_name,
                    operation=definition.name,
                )
            checked.append(item)
        if len(checked) > 50:
            raise ProviderMalformedResponseError(
                "provider returned more than 50 evidence items",
                provider_name="tool-registry",
                operation=definition.name,
            )
        return tuple(checked)
