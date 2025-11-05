from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import structlog

from emergency_agents.db.dao import DeviceDAO
from emergency_agents.db.models import DeviceSummary
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import DeviceStatusQuerySlots


logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class DeviceStatusQueryHandler(IntentHandler[DeviceStatusQuerySlots]):
    """设备状态查询占位实现。

    当前仅返回设备的基础信息，后续可扩展为实时状态查询。
    """

    device_dao: DeviceDAO

    async def handle(self, slots: DeviceStatusQuerySlots, state: Dict[str, object]) -> Dict[str, object]:
        device_id = (slots.device_id or "").strip()
        if not device_id:
            logger.info("device_status_missing_device_id", thread_id=state.get("thread_id"))
            return {
                "response_text": "请提供设备编号，方便查询当前状态。",
                "device_status": None,
            }

        device: DeviceSummary | None = await self.device_dao.fetch_device(device_id)
        if device is None:
            logger.info("device_status_not_found", device_id=device_id, thread_id=state.get("thread_id"))
            return {
                "response_text": f"未找到编号为 {device_id} 的设备，请核对后重试。",
                "device_status": None,
            }

        logger.info(
            "device_status_resolved",
            device_id=device.id,
            device_type=device.device_type,
            thread_id=state.get("thread_id"),
        )

        summary = {
            "id": device.id,
            "name": device.name,
            "device_type": device.device_type,
            "metric": slots.metric,
        }
        response_text = ("设备 {name}（编号 {id}）记录在案，当前版本仅返回基础信息，实时状态查询功能建设中。"
                         .format(name=device.name or "未命名", id=device.id))

        return {
            "response_text": response_text,
            "device_status": summary,
        }
