from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from emergency_agents.db.dao import DeviceDAO, serialize_dataclass
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import VideoAnalysisSlots

logger = logging.getLogger(__name__)


@dataclass
class VideoAnalysisHandler(IntentHandler[VideoAnalysisSlots]):
    device_dao: DeviceDAO
    stream_map: Mapping[str, str]

    async def handle(self, slots: VideoAnalysisSlots, state: dict[str, object]) -> dict[str, object]:
        logger.info(
            "intent_request",
            extra={
                "intent": "video-analysis",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "target": slots.device_id,
                "status": "processing",
            },
        )

        device = await self.device_dao.fetch_video_device(slots.device_id)
        if device is None:
            return {
                "response_text": "暂未登记该设备，无法执行视频分析。",
                "video_analysis": {"status": "not_found"},
            }

        stream_url = device.stream_url or self.stream_map.get(device.id)
        if stream_url is None:
            return {
                "response_text": "设备缺少视频流地址，请运维补录 stream_url。",
                "video_analysis": {"status": "missing_stream"},
            }

        message = (
            f"已进入视频流分析流程（{device.name or device.id}）。"
            " 当前阶段为占位实现，等待视频处理模块接入。"
        )
        payload = {
            "status": "pending_pipeline",
            "device": serialize_dataclass(device) | {"stream_url": stream_url},
            "analysis_goal": slots.analysis_goal,
        }
        return {"response_text": message, "video_analysis": payload}
