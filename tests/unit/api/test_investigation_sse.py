"""不依赖实际时间等待的 SSE 心跳和客户端断开行为测试。"""

from collections.abc import AsyncGenerator
from typing import cast

import pytest
from fastapi import Request

from incident_copilot.api.routes.investigations import _event_stream
from incident_copilot.investigations.models import InvestigationStatus
from incident_copilot.investigations.service import InvestigationService


class EmptyEventRepository:
    """立即返回空事件,使心跳行为保持确定性。"""

    def __init__(self) -> None:
        self.wait_calls = 0

    async def list_events(
        self,
        investigation_id: str,
        *,
        after_sequence: int = 0,
    ) -> tuple[()]:
        del investigation_id, after_sequence
        return ()

    async def wait_for_events(
        self,
        investigation_id: str,
        *,
        after_sequence: int,
        timeout_seconds: float,
    ) -> tuple[()]:
        del investigation_id, after_sequence, timeout_seconds
        self.wait_calls += 1
        return ()


class RunningService:
    """只通过显式测试类型转换使用的最小 Service 投影。"""

    def __init__(self) -> None:
        self.repository = EmptyEventRepository()

    async def get(self, investigation_id: str) -> object:
        del investigation_id
        return type("RunningRecord", (), {"status": InvestigationStatus.RUNNING})()


class DisconnectRequest:
    def __init__(self, disconnected: bool) -> None:
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.asyncio
async def test_running_stream_emits_heartbeat_after_idle_wait() -> None:
    service = RunningService()
    stream = cast(
        AsyncGenerator[str, None],
        _event_stream(
            cast(InvestigationService, service),
            "inv_test",
            cast(Request, DisconnectRequest(False)),
            after_sequence=0,
            heartbeat_seconds=0.01,
        ),
    )

    assert await anext(stream) == ": heartbeat\n\n"
    assert service.repository.wait_calls == 1
    await stream.aclose()


@pytest.mark.asyncio
async def test_disconnected_stream_stops_before_waiting() -> None:
    service = RunningService()
    stream = _event_stream(
        cast(InvestigationService, service),
        "inv_test",
        cast(Request, DisconnectRequest(True)),
        after_sequence=0,
        heartbeat_seconds=0.01,
    )

    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert service.repository.wait_calls == 0
