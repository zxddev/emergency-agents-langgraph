# Copyright 2025 msq
"""标注生命周期智能体：处理地图标注创建与签收。

职责：
- 处理geo_annotate创建PENDING标注
- 处理annotation_sign签收/驳回标注（PENDING → SIGNED/REJECTED）
- 记录timeline事件
- 准备Java API调用（当前TODO）
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Any

from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.merge import append_timeline

logger = logging.getLogger(__name__)


def annotation_lifecycle_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """标注生命周期智能体。
    
    Args:
        state: 图状态，必含state.intent（geo_annotate或annotation_sign）。
    
    Returns:
        更新后的state，包含pending_annotations或已更新的annotations列表。
    """
    intent = state.get("intent") or {}
    intent_type = intent.get("intent_type")
    slots = intent.get("slots") or {}
    
    if intent_type == "geo_annotate":
        return _handle_geo_annotate(state, slots)
    elif intent_type == "annotation_sign":
        return _handle_annotation_sign(state, slots)
    else:
        logger.warning("annotation_lifecycle_agent收到非预期intent_type: %s", intent_type)
        return state


def _handle_geo_annotate(state: Dict[str, Any], slots: Dict[str, Any]) -> Dict[str, Any]:
    """处理地图标注创建。
    
    Args:
        state: 图状态。
        slots: 槽位（label/geometry_type必填）。
    
    Returns:
        更新后的state，包含pending_annotations。
    """
    label = slots.get("label")
    geometry_type = slots.get("geometry_type")
    lat = slots.get("lat")
    lng = slots.get("lng")
    coordinates = slots.get("coordinates")
    confidence = slots.get("confidence")
    description = slots.get("description") or ""
    
    if not label or not geometry_type:
        logger.error("geo_annotate缺少必填字段: label=%s, geometry_type=%s", label, geometry_type)
        return state | {"last_error": {"agent": "annotation_lifecycle", "error": "missing_required_fields"}}
    
    annotation_id = str(uuid.uuid4())
    
    geometry = None
    if geometry_type == "Point" and lat and lng:
        geometry = {"type": "Point", "coordinates": [lng, lat]}
    elif geometry_type in ("LineString", "Polygon") and coordinates:
        geometry = {"type": geometry_type, "coordinates": coordinates}
    
    annotation = {
        "id": annotation_id,
        "label": label,
        "geometry": geometry,
        "geometry_type": geometry_type,
        "status": "PENDING",
        "confidence": confidence,
        "description": description,
        "evidence": [],
        "created_at": None
    }
    
    pending_annotations = (state.get("pending_annotations") or []) + [annotation]
    
    logger.info("创建PENDING标注: id=%s, label=%s, type=%s", annotation_id, label, geometry_type)
    
    state = append_timeline(state, "geo_annotate_created", {"annotation_id": annotation_id, "label": label})
    
    from emergency_agents.audit.logger import log_ai_decision
    log_ai_decision(
        rescue_id=state.get("rescue_id", "unknown"),
        user_id=state.get("user_id", "unknown"),
        agent_name="annotation_lifecycle_agent",
        decision_type="geo_annotate",
        decision_data={"annotation_id": annotation_id, "label": label, "geometry_type": geometry_type}
    )
    
    content = f"地图标注：{label}（{geometry_type}）"
    state = prepare_memory_node(state, content=content, metadata={"agent": "annotation_lifecycle", "annotation_id": annotation_id})
    
    integration_logs = (state.get("integration_logs") or []) + [
        {"target": "java.annotations", "message": "READY TO CALL JAVA API", "method": "POST /annotations", "payload": annotation}
    ]
    
    return state | {"pending_annotations": pending_annotations, "integration_logs": integration_logs}


def _handle_annotation_sign(state: Dict[str, Any], slots: Dict[str, Any]) -> Dict[str, Any]:
    """处理标注签收/驳回。
    
    Args:
        state: 图状态。
        slots: 槽位（annotation_id/decision必填）。
    
    Returns:
        更新后的state，更新annotations状态。
    """
    annotation_id = slots.get("annotation_id")
    decision = (slots.get("decision") or "").strip().upper()
    
    if not annotation_id or decision not in ("SIGNED", "REJECTED", "APPROVE", "REJECT"):
        logger.error("annotation_sign参数无效: id=%s, decision=%s", annotation_id, decision)
        return state | {"last_error": {"agent": "annotation_lifecycle", "error": "invalid_params"}}
    
    if decision in ("APPROVE", "SIGNED"):
        new_status = "SIGNED"
    else:
        new_status = "REJECTED"
    
    pending_annotations = state.get("pending_annotations") or []
    annotations = state.get("annotations") or []
    
    found = False
    updated_pending = []
    
    for ann in pending_annotations:
        if ann.get("id") == annotation_id:
            ann["status"] = new_status
            annotations.append(ann)
            found = True
            logger.info("标注%s: id=%s, label=%s", new_status, annotation_id, ann.get("label"))
        else:
            updated_pending.append(ann)
    
    if not found:
        for ann in annotations:
            if ann.get("id") == annotation_id:
                ann["status"] = new_status
                found = True
                logger.info("更新已有标注状态: id=%s → %s", annotation_id, new_status)
                break
    
    if not found:
        logger.warning("annotation_id未找到: %s", annotation_id)
        return state | {"last_error": {"agent": "annotation_lifecycle", "error": "annotation_not_found"}}
    
    state = append_timeline(state, f"annotation_{new_status.lower()}", {"annotation_id": annotation_id})
    
    from emergency_agents.audit.logger import log_ai_decision
    log_ai_decision(
        rescue_id=state.get("rescue_id", "unknown"),
        user_id=state.get("user_id", "unknown"),
        agent_name="annotation_lifecycle_agent",
        decision_type="annotation_sign",
        decision_data={"annotation_id": annotation_id, "decision": new_status}
    )
    
    integration_logs = (state.get("integration_logs") or []) + [
        {"target": "java.annotations", "message": "READY TO CALL JAVA API", "method": f"POST /annotations/{annotation_id}/sign", "payload": {"decision": new_status}}
    ]
    
    return state | {
        "pending_annotations": updated_pending,
        "annotations": annotations,
        "integration_logs": integration_logs
    }

