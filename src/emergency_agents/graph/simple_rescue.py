# Copyright 2025 msq
from __future__ import annotations

import logging
from typing import Any, Dict, List
from emergency_agents.container import container
from emergency_agents.db.dao import RescueDAO

logger = logging.getLogger(__name__)

async def simple_rescue_logic(
    slots: Dict[str, Any],
    thread_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    简易救援逻辑 (Refactored from SimpleRescueGraph)
    
    执行: 分析槽位 -> 查询装备 -> 生成响应
    """
    # 1. Analyze Slots
    coords = slots.get("coordinates") or {}
    summary = slots.get("situation_summary") or ""
    location = slots.get("location_name") or ""
    mission_type = slots.get("mission_type") or ""

    missing: List[str] = []
    if not isinstance(coords, dict) or "lng" not in coords or "lat" not in coords:
        missing.append("coordinates")
    if not isinstance(summary, str) or len(summary.strip()) < 15:
        missing.append("situation_summary")
    if not isinstance(location, str) or not location.strip():
        missing.append("location_name")
    if not isinstance(mission_type, str) or not mission_type.strip():
        missing.append("mission_type")

    logger.info(f"Slots analyzed: {missing}", extra={"thread_id": thread_id})

    # 2. Fetch Equipment
    # 即使缺失部分信息，只要不是关键信息全无，也尝试查询
    equipment_list = []
    rescue_dao = RescueDAO.create(container.db_pool)
    
    try:
        resources = await rescue_dao.list_available_rescuers(limit=10)
        for record in resources:
            equipment_list.append({
                "rescuer_id": record.rescuer_id,
                "name": record.name,
                "type": record.rescuer_type,
                "status": record.status,
                "equipment": list((record.equipment or {}).keys()),
                "skills": list(record.skills or []),
                "lng": record.lng,
                "lat": record.lat,
            })
    except Exception as e:
        logger.error(f"Failed to fetch equipment: {e}")
        missing.append("rescue_resources_error")

    if not equipment_list:
        missing.append("rescue_resources_empty")

    # 3. Prepare Response
    lines: List[str] = []
    if equipment_list:
        lines.append("当前可调度救援力量：")
        for item in equipment_list[:5]:
            lines.append(f"- {item['name']}（{item['type']}），装备：{', '.join(item['equipment']) or '未登记'}")
    else:
        lines.append("当前数据库未返回可用救援力量，请尽快补录或调配支援单位。")

    if missing:
        lines.append("待补信息：" + ", ".join(sorted(missing)))

    return {
        "response_text": "\n".join(lines),
        "status": "success" if equipment_list else "pending",
        "missing_fields": missing,
        "equipment": equipment_list
    }
