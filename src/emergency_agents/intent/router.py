# Copyright 2025 msq
from __future__ import annotations

import logging
from typing import Any, Dict
from langgraph.types import interrupt

from emergency_agents.geo.track import build_track_feature

logger = logging.getLogger(__name__)


def intent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """根据intent执行路由与专用快速处理（UAV轨迹、机器人狗确认）。"""
    intent = state.get("intent") or {}
    intent_type = (intent.get("intent_type") or "").strip()
    slots = intent.get("slots") or {}

    next_key = "analysis"
    updates: Dict[str, Any] = {}

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
            logs = (state.get("integration_logs") or []) + [
                {"target": "java.robotdog", "message": "READY TO CALL JAVA API", "intent": intent}
            ]
            timeline = (state.get("timeline") or []) + [{"event": "robotdog_control_confirmed", "action": action}]
            updates.update({"integration_logs": logs, "timeline": timeline})
        else:
            timeline = (state.get("timeline") or []) + [{"event": "robotdog_control_rejected", "action": action}]
            updates.update({"timeline": timeline})
        next_key = "done"

    return updates | {"router_next": next_key}


def route_from_router(state: Dict[str, Any]) -> str:
    key = state.get("router_next", "analysis")
    if key not in ("analysis", "done"):
        return "analysis"
    return key


