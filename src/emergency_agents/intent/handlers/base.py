from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from emergency_agents.intent.schemas import BaseSlots

SlotsT = TypeVar("SlotsT", bound=BaseSlots)


class IntentHandler(Generic[SlotsT], ABC):
    """Intent Handler 基类。"""

    @abstractmethod
    async def handle(self, slots: SlotsT, state: dict[str, object]) -> dict[str, object]:
        """处理意图，返回状态更新。"""
