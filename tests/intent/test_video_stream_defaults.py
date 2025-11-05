from __future__ import annotations

import pytest

pytest.importorskip("qdrant_client")

from emergency_agents.intent.registry import DEFAULT_VIDEO_STREAMS
from emergency_agents.video.stream_catalog import VideoStreamCatalog


def test_default_robotdog_stream_present() -> None:
    """默认配置包含侦察巡逻机器狗，确保代码内置流生效。"""
    catalog = VideoStreamCatalog.from_raw_mapping(DEFAULT_VIDEO_STREAMS)
    entry = catalog.auto_select()
    assert entry is not None
    assert entry.display_name == "侦察巡逻机器狗"
    assert entry.stream_url.startswith("rtsp://")
