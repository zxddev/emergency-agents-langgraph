from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from emergency_agents.external.adapter_client import (
    AdapterHubClient,
    AdapterHubConfigurationError,
    AdapterHubError,
    build_robotdog_move_command,
)
from emergency_agents.db.dao import DeviceDAO, serialize_dataclass
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import DeviceControlRobotdogSlots, DeviceControlSlots

logger = logging.getLogger(__name__)


@dataclass
class DeviceControlHandler(IntentHandler[DeviceControlSlots]):
    device_dao: DeviceDAO
    adapter_client: AdapterHubClient
    default_robotdog_id: str | None = None

    async def handle(self, slots: DeviceControlSlots, state: dict[str, object]) -> dict[str, object]:
        logger.info(
            "intent_request",
            extra={
                "intent": "device-control",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "target": slots.device_id,
                "action": slots.action,
                "status": "processing",
            },
        )

        device_id = slots.device_id or self.default_robotdog_id
        if not device_id:
            return {
                "response_text": "请提供要控制的设备编号（例如 7）。",
                "device_control": {"status": "missing_device_id"},
            }

        device = await self.device_dao.fetch_device(device_id)
        if device is None:
            return {
                "response_text": "暂未登记该设备，请核对编号。",
                "device_control": {"status": "not_found"},
            }

        vendor = self._infer_vendor(slots.device_type, device.device_type, slots.action_params)
        if vendor != "dqDog":
            logger.info(
                "device_control_unsupported_vendor",
                extra={"device_type": slots.device_type, "inferred_vendor": vendor},
            )
            message = (
                f"设备 {device.name or device.id} ({device.device_type}) 暂未接入自动控制，"
                "已记录请求等待人工处理。"
            )
            return {
                "response_text": message,
                "device_control": {
                    "status": "pending_manual_integration",
                    "device": asdict(device),
                    "action": slots.action,
                    "params": slots.action_params,
                },
            }

        try:
            command = build_robotdog_move_command(device_id, slots.action)
        except ValueError as exc:
            logger.warning("device_control_invalid_action: %s", exc)
            return {
                "response_text": f"暂不支持动作：{slots.action}",
                "device_control": {
                    "status": "invalid_action",
                    "device": serialize_dataclass(device),
                    "action": slots.action,
                    "params": slots.action_params,
                },
            }

        try:
            logger.info(
                "adapter_robotdog_send",
                extra={"device_id": device.id, "action": command["params"]["action"], "intent": "device-control"},
            )
            adapter_response = await self.adapter_client.send_device_command(command)
        except AdapterHubConfigurationError:
            logger.error("adapter hub base url missing，无法下发机器狗指令")
            return {
                "response_text": "未配置设备控制适配器，已记录动作等待人工处理。",
                "device_control": {
                    "status": "adapter_not_configured",
                    "device": serialize_dataclass(device),
                    "command": command,
                    "params": slots.action_params,
                },
            }
        except AdapterHubError as exc:
            logger.error("adapter hub 调用失败: %s", exc, exc_info=True)
            return {
                "response_text": "已尝试发送控制指令，但适配器返回错误，请稍后重试或人工接管。",
                "device_control": {
                    "status": "adapter_error",
                    "device": serialize_dataclass(device),
                    "command": command,
                    "params": slots.action_params,
                },
            }

        message = (
            f"已向鼎桥机器狗 {device.name or device.id} 发送动作：{command['params']['action']}，请关注执行状态。"
        )
        logger.info(
            "adapter_robotdog_dispatched",
            extra={
                "device_id": device.id,
                "action": command["params"]["action"],
                "intent": "device-control",
            },
        )
        return {
            "response_text": message,
            "device_control": {
                "status": "dispatched",
                "device": serialize_dataclass(device),
                "command": command,
                "adapter_response": adapter_response,
            },
        }

    @staticmethod
    def _infer_vendor(
        provided_type: str | None, recorded_type: str | None, action_params: Mapping[str, Any] | None
    ) -> str | None:
        """根据槽位/数据库类型初步推断设备厂商。"""
        candidates = [
            (action_params or {}).get("vendor"),
            provided_type,
            recorded_type,
        ]
        for raw in candidates:
            if not raw:
                continue
            value = str(raw).lower()
            if "dq" in value or "dingqiao" in value:
                return "dqDog"
            if "dog" in value and "dq" not in value:
                # 默认机器狗归一到鼎桥，后续可扩展
                return "dqDog"
        return None


@dataclass
class RobotDogControlHandler(IntentHandler[DeviceControlRobotdogSlots]):
    adapter_client: AdapterHubClient
    default_robotdog_id: str | None = None

    async def handle(self, slots: DeviceControlRobotdogSlots, state: dict[str, object]) -> dict[str, object]:
        logger.info(
            "intent_request",
            extra={
                "intent": "device_control_robotdog",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "action": slots.action,
                "status": "processing",
            },
        )

        device_id = slots.device_id or self.default_robotdog_id
        if not device_id:
            return {
                "response_text": "缺少机器狗设备 ID，请在意图中提供或配置 DEFAULT_ROBOTDOG_ID。",
                "robotdog_control": {"status": "missing_device_id"},
            }

        try:
            command = build_robotdog_move_command(device_id, slots.action)
        except ValueError:
            return {
                "response_text": f"暂不支持动作：{slots.action}",
                "robotdog_control": {"status": "invalid_action", "action": slots.action},
            }

        try:
            logger.info(
                "adapter_robotdog_send",
                extra={"device_id": device_id, "action": command["params"]["action"], "intent": "device_control_robotdog"},
            )
            adapter_response = await self.adapter_client.send_device_command(command)
        except AdapterHubConfigurationError:
            logger.error("adapter hub base url missing，无法下发机器狗指令")
            return {
                "response_text": "未配置设备控制适配器，无法执行机器狗动作。",
                "robotdog_control": {"status": "adapter_not_configured", "command": command},
            }
        except AdapterHubError as exc:
            logger.error("robotdog_adapter_error: %s", exc, exc_info=True)
            return {
                "response_text": "机器狗控制指令发送失败，请稍后重试或联系人工。",
                "robotdog_control": {"status": "adapter_error", "command": command},
            }

        message = (
            f"已让鼎桥机器狗执行动作：{command['params']['action']}，请关注实时回传。"
        )
        logger.info(
            "adapter_robotdog_dispatched",
            extra={
                "device_id": device_id,
                "action": command["params"]["action"],
                "intent": "device_control_robotdog",
            },
        )
        result_payload = {
            "status": "dispatched",
            "device_id": device_id,
            "command": command,
            "adapter_response": adapter_response,
        }
        if slots.distance_m is not None:
            result_payload["distance_m"] = slots.distance_m
        if slots.angle_deg is not None:
            result_payload["angle_deg"] = slots.angle_deg
        if slots.speed is not None:
            result_payload["speed"] = slots.speed
        if slots.lat is not None and slots.lng is not None:
            result_payload["target_coordinates"] = {"lat": slots.lat, "lng": slots.lng}

        return {"response_text": message, "robotdog_control": result_payload}
