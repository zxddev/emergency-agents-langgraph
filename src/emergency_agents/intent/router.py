# Copyright 2025 msq
from __future__ import annotations

import logging
from typing import Any, Dict
from langgraph.types import interrupt

from emergency_agents.external.adapter_client import (
    AdapterHubClient,
    AdapterHubConfigurationError,
    AdapterHubError,
    build_robotdog_move_command,
)
from emergency_agents.geo.track import build_track_feature

logger = logging.getLogger(__name__)

_robotdog_client: AdapterHubClient | None = None
_default_robotdog_id: str | None = None


def configure_robotdog_adapter(client: AdapterHubClient | None, default_device_id: str | None) -> None:
    global _robotdog_client, _default_robotdog_id
    _robotdog_client = client
    _default_robotdog_id = default_device_id


async def robotdog_control_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """机器狗控制执行节点：将router阶段确认的命令真正发送至适配器。"""
    command = state.get("robotdog_command")
    if not isinstance(command, dict):
        logger.warning("robotdog_control_node invoked without command")
        return {}

    if _robotdog_client is None:
        logger.error("robotdog_control_node adapter client not configured")
        timeline = (state.get("timeline") or []) + [
            {"event": "robotdog_control_failed", "reason": "adapter_not_configured"}
        ]
        logs = (state.get("integration_logs") or []) + [
            {"target": "adapter.robotdog", "message": "COMMAND_FAILED", "reason": "adapter_not_configured"}
        ]
        return {
            "timeline": timeline,
            "integration_logs": logs,
            "robotdog_command": None,
            "last_error": {"robotdog": "adapter_not_configured"},
        }

    try:
        response = await _robotdog_client.send_device_command(command)
    except AdapterHubConfigurationError:
        logger.error("adapter hub base url missing，无法下发机器狗指令")
        timeline = (state.get("timeline") or []) + [
            {"event": "robotdog_control_failed", "reason": "adapter_not_configured"}
        ]
        logs = (state.get("integration_logs") or []) + [
            {"target": "adapter.robotdog", "message": "COMMAND_FAILED", "reason": "adapter_not_configured"}
        ]
        return {
            "timeline": timeline,
            "integration_logs": logs,
            "robotdog_command": None,
            "last_error": {"robotdog": "adapter_not_configured"},
        }
    except AdapterHubError as exc:
        logger.error("robotdog_control_node adapter error: %s", exc, exc_info=True)
        timeline = (state.get("timeline") or []) + [
            {"event": "robotdog_control_failed", "reason": "adapter_error"}
        ]
        logs = (state.get("integration_logs") or []) + [
            {
                "target": "adapter.robotdog",
                "message": "COMMAND_FAILED",
                "reason": "adapter_error",
                "detail": str(exc),
            }
        ]
        return {
            "timeline": timeline,
            "integration_logs": logs,
            "robotdog_command": None,
            "last_error": {"robotdog": "adapter_error", "detail": str(exc)},
        }

    timeline = (state.get("timeline") or []) + [
        {"event": "robotdog_control_dispatched", "action": command.get("params", {}).get("action")}
    ]
    logs = (state.get("integration_logs") or []) + [
        {
            "target": "adapter.robotdog",
            "message": "COMMAND_DISPATCHED",
            "command": command,
            "response": response,
        }
    ]
    return {
        "timeline": timeline,
        "integration_logs": logs,
        "robotdog_command": None,
        "robotdog_result": {"status": "dispatched", "response": response},
    }


