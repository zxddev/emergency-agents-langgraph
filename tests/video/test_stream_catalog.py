from __future__ import annotations

from emergency_agents.video.stream_catalog import VideoStreamCatalog


def test_auto_select_single_entry() -> None:
    """目录只有一个设备时应直接命中。"""
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": {
                "display_name": "巡逻机器狗Alpha",
                "stream_url": "rtsp://alpha",
                "device_type": "robotdog",
            }
        }
    )
    entry = catalog.auto_select()
    assert entry is not None
    assert entry.device_id == "dog-alpha"


def test_auto_select_by_device_type() -> None:
    """按设备类型筛选唯一设备应成功返回。"""
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": {
                "display_name": "巡逻机器狗Alpha",
                "stream_url": "rtsp://alpha",
                "device_type": "robotdog",
            },
            "uav-beta": {
                "display_name": "侦察无人机Beta",
                "stream_url": "rtsp://beta",
                "device_type": "uav",
            },
        }
    )
    entry = catalog.auto_select(device_type="robotdog")
    assert entry is not None
    assert entry.display_name == "巡逻机器狗Alpha"


def test_auto_select_multiple_none() -> None:
    """存在多台同类设备时不应自动选择。"""
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": {
                "display_name": "巡逻机器狗Alpha",
                "stream_url": "rtsp://alpha",
                "device_type": "robotdog",
            },
            "dog-beta": {
                "display_name": "巡逻机器狗Beta",
                "stream_url": "rtsp://beta",
                "device_type": "robotdog",
            },
        }
    )
    entry = catalog.auto_select(device_type="robotdog")
    assert entry is None


def test_resolve_token_duplicates_removed() -> None:
    """相同名称不会导致重复匹配。"""
    catalog = VideoStreamCatalog.from_raw_mapping(
        {
            "dog-alpha": "rtsp://alpha",
        }
    )
    candidates = catalog.resolve("dog-alpha")
    assert len(candidates) == 1
