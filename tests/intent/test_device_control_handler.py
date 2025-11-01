from __future__ import annotations

from typing import Any, Mapping, Optional

import pytest

pytest.importorskip("psycopg")

from emergency_agents.external.adapter_client import AdapterHubError
from emergency_agents.intent.handlers.device_control import (
    DeviceControlHandler,
)
from emergency_agents.intent.schemas import DeviceControlSlots
from emergency_agents.db.models import DeviceSummary


class _FakeAdapterClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.last_command: dict[str, Any] | None = None

    async def send_device_command(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        self.last_command = dict(command)
        if self.should_fail:
            raise AdapterHubError("adapter error")
        return {"code": 0, "msg": "ok"}


class _FakeDeviceDAO:
    def __init__(self, record: Optional[DeviceSummary]) -> None:
        self._record = record

    async def fetch_device(self, device_id: str) -> DeviceSummary | None:
        return self._record if self._record and self._record.id == device_id else None

    async def fetch_video_device(self, device_id: str) -> DeviceSummary | None:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_device_control_known_device() -> None:
    dao = _FakeDeviceDAO(DeviceSummary(id="dog-1", device_type="robot_dog", name="机器狗A"))
    adapter = _FakeAdapterClient()
    handler = DeviceControlHandler(device_dao=dao, adapter_client=adapter)
    slots = DeviceControlSlots(device_type="robot_dog", device_id="dog-1", action="forward")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["device_control"]["status"] == "dispatched"
    assert adapter.last_command is not None
    assert adapter.last_command["params"]["action"] == "forward"


@pytest.mark.asyncio
async def test_device_control_unknown_device() -> None:
    dao = _FakeDeviceDAO(None)
    adapter = _FakeAdapterClient()
    handler = DeviceControlHandler(device_dao=dao, adapter_client=adapter)
    slots = DeviceControlSlots(device_type="robot_dog", device_id="unknown", action="forward")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["device_control"]["status"] == "not_found"
    assert adapter.last_command is None


@pytest.mark.asyncio
async def test_device_control_invalid_action() -> None:
    dao = _FakeDeviceDAO(DeviceSummary(id="dog-1", device_type="robot_dog", name="机器狗A"))
    adapter = _FakeAdapterClient()
    handler = DeviceControlHandler(device_dao=dao, adapter_client=adapter)
    slots = DeviceControlSlots(device_type="robot_dog", device_id="dog-1", action="moonwalk")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["device_control"]["status"] == "invalid_action"
    assert adapter.last_command is None
