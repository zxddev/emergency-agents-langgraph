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
        """视频分析意图处理

        Args:
            slots: 视频分析槽位（设备ID、分析目标）
            state: 会话状态

        Returns:
            处理结果（当前未实现，会抛出错误）

        Raises:
            NotImplementedError: 视频分析功能尚未实现

        Reference:
            - 代码审查报告-强类型与@task合规性.md 第3.1节：占位代码检查
            - 不做降级/fallback/mock 原则：直接暴露问题
        """
        logger.info(
            "intent_request",
            extra={
                "intent": "video-analysis",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "target": slots.device_id,
                "status": "not_implemented",
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

        # 直接抛出错误，不返回占位数据（符合"不做降级"原则）
        raise NotImplementedError(
            f"视频分析功能尚未实现。"
            f"设备：{device.name or device.id}（{device.id}），"
            f"分析目标：{slots.analysis_goal}。"
            f"需要接入以下模块之一：\n"
            f"1. GLM-4V 视觉大模型（推荐）\n"
            f"2. YOLO 目标检测 + 场景分析\n"
            f"3. 其他视频处理管道\n"
            f"请在 src/emergency_agents/video/ 目录实现视频处理模块，"
            f"然后修改此 Handler 调用真实模块。"
        )
