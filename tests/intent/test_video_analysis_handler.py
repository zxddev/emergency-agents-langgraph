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


@pytest.mark.asyncio
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
    handler = VideoAnalysisHandler(device_dao=cast(Any, dao), stream_map=cast(Mapping[str, str], {}))
    slots = VideoAnalysisSlots(device_id="drone-1", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["video_analysis"]["status"] == "pending_pipeline"
    assert result["video_analysis"]["device"]["stream_url"] == "rtsp://db"


@pytest.mark.asyncio
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
    )
    slots = VideoAnalysisSlots(device_id="drone-1", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["video_analysis"]["device"]["stream_url"] == "rtsp://map"


@pytest.mark.asyncio
async def test_video_analysis_unknown_device() -> None:
    dao = _StubDeviceDAO({"unknown": None})
    handler = VideoAnalysisHandler(device_dao=cast(Any, dao), stream_map=cast(Mapping[str, str], {}))
    slots = VideoAnalysisSlots(device_id="unknown", device_type="uav", analysis_goal="damage_assessment")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["video_analysis"]["status"] == "not_found"
