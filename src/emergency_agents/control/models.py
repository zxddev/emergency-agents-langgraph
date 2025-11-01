"""语音控制相关的数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Literal, Optional, TypedDict


class DeviceType(str, Enum):
    """设备类型枚举，覆盖语音控制支持的硬件分类。"""

    ROBOTDOG = "robotdog"
    UAV = "uav"
    UGV = "ugv"
    USV = "usv"


@dataclass(frozen=True)
class ControlIntent:
    """解析后的控制意图。"""

    device_type: DeviceType
    device_id: str
    action: str
    raw_text: str
    auto_confirm: bool
    params: Dict[str, Any]
    confirmation_prompt: str
    device_name: Optional[str]
    device_vendor: Optional[str]


@dataclass(frozen=True)
class DeviceCommand:
    """发送到 Adapter Hub 的统一命令结构。"""

    device_id: str
    device_vendor: str
    command_type: str
    params: Dict[str, Any]


class AdapterDispatchResult(TypedDict, total=False):
    """适配层回执。"""

    status: Literal["success", "failed"]
    payload: Dict[str, Any]
    error: str


class VoiceControlState(TypedDict, total=False):
    """LangGraph 语音控制子图的状态容器。"""

    request_id: str
    raw_text: str
    device_id: str
    device_type: str
    auto_confirm: bool
    confirmation: bool
    normalized_intent: ControlIntent
    device_command: DeviceCommand
    adapter_result: AdapterDispatchResult
    status: Literal["init", "validated", "dispatched", "error"]
    error_detail: str
    audit_trail: list[Dict[str, Any]]
