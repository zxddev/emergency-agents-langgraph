from __future__ import annotations

import re
from typing import Any, Dict, Tuple

# 占位地点关键词，用于识别模型复述的模板地址
PLACEHOLDER_LOCATION_MARKERS: Tuple[str, ...] = ("XX", "示例", "样例", "测试")
# 占位经纬度（来自提示示例），匹配时应视为未填写
PLACEHOLDER_COORDINATE_PAIRS: Tuple[Tuple[float, float], ...] = (
    (31.2038, 103.9276),
)
# 任务类型别名映射，统一转为可读中文描述
RESCUE_MISSION_ALIASES: Dict[str, str] = {
    "rescue": "前突救援",
    "forward_rescue": "前突救援",
    "forward-rescue": "前突救援",
    "处置": "前突救援",
    "前突": "前突救援",
}


def normalize_slots(intent_type: str | None, slots: Dict[str, Any]) -> Dict[str, Any]:
    """根据意图类型规范化槽位字段，移除schema外字段。"""
    if not intent_type or not isinstance(slots, dict):
        return {}

    if intent_type in {"rescue_task_generate", "rescue-task-generate"}:
        return _normalize_rescue_task_slots(slots)

    if intent_type in {"rescue_simulation", "rescue-simulation"}:
        normalized = _normalize_rescue_task_slots(slots)
        normalized.setdefault("simulation_only", True)
        return normalized

    if intent_type == "hazard_report":
        return _normalize_hazard_slots(slots)

    if intent_type == "device_control_robotdog":
        return _normalize_robotdog_slots(slots)

    if intent_type == "device-control":
        return _normalize_device_control_slots(slots)

    return {k: v for k, v in slots.items() if v is not None}


