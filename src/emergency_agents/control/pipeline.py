"""语音控制流水线，实现指令解析与命令构造所需的前置归一化。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

import structlog

from .models import ControlIntent, DeviceType

if TYPE_CHECKING:
    from emergency_agents.external.device_directory import DeviceDirectory, DeviceEntry
else:
    DeviceDirectory = Any
    DeviceEntry = Any


_logger = structlog.get_logger(__name__)


class VoiceControlError(RuntimeError):
    """语音指令解析异常。"""


_DEVICE_KEYWORDS: Dict[DeviceType, tuple[str, ...]] = {
    DeviceType.ROBOTDOG: ("机器狗", "狗", "robotdog", "鼎桥"),
    DeviceType.UAV: ("无人机", "drone", "飞行", "起飞"),
    DeviceType.UGV: ("无人车", "机器人", "robot"),
    DeviceType.USV: ("无人船", "舰艇", "船艇", "boat"),
}

_ACTION_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "forward": ("前进", "向前", "前走", "forward"),
    "back": ("后退", "向后", "back", "倒退"),
    "turnLeft": ("左转", "向左", "左拐", "turn left"),
    "turnRight": ("右转", "向右", "右拐", "turn right"),
    "up": ("起立", "站立", "站起", "站起来", "抬起", "上升", "stand up"),
    "down": ("趴下", "坐下", "下降", "蹲下", "sit down"),
    "stop": ("停止", "停下", "stop"),
    "forceStop": ("急停", "紧急停止", "force stop", "forceStop"),
}


def _normalize_device_type(value: str) -> DeviceType:
    for device in DeviceType:
        if device.value == value:
            return device
    lowered = value.strip().lower()
    for device in DeviceType:
        if lowered == device.value:
            return device
    raise VoiceControlError(f"未知设备类型: {value}")


@dataclass
class VoiceControlPipeline:
    """语音控制解析流水线。"""

    default_robotdog_id: str | None = None
    device_directory: DeviceDirectory | None = None

    def parse(
        self,
        *,
        command_text: str,
        device_id: str | None,
        device_type: str | None,
        auto_confirm: bool,
    ) -> ControlIntent:
        """根据自然语言指令生成控制意图。"""

        if not command_text or not command_text.strip():
            raise VoiceControlError("缺少指令文本")

        normalized_type = self._detect_device_type(command_text, device_type)

        entry: Optional[DeviceEntry] = None
        if not device_id and self.device_directory is not None:
            entry = self.device_directory.match(command_text, normalized_type)
            if entry is None:
                raise VoiceControlError("未找到匹配的设备名称，请确认设备列表")

        resolved_device_id = self._resolve_device_id(normalized_type, device_id, entry)
        device_name = entry.name if entry is not None else None
        device_vendor = entry.vendor if entry is not None and entry.vendor else None
        action = self._detect_action(command_text)

        confirmation_prompt = f"将控制{normalized_type.value}执行动作：{action}"
        _logger.info(
            "voice_control_normalized",
            device_type=normalized_type.value,
            device_id=resolved_device_id,
            action=action,
            auto_confirm=auto_confirm,
        )

        return ControlIntent(
            device_type=normalized_type,
            device_id=resolved_device_id,
            action=action,
            raw_text=command_text,
            auto_confirm=auto_confirm,
            params={"action": action},
            confirmation_prompt=confirmation_prompt,
            device_name=device_name,
            device_vendor=device_vendor,
        )

    def _detect_device_type(self, command_text: str, device_type: str | None) -> DeviceType:
        if device_type:
            return _normalize_device_type(device_type)

        lowered = command_text.strip().lower()
        for device, keywords in _DEVICE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in lowered:
                    return device
        raise VoiceControlError("无法识别设备类型，请补充设备信息")

    def _resolve_device_id(
        self,
        device_type: DeviceType,
        device_id: str | None,
        entry: Optional[DeviceEntry],
    ) -> str:
        if device_id and device_id.strip():
            return device_id.strip()
        if entry is not None:
            return entry.device_id
        if self.device_directory is not None:
            raise VoiceControlError("未匹配到设备 ID，请确认设备名称是否正确")
        if device_type is DeviceType.ROBOTDOG and self.default_robotdog_id:
            return self.default_robotdog_id
        raise VoiceControlError("缺少设备 ID")

    def _detect_action(self, command_text: str) -> str:
        lowered = command_text.lower().replace("_", " ")
        for action, keywords in _ACTION_KEYWORDS.items():
            for keyword in keywords:
                pattern = keyword.lower()
                if pattern in lowered:
                    return action
        words = re.split(r"\s+", command_text)
        if len(words) == 1 and words[0]:
            return self._fallback_normalize(words[0])
        raise VoiceControlError("无法识别动作指令")

    def _fallback_normalize(self, token: str) -> str:
        key = token.strip().lower()
        for action, keywords in _ACTION_KEYWORDS.items():
            if key in (kw.lower() for kw in keywords):
                return action
        raise VoiceControlError(f"不支持的动作: {token}")
