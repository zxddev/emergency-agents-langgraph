# Copyright 2025 msq
"""报告接收智能体：处理被困报告与灾情报告。

职责：
- 解析trapped_report/hazard_report槽位
- 创建PENDING实体/事件（当前阶段记录到state，待Java API集成）
- 写入timeline事件
- 准备两阶段提交
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Any

from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.merge import append_timeline

logger = logging.getLogger(__name__)


def report_intake_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """报告接收智能体。
    
    Args:
        state: 图状态，必含state.intent（intent_type为trapped_report或hazard_report）。
    
    Returns:
        更新后的state，包含pending_entities或pending_events。
    """
    intent = state.get("intent") or {}
    intent_type = intent.get("intent_type")
    slots = intent.get("slots") or {}
    
    if intent_type == "trapped_report":
        return _handle_trapped_report(state, slots)
    elif intent_type == "hazard_report":
        return _handle_hazard_report(state, slots)
    else:
        logger.warning("report_intake_agent收到非预期intent_type: %s", intent_type)
        return state


def _handle_trapped_report(state: Dict[str, Any], slots: Dict[str, Any]) -> Dict[str, Any]:
    """处理被困报告。
    
    Args:
        state: 图状态。
        slots: 槽位（count必填，lat/lng或location_text）。
    
    Returns:
        更新后的state，包含pending_entities。
    """
    count = int(slots.get("count", 0))
    lat = slots.get("lat")
    lng = slots.get("lng")
    location_text = slots.get("location_text")
    description = slots.get("description") or f"{count}人被困"
    time_reported = slots.get("time_reported")
    
    if count <= 0:
        logger.error("trapped_report count无效: %s", count)
        return state | {"last_error": {"agent": "report_intake", "error": "invalid_count"}}
    
    entity_id = str(uuid.uuid4())
    
    entity = {
        "id": entity_id,
        "type": "TRAPPED",
        "count": count,
        "lat": lat,
        "lng": lng,
        "location_text": location_text,
        "description": description,
        "time_reported": time_reported,
        "status": "PENDING",
        "geometry": {
            "type": "Point",
            "coordinates": [lng, lat] if lng and lat else None
        }
    }
    
    pending_entities = (state.get("pending_entities") or []) + [entity]
    
    logger.info("创建PENDING被困实体: id=%s, count=%d, location=%s", entity_id, count, location_text or f"({lat},{lng})")
    
    state = append_timeline(state, "trapped_report_created", {"entity_id": entity_id, "count": count})
    
    from emergency_agents.audit.logger import log_ai_decision
    log_ai_decision(
        rescue_id=state.get("rescue_id", "unknown"),
        user_id=state.get("user_id", "unknown"),
        agent_name="report_intake_agent",
        decision_type="trapped_report",
        decision_data={"entity_id": entity_id, "count": count, "lat": lat, "lng": lng}
    )
    
    content = f"被困报告：{count}人，位置{location_text or f'({lat},{lng})'}"
    state = prepare_memory_node(state, content=content, metadata={"agent": "report_intake", "entity_id": entity_id})
    
    integration_logs = (state.get("integration_logs") or []) + [
        {"target": "java.entities", "message": "READY TO CALL JAVA API", "method": "POST /entities", "payload": entity}
    ]
    
    return state | {"pending_entities": pending_entities, "integration_logs": integration_logs}


def _handle_hazard_report(state: Dict[str, Any], slots: Dict[str, Any]) -> Dict[str, Any]:
    """处理灾情报告。
    
    Args:
        state: 图状态。
        slots: 槽位（event_type必填）。
    
    Returns:
        更新后的state，包含pending_events。
    """
    event_type = slots.get("event_type")
    title = slots.get("title") or f"{event_type}事件"
    lat = slots.get("lat")
    lng = slots.get("lng")
    location_text = slots.get("location_text")
    severity = slots.get("severity") or "MED"
    description = slots.get("description") or ""
    parent_event_id = slots.get("parent_event_id")
    
    if not event_type:
        logger.error("hazard_report event_type缺失")
        return state | {"last_error": {"agent": "report_intake", "error": "missing_event_type"}}
    
    event_id = str(uuid.uuid4())
    
    event = {
        "id": event_id,
        "event_type": event_type,
        "title": title,
        "lat": lat,
        "lng": lng,
        "location_text": location_text,
        "severity": severity,
        "description": description,
        "parent_event_id": parent_event_id,
        "status": "active",
        "geometry": {
            "type": "Point",
            "coordinates": [lng, lat] if lng and lat else None
        }
    }
    
    pending_events = (state.get("pending_events") or []) + [event]
    
    logger.info("创建事件: id=%s, type=%s, severity=%s, location=%s", event_id, event_type, severity, location_text or f"({lat},{lng})")
    
    state = append_timeline(state, "hazard_report_created", {"event_id": event_id, "event_type": event_type, "severity": severity})
    
    from emergency_agents.audit.logger import log_ai_decision
    log_ai_decision(
        rescue_id=state.get("rescue_id", "unknown"),
        user_id=state.get("user_id", "unknown"),
        agent_name="report_intake_agent",
        decision_type="hazard_report",
        decision_data={"event_id": event_id, "event_type": event_type, "severity": severity}
    )
    
    content = f"{event_type}事件：{title}，严重度{severity}，位置{location_text or f'({lat},{lng})'}"
    state = prepare_memory_node(state, content=content, metadata={"agent": "report_intake", "event_id": event_id})
    
    integration_logs = (state.get("integration_logs") or []) + [
        {"target": "java.events", "message": "READY TO CALL JAVA API", "method": "POST /events", "payload": event}
    ]
    
    return state | {"pending_events": pending_events, "integration_logs": integration_logs}

