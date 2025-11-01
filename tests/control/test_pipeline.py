from __future__ import annotations

import pytest

from emergency_agents.control import DeviceType, VoiceControlError, VoiceControlPipeline
from emergency_agents.external.device_directory import DeviceEntry


class _StubDirectory:
    def __init__(self, entry: DeviceEntry | None) -> None:
        self._entry = entry

    def match(self, command_text: str, device_type: DeviceType) -> DeviceEntry | None:
        return self._entry


def test_pipeline_parses_robotdog_forward() -> None:
    entry = DeviceEntry(device_id="dog-001", name="先锋机器狗", device_type=DeviceType.ROBOTDOG, vendor="dqDog")
    pipeline = VoiceControlPipeline(default_robotdog_id=None, device_directory=_StubDirectory(entry))
    intent = pipeline.parse(
        command_text="请让先锋机器狗前进",
        device_id=None,
        device_type=None,
        auto_confirm=True,
    )
    assert intent.device_type is DeviceType.ROBOTDOG
    assert intent.device_id == "dog-001"
    assert intent.action == "forward"
    assert intent.params == {"action": "forward"}
    assert intent.device_name == "先锋机器狗"


def test_pipeline_requires_device_id_without_default() -> None:
    pipeline = VoiceControlPipeline(default_robotdog_id=None, device_directory=_StubDirectory(None))
    with pytest.raises(VoiceControlError):
        pipeline.parse(
            command_text="机器狗左转",
            device_id=None,
            device_type=None,
            auto_confirm=True,
        )


def test_pipeline_uses_explicit_device_type() -> None:
    pipeline = VoiceControlPipeline(default_robotdog_id="dog-001", device_directory=_StubDirectory(None))
    intent = pipeline.parse(
        command_text="请前进",
        device_id="dog-123",
        device_type=DeviceType.ROBOTDOG.value,
        auto_confirm=False,
    )
    assert intent.device_id == "dog-123"
    assert intent.auto_confirm is False


def test_pipeline_error_when_device_name_missing() -> None:
    pipeline = VoiceControlPipeline(default_robotdog_id=None, device_directory=_StubDirectory(None))
    with pytest.raises(VoiceControlError):
        pipeline.parse(
            command_text="先锋机器狗停止",
            device_id=None,
            device_type=None,
            auto_confirm=True,
        )
