from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import structlog

from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import BaseSlots


logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class DisasterOverviewHandler(IntentHandler[BaseSlots]):
    """整体灾情分析占位，实现后续态势研判接入。"""

    async def handle(self, slots: BaseSlots, state: Dict[str, object]) -> Dict[str, object]:
        thread_id = state.get("thread_id")
        logger.info("disaster_overview_placeholder", thread_id=thread_id)
        message = (
            "已记录整体灾情分析请求，目前正在接入态势研判流程，请稍后重试或联系值守分析员。"
        )
        return {
            "response_text": message,
            "disaster_overview": {"status": "pending", "thread_id": thread_id},
        }