def intent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """根据intent执行路由与专用快速处理（UAV轨迹、机器人狗确认、报告接收）。"""
    intent = state.get("intent") or {}
    intent_type = (intent.get("intent_type") or "").strip()
    slots = intent.get("slots") or {}

    next_key = "analysis"
    updates: Dict[str, Any] = {}
    
    if intent_type in ("trapped_report", "hazard_report"):
        next_key = "report_intake"
        return updates | {"router_next": next_key}
    
    if intent_type in ("geo_annotate", "annotation_sign"):
        next_key = "annotation_lifecycle"
        return updates | {"router_next": next_key}

    if intent_type == "recon_minimal":
        fleet = state.get("fleet_position") or {"lng": 103.80, "lat": 31.66}
        try:
            target_lng = float(slots.get("lng"))
            target_lat = float(slots.get("lat"))
            alt_m = int(slots.get("alt_m", 80))
            steps = int(slots.get("steps", 20))
            
            track = build_track_feature(fleet, target_lng, target_lat, alt_m, steps)
            tracks = (state.get("uav_tracks") or []) + [track]
            timeline = (state.get("timeline") or []) + [
                {"event": "uav_track_generated", "track_id": len(tracks), "alt_m": alt_m, "steps": steps}
            ]
            updates.update({"uav_tracks": tracks, "timeline": timeline})
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("recon_minimal坐标解析失败，需validator补齐: %s", e)
        next_key = "done"

    elif intent_type == "device_control_robotdog":
        action = (slots.get("action") or "").strip()
        decision = interrupt({
            "readback": f"将执行机器狗动作: {action or 'unknown'}. 请确认。",
            "intent": intent,
        })
        confirmed = False
        if isinstance(decision, dict):
            confirmed = bool(decision.get("confirm"))
        elif isinstance(decision, bool):
            confirmed = decision
        if confirmed:
            device_id = slots.get("device_id") or _default_robotdog_id
            if not device_id:
                logger.error("robotdog_control_missing_device_id")
                timeline = (state.get("timeline") or []) + [
                    {"event": "robotdog_control_failed", "reason": "missing_device_id"}
                ]
                updates.update({"timeline": timeline, "last_error": {"robotdog": "missing_device_id"}})
            else:
                try:
                    command = build_robotdog_move_command(str(device_id), action)
                except ValueError as exc:
                    logger.error("robotdog_control_invalid_action: %s", exc)
                    timeline = (state.get("timeline") or []) + [
                        {"event": "robotdog_control_failed", "reason": "invalid_action", "action": action}
                    ]
                    updates.update({"timeline": timeline, "last_error": {"robotdog": "invalid_action"}})
                else:
                    timeline = (state.get("timeline") or []) + [
                        {"event": "robotdog_control_confirmed", "action": command["params"]["action"]}
                    ]
                    logs = (state.get("integration_logs") or []) + [
                        {
                            "target": "adapter.robotdog",
                            "message": "COMMAND_DISPATCH_PENDING",
                            "command": command,
                        }
                    ]
                    updates.update(
                        {
                            "timeline": timeline,
                            "integration_logs": logs,
                            "robotdog_command": command,
                        }
                    )
                    return updates | {"router_next": "robotdog_control"}
        else:
            timeline = (state.get("timeline") or []) + [{"event": "robotdog_control_rejected", "action": action}]
            updates.update({"timeline": timeline})
        next_key = "done"

    elif intent_type == "conversation_control":
        command = (slots.get("command") or "").strip().lower()
        timeline = (state.get("timeline") or []) + [{"event": f"conversation_{command}"}]
        
        if command == "cancel":
            logger.info("用户取消当前操作")
            updates.update({
                "status": "cancelled",
                "timeline": timeline,
                "validation_attempt": 0,
                "validation_status": "valid"
            })
            next_key = "done"
        elif command == "retry":
            logger.info("用户重新开始")
            updates.update({
                "validation_attempt": 0,
                "validation_status": "valid",
                "timeline": timeline,
                "intent": {}
            })
            next_key = "analysis"
        elif command == "help":
            help_text = (
                "可用指令：侦察/标注/查询路线/控制设备/报告灾情等。"
                "示例：'到31.68,103.85侦察' / '机器狗前进5米' / '标注该点为被困群众'。"
            )
            updates.update({
                "timeline": timeline,
                "help_response": help_text
            })
            next_key = "done"
        elif command == "back":
            logger.info("用户返回上一步")
            attempt = max(0, int(state.get("validation_attempt", 1)) - 1)
            updates.update({
                "validation_attempt": attempt,
                "timeline": timeline
            })
            next_key = "done"
        else:
            logger.warning("未识别的conversation_control命令: %s", command)
            next_key = "done"

    return updates | {"router_next": next_key}


def route_from_router(state: Dict[str, Any]) -> str:
    key = state.get("router_next", "analysis")
    if key not in ("analysis", "done", "report_intake", "annotation_lifecycle", "robotdog_control"):
        return "analysis"
    return key
