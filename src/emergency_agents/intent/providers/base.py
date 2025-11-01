from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from emergency_agents.intent.providers.types import IntentPrediction


@dataclass(frozen=True)
class IntentThresholds:
    """意图阈值配置。"""

    confidence: float
    margin: float


class IntentProvider(ABC):
    """意图识别提供者抽象基类。"""

    def __init__(self, source: str) -> None:
        self._source = source

    @property
    def source(self) -> str:
        return self._source

    @abstractmethod
    def predict(self, text: str) -> IntentPrediction:
        """执行意图识别。"""
