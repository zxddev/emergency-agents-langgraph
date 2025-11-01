from __future__ import annotations

from types import SimpleNamespace

import pytest

from emergency_agents.llm.endpoint_manager import LLMEndpointConfig
from emergency_agents.llm.factory import LLMClientFactory


class _StubManager:
    def __init__(self, endpoints) -> None:
        self.endpoints = tuple(endpoints)
        self.call_sync_invocations = 0
        self.call_async_invocations = 0

    def call_sync(self, *_args, **_kwargs):
        self.call_sync_invocations += 1
        raise RuntimeError("stub manager should not execute sync calls in tests")

    async def call_async(self, *_args, **_kwargs):
        self.call_async_invocations += 1
        raise RuntimeError("stub manager should not execute async calls in tests")


@pytest.mark.parametrize("scope,expected", [("rescue", "rescue-primary"), ("intent", "intent-primary"), ("unknown", "default-primary")])
def test_llm_client_factory_scope_resolution(monkeypatch: pytest.MonkeyPatch, scope: str, expected: str) -> None:
    captured: dict[str, tuple[LLMEndpointConfig, ...]] = {}

    def fake_from_endpoints(endpoints, **kwargs):
        captured["endpoints"] = tuple(endpoints)
        captured["kwargs"] = kwargs
        return _StubManager(endpoints)

    monkeypatch.setattr(
        "emergency_agents.llm.endpoint_manager.LLMEndpointManager.from_endpoints",
        fake_from_endpoints,
    )

    config = SimpleNamespace(
        llm_endpoint_groups={
            "default": (
                LLMEndpointConfig(name="default-primary", base_url="https://default", api_key="default-key"),
            ),
            "rescue": (
                LLMEndpointConfig(name="rescue-primary", base_url="https://rescue", api_key="rescue-key"),
            ),
            "intent": (
                LLMEndpointConfig(name="intent-primary", base_url="https://intent", api_key="intent-key"),
            ),
        },
        llm_endpoints=(
            LLMEndpointConfig(name="fallback-primary", base_url="https://fallback", api_key="fallback-key"),
        ),
        llm_failure_threshold=2,
        llm_recovery_seconds=30,
        llm_max_concurrency=5,
    )

    factory = LLMClientFactory(config)  # type: ignore[arg-type]
    client = factory.get_sync(scope)

    assert isinstance(client, object)
    endpoints_used = captured["endpoints"]
    assert endpoints_used[0].name == expected
    assert captured["kwargs"]["max_concurrency"] == 5

    # second调用应命中缓存，不再触发 from_endpoints
    captured.clear()
    factory.get_sync(scope)
    assert not captured
