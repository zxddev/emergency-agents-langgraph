"""语音控制 REST 接口。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from emergency_agents.control import ControlIntent, DeviceCommand, DeviceType, VoiceControlState


router = APIRouter(prefix="/voice/control", tags=["voice-control"])


class VoiceControlRequest(BaseModel):
    """语音控制命令请求体。"""

    command_text: str = Field(..., description="自然语言指令文本")
    device_id: Optional[str] = Field(None, description="目标设备 ID")
    device_type: Optional[DeviceType] = Field(None, description="设备类型枚举")
    auto_confirm: bool = Field(True, description="是否跳过人工确认")


class VoiceControlIntentModel(BaseModel):
    """返回时展示的意图结构。"""

    device_type: DeviceType
    device_id: str
    action: str
    confirmation_prompt: str
    auto_confirm: bool
    device_name: Optional[str] = None
    device_vendor: Optional[str] = None


class VoiceControlCommandModel(BaseModel):
    """返回时展示的命令结构。"""

    device_id: str
    device_vendor: str
    control_target: str
    command_type: str
    params: Dict[str, Any]


class VoiceControlResponse(BaseModel):
    """语音控制响应。"""

    request_id: str
    status: str
    intent: Optional[VoiceControlIntentModel] = None
    command: Optional[VoiceControlCommandModel] = None
    adapter_result: Optional[Dict[str, Any]] = None
    audit_trail: List[Dict[str, Any]]
    error_detail: Optional[str] = None


def _require_voice_control_graph(request: Request) -> Any:
    graph = getattr(request.app.state, "voice_control_graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="voice control graph unavailable")
    return graph


def _serialize_intent(intent: Optional[ControlIntent]) -> Optional[VoiceControlIntentModel]:
    if intent is None:
        return None
    return VoiceControlIntentModel(
        device_type=intent.device_type,
        device_id=intent.device_id,
        action=intent.action,
        confirmation_prompt=intent.confirmation_prompt,
        auto_confirm=intent.auto_confirm,
        device_name=intent.device_name,
        device_vendor=intent.device_vendor,
    )


def _serialize_command(command: Optional[DeviceCommand]) -> Optional[VoiceControlCommandModel]:
    if command is None:
        return None
    return VoiceControlCommandModel(
        device_id=command.device_id,
        device_vendor=command.device_vendor,
        control_target=command.control_target,
        command_type=command.command_type,
        params=command.params,
    )


@router.post("/commands", response_model=VoiceControlResponse)
def create_voice_control_command(request: Request, payload: VoiceControlRequest) -> VoiceControlResponse:
    """通过 REST 触发语音控制指令。"""

    graph = _require_voice_control_graph(request)
    init_state: VoiceControlState = {
        "raw_text": payload.command_text,
        "auto_confirm": payload.auto_confirm,
    }
    if payload.device_id:
        init_state["device_id"] = payload.device_id
    if payload.device_type is not None:
        init_state["device_type"] = payload.device_type.value

    result: VoiceControlState = graph.invoke(
        init_state,
        config={"durability": "exit"},  # 短流程（语音控制），使用默认高性能模式
    )

    response = VoiceControlResponse(
        request_id=result.get("request_id", ""),
        status=result.get("status", "unknown"),
        intent=_serialize_intent(result.get("normalized_intent")),
        command=_serialize_command(result.get("device_command")),
        adapter_result=result.get("adapter_result"),
        audit_trail=list(result.get("audit_trail") or []),
        error_detail=result.get("error_detail"),
    )
    return response
