"""语音控制 LangGraph 子图构建。"""

from __future__ import annotations

import uuid
from typing import Any, Dict

import structlog
from langgraph.graph import StateGraph
from langgraph.types import interrupt

from emergency_agents.control import (
    AdapterDispatchResult,
    ControlIntent,
    DeviceCommand,
    DeviceType,
    VoiceControlPipeline,
    VoiceControlState,
    VoiceControlError,
)
from emergency_agents.external.adapter_client import (
    AdapterHubClient,
    AdapterHubConfigurationError,
    AdapterHubError,
    AdapterHubRequestError,
    AdapterHubResponseError,
    build_robotdog_move_command,
)
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer


_logger = structlog.get_logger(__name__)


async def build_voice_control_graph(
    *,
    pipeline: VoiceControlPipeline,
    adapter_client: AdapterHubClient,
    postgres_dsn: str,
    checkpoint_schema: str = "voice_control_checkpoint",
) -> Any:
    """构建语音控制子图并绑定异步持久化。"""

    _logger.info("voice_control_graph_init", schema=checkpoint_schema)

    graph = StateGraph(VoiceControlState)

    def _append_audit(state: VoiceControlState, event: Dict[str, Any]) -> list[Dict[str, Any]]:
        trail = list(state.get("audit_trail") or [])
        trail.append(event)
        return trail

    def _ingest(state: VoiceControlState) -> Dict[str, Any]:
        raw_text = state.get("raw_text") or ""
        if not raw_text.strip():
            raise VoiceControlError("缺少控制指令文本")
        request_id = state.get("request_id") or str(uuid.uuid4())
        trail = _append_audit(state, {"event": "voice_control_ingest", "request_id": request_id, "text": raw_text})
        auto_confirm = bool(state.get("auto_confirm", True))
        return {
            "request_id": request_id,
            "status": "init",
            "audit_trail": trail,
            "auto_confirm": auto_confirm,
        }

    def _normalize(state: VoiceControlState) -> Dict[str, Any]:
        raw_text = state.get("raw_text") or ""
        intent = pipeline.parse(
            command_text=raw_text,
            device_id=state.get("device_id"),
            device_type=state.get("device_type"),
            auto_confirm=bool(state.get("auto_confirm", True)),
        )
        trail = _append_audit(
            state,
            {
                "event": "voice_control_normalized",
                "device_type": intent.device_type.value,
                "device_id": intent.device_id,
                "action": intent.action,
            },
        )
        return {
            "normalized_intent": intent,
            "audit_trail": trail,
        }

    def _confirm(state: VoiceControlState) -> Dict[str, Any]:
        intent: ControlIntent = state["normalized_intent"]
        trail = list(state.get("audit_trail") or [])
        if intent.auto_confirm:
            trail.append(
                {
                    "event": "voice_control_auto_confirm",
                    "device_id": intent.device_id,
                    "device_name": intent.device_name,
                    "action": intent.action,
                }
            )
            return {"status": "validated", "audit_trail": trail, "confirmation": True}

        decision = interrupt(
            {
                "request_id": state.get("request_id"),
                "prompt": intent.confirmation_prompt,
                "intent": {
                    "device_type": intent.device_type.value,
                    "device_id": intent.device_id,
                    "action": intent.action,
                },
            }
        )

        confirmed = False
        if isinstance(decision, dict):
            confirmed = bool(decision.get("confirm"))
        elif isinstance(decision, bool):
            confirmed = decision

        if not confirmed:
            trail.append(
                {
                    "event": "voice_control_rejected",
                    "device_id": intent.device_id,
                    "device_name": intent.device_name,
                    "action": intent.action,
                }
            )
            return {
                "status": "error",
                "error_detail": "操作未确认",
                "audit_trail": trail,
                "confirmation": False,
            }

        trail.append(
            {
                "event": "voice_control_confirmed",
                "device_id": intent.device_id,
                "device_name": intent.device_name,
                "action": intent.action,
            }
        )
        return {"status": "validated", "audit_trail": trail, "confirmation": True}

    def _build_command(state: VoiceControlState) -> Dict[str, Any]:
        # 非确认状态无需构造命令，直接透传状态供后续节点终止
        if state.get("status") != "validated":
            _logger.info("voice_control_skip_build", status=state.get("status"))
            return {}

        intent: ControlIntent = state["normalized_intent"]
        commands_payload: list[dict[str, Any]] = []

        if intent.device_type is DeviceType.ROBOTDOG:
            # 急停需要先停再急停，确保硬件完全制动
            if intent.action == "forceStop":
                commands_payload.append(
                    build_robotdog_move_command(intent.device_id, "stop")
                )
                commands_payload.append(
                    build_robotdog_move_command(intent.device_id, "forceStop")
                )
            else:
                commands_payload.append(
                    build_robotdog_move_command(intent.device_id, intent.action)
                )
        else:
            raise VoiceControlError(f"暂不支持的设备类型: {intent.device_type.value}")

        commands: list[DeviceCommand] = [
            DeviceCommand(
                device_id=payload["deviceId"],
                device_vendor=payload["deviceVendor"],
                control_target=payload["controlTarget"],
                command_type=payload["commandType"],
                params=payload["params"],
            )
            for payload in commands_payload
        ]

        actions = [command.params.get("action") for command in commands]
        trail = _append_audit(
            state,
            {
                "event": "voice_control_command_built",
                "device_id": commands[-1].device_id,
                "device_vendor": commands[-1].device_vendor,
                "command_type": commands[-1].command_type,
                "actions": actions,
            },
        )
        return {
            "device_command": commands[-1],
            "device_commands": commands,
            "audit_trail": trail,
        }

    async def _dispatch(state: VoiceControlState) -> Dict[str, Any]:
        # 未通过确认的流程直接跳过派发，确保不会误触设备
        if state.get("status") != "validated":
            _logger.info("voice_control_skip_dispatch", status=state.get("status"))
            return {"status": state.get("status", "error"), "audit_trail": list(state.get("audit_trail") or [])}

        commands: list[DeviceCommand] = list(state.get("device_commands") or [])
        if not commands and state.get("device_command") is not None:
            commands = [state["device_command"]]

        if not commands:
            _logger.error("voice_control_no_command", state=state)
            raise VoiceControlError("缺少待派发的设备命令")

        trail = list(state.get("audit_trail") or [])
        dispatch_steps: list[dict[str, Any]] = []

        for index, command in enumerate(commands, start=1):
            payload = {
                "deviceId": command.device_id,
                "deviceVendor": command.device_vendor,
                "controlTarget": command.control_target,
                "commandType": command.command_type,
                "params": command.params,
            }
            step_record: dict[str, Any] = {
                "step": index,
                "action": command.params.get("action"),
                "payload": payload,
            }
            _logger.info(
                "voice_control_dispatch_attempt",
                step=index,
                device_id=command.device_id,
                vendor=command.device_vendor,
                command_type=command.command_type,
                action=command.params.get("action"),
            )
            try:
                response = await adapter_client.send_device_command(payload)
            except (AdapterHubConfigurationError, AdapterHubRequestError, AdapterHubResponseError) as exc:
                _logger.error(
                    "voice_control_dispatch_failed",
                    error=str(exc),
                    device_id=command.device_id,
                    step=index,
                )
                step_record["error"] = str(exc)
                dispatch_steps.append(step_record)
                trail.append(
                    {
                        "event": "voice_control_dispatch_failed",
                        "device_id": command.device_id,
                        "step": index,
                        "reason": str(exc),
                    }
                )
                failure: AdapterDispatchResult = {
                    "status": "failed",
                    "error": "机器狗设备不在线，请联系工程师调试",
                    "steps": dispatch_steps,
                }
                return {
                    "status": "error",
                    "error_detail": "机器狗设备不在线，请联系工程师调试",
                    "adapter_result": failure,
                    "audit_trail": trail,
                }
            except AdapterHubError as exc:
                _logger.error(
                    "voice_control_dispatch_unknown",
                    error=str(exc),
                    device_id=command.device_id,
                    step=index,
                )
                step_record["error"] = str(exc)
                dispatch_steps.append(step_record)
                trail.append(
                    {
                        "event": "voice_control_dispatch_failed",
                        "device_id": command.device_id,
                        "step": index,
                        "reason": str(exc),
                    }
                )
                failure = {
                    "status": "failed",
                    "error": "机器狗设备不在线，请联系工程师调试",
                    "steps": dispatch_steps,
                }
                return {
                    "status": "error",
                    "error_detail": "机器狗设备不在线，请联系工程师调试",
                    "adapter_result": failure,
                    "audit_trail": trail,
                }

            response_payload = dict(response)
            step_record["response"] = response_payload
            dispatch_steps.append(step_record)
            trail.append(
                {
                    "event": "voice_control_dispatched",
                    "device_id": command.device_id,
                    "step": index,
                    "response": response_payload,
                }
            )

        final_command = commands[-1]
        _logger.info(
            "voice_control_dispatched",
            device_id=final_command.device_id,
            vendor=final_command.device_vendor,
            command_type=final_command.command_type,
            actions=[cmd.params.get("action") for cmd in commands],
        )
        success: AdapterDispatchResult = {
            "status": "success",
            "payload": dispatch_steps[-1]["response"],
            "steps": dispatch_steps,
        }
        return {
            "status": "dispatched",
            "adapter_result": success,
            "audit_trail": trail,
        }

    def _finalize(state: VoiceControlState) -> Dict[str, Any]:
        return {}

    graph.add_node("ingest", _ingest)
    graph.add_node("normalize", _normalize)
    graph.add_node("confirm", _confirm)
    graph.add_node("build_command", _build_command)
    graph.add_node("dispatch", _dispatch)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "normalize")
    graph.add_edge("normalize", "confirm")
    graph.add_edge("confirm", "build_command")
    graph.add_edge("build_command", "dispatch")
    graph.add_edge("dispatch", "finalize")

    checkpointer, close_cb = await create_async_postgres_checkpointer(
        dsn=postgres_dsn,
        schema=checkpoint_schema,
        min_size=1,
        max_size=1,
    )
    compiled = graph.compile(checkpointer=checkpointer)
    setattr(compiled, "_checkpoint_close", close_cb)
    _logger.info("voice_control_graph_ready", schema=checkpoint_schema)
    return compiled
