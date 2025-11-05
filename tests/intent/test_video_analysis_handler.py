from __future__ import annotations

import pytest
pytest.importorskip("qdrant_client")

from emergency_agents.intent.handlers.video_analysis import VideoAnalysisHandler
from emergency_agents.intent.schemas import VideoAnalysisSlots
from emergency_agents.video.stream_catalog import VideoStreamCatalog


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要真实视频流和GLM-4V API，跳过集成测试")
async def test_video_analysis_stream_from_db() -> None:
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": {
                "display_name": "巡逻机器狗Alpha",
                "stream_url": "rtsp://db",
                "aliases": ["机器狗Alpha"],
                "device_type": "robotdog",
            }
        }
    )
    handler = VideoAnalysisHandler(
        stream_catalog=catalog,
        vllm_url="http://localhost:8001/v1",
        vllm_api_key=None,
        vllm_model="glm-4.5-v",
    )
    slots = VideoAnalysisSlots(
        device_name="巡逻机器狗Alpha",
        device_type="robotdog",
        analysis_goal="damage_assessment",
    )
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    # 真实实现会尝试连接视频流和 GLM-4V，这里跳过测试
    assert result["video_analysis"]["status"] in ["success", "capture_failed", "error"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="需要真实视频流和GLM-4V API，跳过集成测试")
async def test_video_analysis_missing_stream() -> None:
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": {
                "display_name": "巡逻机器狗Alpha",
                "stream_url": "",
                "aliases": ["机器狗Alpha"],
                "device_type": "robotdog",
            }
        }
    )
    handler = VideoAnalysisHandler(
        stream_catalog=catalog,
        vllm_url="http://localhost:8001/v1",
        vllm_api_key=None,
        vllm_model="glm-4.5-v",
    )
    slots = VideoAnalysisSlots(
        device_name="巡逻机器狗Alpha",
        device_type="robotdog",
        analysis_goal="damage_assessment",
    )
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    # 真实实现会尝试连接视频流，这里跳过测试
    assert result["video_analysis"]["status"] in ["success", "capture_failed", "error"]


@pytest.mark.asyncio
async def test_video_analysis_unknown_device() -> None:
    """测试设备不存在的情况 - 不需要真实视频流，可以正常测试"""
    catalog = VideoStreamCatalog.from_raw_mapping({})
    handler = VideoAnalysisHandler(
        stream_catalog=catalog,
        vllm_url="http://localhost:8001/v1",
        vllm_api_key=None,
        vllm_model="glm-4.5-v",
    )
    slots = VideoAnalysisSlots(device_name="不存在的设备", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["video_analysis"]["status"] == "device_not_found"  # 修复：新实现返回 device_not_found


@pytest.mark.asyncio
async def test_video_analysis_ambiguous_device() -> None:
    """名称命中多台设备时应提示澄清"""
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": {
                "display_name": "巡逻机器狗Alpha",
                "stream_url": "rtsp://alpha",
                "aliases": ["巡逻机器狗"],
                "device_type": "robotdog",
            },
            "dog-beta": {
                "display_name": "巡逻机器狗Beta",
                "stream_url": "rtsp://beta",
                "aliases": ["巡逻机器狗"],
                "device_type": "robotdog",
            },
        }
    )
    handler = VideoAnalysisHandler(
        stream_catalog=catalog,
        vllm_url="http://localhost:8001/v1",
        vllm_api_key=None,
        vllm_model="glm-4.5-v",
    )
    slots = VideoAnalysisSlots(device_name="巡逻机器狗", device_type="robotdog", analysis_goal="status")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["video_analysis"]["status"] == "ambiguous_device_name"
    assert len(result["video_analysis"]["candidates"]) == 2
