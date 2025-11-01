from __future__ import annotations

import asyncio
from typing import List

import pytest

from emergency_agents.voice.asr.base import ASRConfig, ASRProvider, ASRResult
from emergency_agents.voice.asr.manager import ASRManager


class DummyProvider(ASRProvider):
    """测试用ASR Provider，支持按序列注入失败。"""

    def __init__(
        self,
        name: str,
        priority: int,
        failure_sequence: List[bool],
    ) -> None:
        self._name = name
        self._priority = priority
        self._failure_sequence = list(failure_sequence)
        self.recognize_calls = 0
        self.health_checks = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def recognize(self, audio_data: bytes, config: ASRConfig | None = None) -> ASRResult:
        self.recognize_calls += 1
        should_fail = self._failure_sequence.pop(0) if self._failure_sequence else False
        if should_fail:
            raise RuntimeError(f"{self._name} recognize failure")
        return ASRResult(text="识别成功", provider=self._name, confidence=0.9, latency_ms=100)

    async def health_check(self) -> bool:
        self.health_checks += 1
        return True


def test_primary_provider_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """主Provider健康时应直接使用主Provider。"""

    monkeypatch.setenv("ASR_PRIMARY_PROVIDER", "primary")
    monkeypatch.setenv("ASR_FALLBACK_PROVIDER", "fallback")

    primary = DummyProvider("primary", priority=100, failure_sequence=[False])
    fallback = DummyProvider("fallback", priority=50, failure_sequence=[False])

    manager = ASRManager(providers=[primary, fallback])
    result = asyncio.run(manager.recognize(b"audio-bytes"))

    assert result.provider == "primary"
    assert primary.recognize_calls == 1
    assert fallback.recognize_calls == 0


def test_failover_when_primary_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """主Provider失败时应自动降级到备用Provider。"""

    monkeypatch.setenv("ASR_PRIMARY_PROVIDER", "primary")
    monkeypatch.setenv("ASR_FALLBACK_PROVIDER", "fallback")
    monkeypatch.setenv("ASR_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("ASR_RECOVERY_SECONDS", "5")

    primary = DummyProvider("primary", priority=100, failure_sequence=[True])
    fallback = DummyProvider("fallback", priority=80, failure_sequence=[False])

    manager = ASRManager(providers=[primary, fallback])

    result = asyncio.run(manager.recognize(b"audio-bytes"))

    assert result.provider == "fallback"
    assert primary.recognize_calls == 1
    assert fallback.recognize_calls == 1

    status_primary = manager._provider_status["primary"]
    assert status_primary.consecutive_failures == 1
    assert status_primary.available is False