def _normalize_rescue_task_slots(slots: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    mission_type = _first_non_empty(
        slots,
        ["mission_type", "missionType", "task_type", "taskType", "type"],
    )
    if mission_type:
        mission_text = str(mission_type).strip()
        mapped = RESCUE_MISSION_ALIASES.get(mission_text.lower(), mission_text)
        result["mission_type"] = mapped

    location_name = _first_non_empty(
        slots,
        ["location_name", "locationName", "location_text", "location"],
    )
    if location_name:
        candidate = str(location_name).strip()
        if not _is_placeholder_location(candidate):
            result["location_name"] = candidate

    coordinates = _extract_coordinates(slots)
    if coordinates:
        result["coordinates"] = coordinates

    disaster_type = _first_non_empty(
        slots,
        ["disaster_type", "disasterType", "disaster"],
    )
    if disaster_type:
        result["disaster_type"] = str(disaster_type).strip()

    summary = _first_non_empty(
        slots,
        ["situation_summary", "situationSummary", "summary", "description", "detail"]
    )
    if summary:
        result["situation_summary"] = str(summary).strip()

    impact_scope = _first_non_empty(slots, ["impact_scope", "scope"])
    if impact_scope is not None:
        try:
            result["impact_scope"] = int(impact_scope)
        except (TypeError, ValueError):
            pass

    simulation_only = _first_non_empty(slots, ["simulation_only", "simulationOnly"])
    if simulation_only is not None:
        result["simulation_only"] = bool(simulation_only)

    task_id = _first_non_empty(slots, ["task_id", "taskId"])
    if task_id:
        result["task_id"] = str(task_id)

    return result


def _normalize_hazard_slots(slots: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    event_type = _first_non_empty(
        slots,
        ["event_type", "eventType", "type"],
    )
    if event_type:
        result["event_type"] = str(event_type).strip()

    location_text = _first_non_empty(
        slots,
        ["location_text", "location", "location_name", "locationName"],
    )
    if location_text:
        candidate = str(location_text).strip()
        if not _is_placeholder_location(candidate):
            result["location_text"] = candidate

    coordinates = _extract_coordinates(slots)
    if coordinates:
        result["coordinates"] = coordinates

    severity = _first_non_empty(slots, ["severity", "level"])
    if severity:
        result["severity"] = str(severity).strip()

    description = _first_non_empty(
        slots, ["description", "detail", "summary"]
    )
    if description:
        result["description"] = str(description).strip()

    parent_event = _first_non_empty(
        slots, ["parent_event_id", "parentEventId"]
    )
    if parent_event:
        result["parent_event_id"] = str(parent_event).strip()

    time_reported = _first_non_empty(
        slots, ["time_reported", "timeReported", "reported_time"]
    )
    if time_reported:
        result["time_reported"] = str(time_reported).strip()

    return result


def _normalize_robotdog_slots(slots: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    action = slots.get("action") or slots.get("动作") or slots.get("command")
    if isinstance(action, str) and action.strip():
        result["action"] = action.strip()

    device_aliases = ["device_id", "device", "id", "设备", "robot_id"]
    for key in device_aliases:
        value = slots.get(key)
        if value:
            parsed = _extract_device_id(value)
            if parsed:
                result["device_id"] = parsed
                break

    return result


def _normalize_device_control_slots(slots: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    action = slots.get("action") or slots.get("command")
    if isinstance(action, str) and action.strip():
        result["action"] = action.strip()

    device_id = slots.get("device_id") or slots.get("device") or slots.get("id")
    if device_id:
        parsed = _extract_device_id(device_id)
        if parsed:
            result["device_id"] = parsed

    device_type = slots.get("device_type") or slots.get("type")
    if isinstance(device_type, str) and device_type.strip():
        result["device_type"] = device_type.strip()

    params = slots.get("action_params") or {}
    if isinstance(params, dict) and params:
        result["action_params"] = params

    return result


def _extract_device_id(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return str(int(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        import re

        match = re.search(r"\d+", stripped)
        if match:
            return match.group(0)
        return stripped
    return None


def _extract_coordinates(slots: Dict[str, Any]) -> Dict[str, float] | None:
    lat_values = [
        slots.get("lat"),
        slots.get("latitude"),
        slots.get("Latitude"),
    ]
    lng_values = [
        slots.get("lng"),
        slots.get("lon"),
        slots.get("long"),
        slots.get("longitude"),
        slots.get("Longitude"),
    ]

    lat = _first_numeric(lat_values)
    lng = _first_numeric(lng_values)
    if lat is not None and lng is not None:
        if not _is_placeholder_coordinates(lat, lng):
            return {"lat": lat, "lng": lng}
        return None

    coords = slots.get("coordinates")
    if isinstance(coords, dict):
        lat = _first_numeric(
            [coords.get("lat"), coords.get("latitude"), coords.get("Lat")]
        )
        lng = _first_numeric(
            [coords.get("lng"), coords.get("lon"), coords.get("longitude"), coords.get("Lng")]
        )
        if lat is not None and lng is not None:
            if not _is_placeholder_coordinates(lat, lng):
                return {"lat": lat, "lng": lng}
            return None

    if isinstance(coords, str):
        match = re.findall(r"-?\d+(?:\.\d+)?", coords)
        if len(match) >= 2:
            lng_str, lat_str = match[0], match[1]
            lng_val = _to_float(lng_str)
            lat_val = _to_float(lat_str)
            if lat_val is not None and lng_val is not None:
                if not _is_placeholder_coordinates(lat_val, lng_val):
                    return {"lat": lat_val, "lng": lng_val}
                return None

    return None


def _first_non_empty(slots: Dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = slots.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _first_numeric(values: list[Any]) -> float | None:
    for value in values:
        num = _to_float(value)
        if num is not None:
            return num
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_placeholder_location(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    return any(marker in text for marker in PLACEHOLDER_LOCATION_MARKERS)


def _is_placeholder_coordinates(lat: float, lng: float) -> bool:
    pair = (round(lat, 4), round(lng, 4))
    return pair in {(round(lat_ref, 4), round(lng_ref, 4)) for lat_ref, lng_ref in PLACEHOLDER_COORDINATE_PAIRS}
