from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from emergency_agents.llm.endpoint_manager import (
    LLMEndpointConfig,
    LLMEndpointManager,
)
from emergency_agents.llm.client import FailoverLLMClient, FailoverAsyncLLMClient


class _StubSyncClient:
    """同步客户端桩：根据预设队列返回结果或抛出异常。"""

    def __init__(self, name: str, queue: List[Any]) -> None:
        self._name = name
        self._queue = queue
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create),
        )

    def _create(self, *args: Any, **kwargs: Any) -> Any:
        if not self._queue:
            raise RuntimeError(f"{self._name} queue exhausted")
        action = self._queue.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class _StubAsyncClient:
    """异步客户端桩，与同步版本共享相同的行为队列。"""

    def __init__(self, name: str, queue: List[Any]) -> None:
        self._name = name
        self._queue = queue
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create),
        )

    async def _create(self, *args: Any, **kwargs: Any) -> Any:
        if not self._queue:
            raise RuntimeError(f"{self._name} queue exhausted")
        action = self._queue.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


def _build_manager(primary_responses: List[Any], backup_responses: List[Any]) -> LLMEndpointManager:
    """构建带有桩客户端的端点管理器。"""

    queues: Dict[str, List[Any]] = {
        "primary": primary_responses,
        "backup": backup_responses,
    }

    endpoints = [
        LLMEndpointConfig(name="primary", base_url="https://primary", api_key="k1", priority=100),
        LLMEndpointConfig(name="backup", base_url="https://backup", api_key="k2", priority=80),
    ]

    def build_sync(endpoint: LLMEndpointConfig) -> _StubSyncClient:
        return _StubSyncClient(endpoint.name, queues[endpoint.name])

    def build_async(endpoint: LLMEndpointConfig) -> _StubAsyncClient:
        return _StubAsyncClient(endpoint.name, queues[endpoint.name])

    return LLMEndpointManager(
        endpoints=endpoints,
        failure_threshold=2,
        recovery_seconds=30,
        sync_client_builder=build_sync,
        async_client_builder=build_async,
    )


def test_failover_llm_client_primary_success() -> None:
    manager = _build_manager(primary_responses=[{"provider": "primary"}], backup_responses=[{"provider": "backup"}])
    client = FailoverLLMClient(manager)
    result = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
    assert result["provider"] == "primary"


def test_failover_llm_client_switch_to_backup_on_failure() -> None:
    manager = _build_manager(
        primary_responses=[RuntimeError("boom"), RuntimeError("boom")],
        backup_responses=[{"provider": "backup"}],
    )
    client = FailoverLLMClient(manager)
    result = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
    assert result["provider"] == "backup"
    snapshot = manager.status_snapshot()
    assert snapshot["primary"]["available"] is False
    assert snapshot["backup"]["available"] is True


@pytest.mark.asyncio
async def test_failover_async_llm_client_switch_to_backup_on_failure() -> None:
    manager = _build_manager(
        primary_responses=[RuntimeError("boom"), RuntimeError("boom")],
        backup_responses=[{"provider": "backup_async"}],
    )
    client = FailoverAsyncLLMClient(manager)
    result = await client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
    assert result["provider"] == "backup_async"
