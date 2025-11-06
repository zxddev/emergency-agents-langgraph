from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import structlog

from emergency_agents.db.dao import DeviceDAO
from emergency_agents.db.models import CarriedDevice, DeviceSummary
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import DeviceStatusQuerySlots


logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class DeviceStatusQueryHandler(IntentHandler[DeviceStatusQuerySlots]):
    """设备状态查询Handler。

    支持两种查询模式：
    1. device_name 为空：查询所有车载携带设备（is_selected=1）及其天气能力
    2. device_name 有值：根据设备名称查询指定设备的基础信息
    """

    device_dao: DeviceDAO

    async def handle(self, slots: DeviceStatusQuerySlots, state: Dict[str, object]) -> Dict[str, object]:
        device_name = (slots.device_name or "").strip()

        # 模式1: 未指定设备名称，查询所有车载携带设备
        if not device_name:
            logger.info("device_status_query_all_carried", thread_id=state.get("thread_id"))
            carried_devices: list[CarriedDevice] = await self.device_dao.fetch_carried_devices()

            if not carried_devices:
                logger.info("device_status_no_carried_devices", thread_id=state.get("thread_id"))
                return {
                    "response_text": "当前没有车载携带的设备。",
                    "carried_devices": [],
                }

            # 格式化输出所有携带设备及其天气能力描述
            device_lines: list[str] = []
            for idx, device in enumerate(carried_devices, start=1):
                name = device.name or "未命名设备"
                capability = device.weather_capability or "无天气能力说明"
                device_lines.append(f"{idx}. {name}：{capability}")

            response_text = f"车载携带设备清单（共{len(carried_devices)}台）：\n" + "\n".join(device_lines)

            logger.info(
                "device_status_carried_devices_listed",
                device_count=len(carried_devices),
                thread_id=state.get("thread_id"),
            )

            return {
                "response_text": response_text,
                "carried_devices": [
                    {"name": d.name, "weather_capability": d.weather_capability}
                    for d in carried_devices
                ],
            }

        # 模式2: 指定设备名称，按名称查询单个设备的基础信息
        device: DeviceSummary | None = await self.device_dao.fetch_device_by_name(device_name)
        if device is None:
            logger.info(
                "device_status_not_found_by_name",
                device_name=device_name,
                thread_id=state.get("thread_id"),
            )
            return {
                "response_text": f"未找到名称为 {device_name} 的设备，请核对后重试。",
                "device_status": None,
            }

        logger.info(
            "device_status_resolved_by_name",
            device_id=device.id,
            device_name=device.name,
            device_type=device.device_type,
            thread_id=state.get("thread_id"),
        )

        summary = {
            "id": device.id,
            "name": device.name,
            "device_type": device.device_type,
            "metric": slots.metric,
        }
        response_text = (
            "设备 {name}（编号 {id}）记录在案，当前版本仅返回基础信息，实时状态查询功能建设中。".format(
                name=device.name or "未命名", id=device.id
            )
        )

        return {
            "response_text": response_text,
            "device_status": summary,
        }
