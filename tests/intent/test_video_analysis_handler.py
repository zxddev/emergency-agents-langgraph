from __future__ import annotations

from typing import Any, Mapping, cast

import pytest

pytest.importorskip("psycopg")

from emergency_agents.db.models import VideoDevice
from emergency_agents.intent.handlers.video_analysis import VideoAnalysisHandler
from emergency_agents.intent.schemas import VideoAnalysisSlots


class _StubDeviceDAO:
    def __init__(self, mapping: Mapping[str, VideoDevice | None]) -> None:
        self._mapping = dict(mapping)

    async def fetch_video_device(self, device_id: str) -> VideoDevice | None:
        return self._mapping.get(device_id)

    async def fetch_video_device_by_name(self, device_name: str) -> VideoDevice | None:
        """根据设备名称查询（测试stub）"""
        # 简化实现：直接用名称作为key查找
        for device in self._mapping.values():
            if device and device.name == device_name:
                return device
        return None


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要真实视频流和GLM-4V API，跳过集成测试")
async def test_video_analysis_stream_from_db() -> None:
    dao = _StubDeviceDAO(
        {
            "drone-1": VideoDevice(
                id="drone-1",
                device_type="uav",
                name="无人机A",
                stream_url="rtsp://db",
            )
        }
    )
    handler = VideoAnalysisHandler(
        device_dao=cast(Any, dao),
        stream_map=cast(Mapping[str, str], {}),
        vllm_url="http://localhost:8001/v1",  # 测试用 URL
    )
    slots = VideoAnalysisSlots(device_name="无人机A", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    # 真实实现会尝试连接视频流和 GLM-4V，这里跳过测试
    assert result["video_analysis"]["status"] in ["success", "capture_failed", "error"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要真实视频流和GLM-4V API，跳过集成测试")
async def test_video_analysis_missing_stream() -> None:
    dao = _StubDeviceDAO(
        {
            "drone-1": VideoDevice(
                id="drone-1",
                device_type="uav",
                name="无人机A",
                stream_url=None,
            )
        }
    )
    handler = VideoAnalysisHandler(
        device_dao=cast(Any, dao),
        stream_map=cast(Mapping[str, str], {"drone-1": "rtsp://map"}),
        vllm_url="http://localhost:8001/v1",  # 测试用 URL
    )
    slots = VideoAnalysisSlots(device_name="无人机A", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    # 真实实现会尝试连接视频流，这里跳过测试
    assert result["video_analysis"]["status"] in ["success", "capture_failed", "error"]


@pytest.mark.asyncio
async def test_video_analysis_unknown_device() -> None:
    """测试设备不存在的情况 - 不需要真实视频流，可以正常测试"""
    dao = _StubDeviceDAO({"unknown": None})
    handler = VideoAnalysisHandler(
        device_dao=cast(Any, dao),
        stream_map=cast(Mapping[str, str], {}),
        vllm_url="http://localhost:8001/v1",  # 测试用 URL
    )
    slots = VideoAnalysisSlots(device_name="不存在的设备", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["video_analysis"]["status"] == "device_not_found"  # 修复：新实现返回 device_not_found
