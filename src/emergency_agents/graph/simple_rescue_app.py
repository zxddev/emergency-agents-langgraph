"""简化救援子图：用于实时语音交互快速响应。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from typing_extensions import NotRequired, Required, TypedDict

from langgraph.graph import StateGraph

from emergency_agents.db.dao import RescueDAO

logger = structlog.get_logger(__name__)


class SimpleRescueState(TypedDict, total=False):
    thread_id: Required[str]
    user_id: Required[str]
    slots: Required[Dict[str, Any]]

    missing_fields: NotRequired[List[str]]
    equipment: NotRequired[List[Dict[str, Any]]]
    response_text: NotRequired[str]
    status: NotRequired[str]


async def build_simple_rescue_graph(*, rescue_dao: RescueDAO) -> Any:
    """构建简化救援子图。"""

    graph = StateGraph(SimpleRescueState)

    def analyze_slots(state: SimpleRescueState) -> Dict[str, Any]:
        slots = state.get("slots") or {}
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

        logger.info(
            "simple_rescue_slots_analyzed",
            thread_id=state.get("thread_id"),
            missing=missing,
        )
        return {"missing_fields": missing}

    async def fetch_equipment(state: SimpleRescueState) -> Dict[str, Any]:
        missing = state.get("missing_fields") or []
        if missing and set(missing) != {"mission_type"}:
            # 关键信息缺失时不继续查询资源
            return {}

        try:
            resources = await rescue_dao.list_available_rescuers(limit=10)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "simple_rescue_equipment_query_failed",
                thread_id=state.get("thread_id"),
                error=str(exc),
            )
            return {
                "status": "error",
                "missing_fields": sorted(set(missing + ["rescue_resources"])),
            }

        equipment_list: List[Dict[str, Any]] = []
        for record in resources:
            equipment_list.append(
                {
                    "rescuer_id": record.rescuer_id,
                    "name": record.name,
                    "type": record.rescuer_type,
                    "status": record.status,
                    "equipment": list((record.equipment or {}).keys()),
                    "skills": list(record.skills or []),
                    "lng": record.lng,
                    "lat": record.lat,
                }
            )

        if not equipment_list:
            missing = sorted(set(missing + ["rescue_resources"]))

        logger.info(
            "simple_rescue_equipment_collected",
            thread_id=state.get("thread_id"),
            count=len(equipment_list),
        )
        return {
            "equipment": equipment_list,
            "missing_fields": missing,
        }

    def prepare_response(state: SimpleRescueState) -> Dict[str, Any]:
        missing = state.get("missing_fields") or []
        equipment = state.get("equipment") or []

        lines: List[str] = []
        if equipment:
            head = "当前可调度救援力量："
            lines.append(head)
            for item in equipment[:5]:
                lines.append(
                    f"- {item['name']}（{item['type']}），装备：{', '.join(item['equipment']) or '未登记'}"
                )
        else:
            lines.append("当前数据库未返回可用救援力量，请尽快补录或调配支援单位。")

        if missing:
            lines.append(
                "待补信息：" + ", ".join(sorted(missing))
            )

        logger.info(
            "simple_rescue_java_call_todo",
            thread_id=state.get("thread_id"),
            note="TODO 调用 Java 调度接口，当前仅记录日志",
        )

        response_text = "\n".join(lines)
        return {
            "response_text": response_text,
            "status": "success" if equipment else "pending",
        }

    graph.add_node("analyze_slots", analyze_slots)
    graph.add_node("fetch_equipment", fetch_equipment)
    graph.add_node("prepare_response", prepare_response)

    graph.set_entry_point("analyze_slots")
    graph.add_edge("analyze_slots", "fetch_equipment")
    graph.add_edge("fetch_equipment", "prepare_response")
    graph.add_edge("prepare_response", "__end__")

    compiled = graph.compile()
    logger.info("simple_rescue_graph_ready")
    return compiled


__all__ = ["build_simple_rescue_graph", "SimpleRescueState"]

