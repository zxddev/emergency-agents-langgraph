# Copyright 2025 msq
"""意图槽位校验与追问生成。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import jsonschema

logger = logging.getLogger(__name__)

PLACEHOLDER_MISSING_FIELDS: set[str] = {
    "未知字段",
    "未知槽位",
    "unknown_field",
    "unknown",
    "missing_field",
}
PLACEHOLDER_LOCATION_MARKERS: tuple[str, ...] = ("XX", "示例", "样例", "测试")
PLACEHOLDER_COORDINATE_PAIRS: tuple[tuple[float, float], ...] = (
    (31.2038, 103.9276),
)


def _extract_missing_fields(validation_error, schema: Dict[str, Any]) -> List[str]:
    """从ValidationError提取缺失字段。
    
    Args:
        validation_error: jsonschema.ValidationError实例。
        schema: JSON Schema字典。
    
    Returns:
        缺失字段名列表。
    """
    missing = []
    if validation_error.validator == "required":
        missing = list(validation_error.validator_value)
    return missing


def _sanitize_missing_fields(fields: List[str]) -> List[str]:
    """过滤占位缺失字段，标准化字段名称。"""
    sanitized: List[str] = []
    for field in fields:
        if not isinstance(field, str):
            continue
        name = field.strip().strip("“”'\" ")
        if not name or name in PLACEHOLDER_MISSING_FIELDS:
            continue
        sanitized.append(name)
    return sanitized


def _has_non_empty_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(value.strip())


def _has_detail_text(value: Any, min_len: int = 15) -> bool:
    if not isinstance(value, str):
        return False
    return len(value.strip()) >= min_len


def _has_coordinates(slots: Dict[str, Any]) -> bool:
    coordinates = slots.get("coordinates")
    if isinstance(coordinates, dict):
        lat = coordinates.get("lat") or coordinates.get("latitude")
        lng = coordinates.get("lng") or coordinates.get("longitude") or coordinates.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            return not _is_placeholder_coordinates(lat, lng)
        return False
    lat = slots.get("lat") or slots.get("latitude")
    lng = slots.get("lng") or slots.get("longitude") or slots.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return not _is_placeholder_coordinates(lat, lng)
    return False


def _has_location(slots: Dict[str, Any]) -> bool:
    location_keys = ("location", "location_name", "location_text", "locationName")
    for key in location_keys:
        value = slots.get(key)
        if _has_non_empty_text(value) and not _is_placeholder_location_text(str(value)):
            return True
    return _has_coordinates(slots)


def _enforce_required_fields(intent_type: Optional[str], slots: Dict[str, Any]) -> List[str]:
    """基于业务规则补充缺失字段列表。"""
    canonical = (intent_type or "").lower()
    missing: List[str] = []

    if canonical in {"rescue_task_generate", "rescue-task-generate"}:
        if not _has_non_empty_text(slots.get("mission_type")):
            missing.append("mission_type")
        if not _has_coordinates(slots):
            missing.append("coordinates")
        if not _has_detail_text(slots.get("situation_summary"), min_len=15):
            missing.append("situation_summary")
        if not _has_location(slots):
            missing.append("location")

    if canonical == "hazard_report":
        if not _has_non_empty_text(slots.get("event_type")):
            missing.append("event_type")
        if not _has_location(slots):
            missing.append("location")

    return missing


def _generate_prompt_for_missing(intent_type: str, missing_fields: List[str], llm_client, llm_model: str) -> str:
    """LLM生成自然语言追问。

    Args:
        intent_type: 意图类型。
        missing_fields: 缺失字段列表。
        llm_client: LLM客户端。
        llm_model: 模型名。
    
    Returns:
        自然语言追问文本。
    """
    prompt = (
        f"用户执行'{intent_type}'操作，但缺少必填参数：{', '.join(missing_fields)}。\n"
        "请生成一句简短的中文追问，帮助用户补充这些信息。只返回追问句子，不要其他内容。"
    )
    
    try:
        rsp = llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return rsp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("LLM生成追问失败: %s，使用模板", e)
        return f"请补充以下信息：{', '.join(missing_fields)}"


def validate_and_prompt_node(state: Dict[str, Any], llm_client, llm_model: str) -> Dict[str, Any]:
    """验证intent槽位并在缺失时生成追问。
    
    Args:
        state: 图状态，必含state.intent。
        llm_client: LLM客户端。
        llm_model: 模型名。
    
    Returns:
        更新后的state，包含validation_status字段。
    """
    intent = state.get("intent") or {}
    intent_type = intent.get("intent_type")
    slots = intent.get("slots") or {}

    from emergency_agents.intent.schemas import INTENT_SCHEMAS
    from emergency_agents.intent.slot_normalizer import normalize_slots

    cleaned_slots = normalize_slots(intent_type, slots)
    intent = intent | {"slots": cleaned_slots}
    slots = cleaned_slots

    schema = INTENT_SCHEMAS.get(intent_type)
    if not schema:
        logger.info("intent_type=%s 无schema定义，跳过验证", intent_type)
        return state | {"validation_status": "valid"}

    skip_validation_intents = {"device_control_robotdog", "device-control"}
    if intent_type in skip_validation_intents:
        logger.info("intent_type=%s 跳过槽位验证（基础控制）", intent_type)
        return state | {"intent": intent, "validation_status": "valid"}

    extra_missing = _enforce_required_fields(intent_type, slots)
    sanitized_extra = _sanitize_missing_fields(extra_missing)

    try:
        jsonschema.validate(slots, schema)
        logger.info("intent_type=%s 槽位验证通过", intent_type)
        if sanitized_extra:
            prompt = _generate_prompt_for_missing(intent_type, sanitized_extra, llm_client, llm_model)
            logger.info(
                "intent_type=%s 业务必填缺失=%s，生成追问（schema通过）",
                intent_type,
                sanitized_extra,
            )
            return state | {
                "validation_status": "invalid",
                "prompt": prompt,
                "missing_fields": sanitized_extra,
                "validation_attempt": int(state.get("validation_attempt", 0)) + 1,
            }
        return state | {"validation_status": "valid"}
    except jsonschema.ValidationError as e:
        missing = _sanitize_missing_fields(_extract_missing_fields(e, schema))
        extra_from_rules = _sanitize_missing_fields(extra_missing)
        combined_missing = sorted({*missing, *extra_from_rules})

        if not combined_missing:
            logger.warning("jsonschema验证失败但未提取到缺失字段: %s", e.message)
            combined_missing = ["未知字段"]

        attempt = int(state.get("validation_attempt", 0)) + 1

        if attempt > 3:
            logger.warning("validation_attempt=%d 超过阈值，标记失败", attempt)
            return state | {
                "validation_status": "failed",
                "validation_attempt": attempt,
                "last_error": {"validator": "max_attempts_exceeded", "missing": combined_missing}
            }

        prompt = _generate_prompt_for_missing(intent_type, combined_missing, llm_client, llm_model)

        logger.info(
            "intent_type=%s 缺失字段%s，生成追问（尝试%d/3）",
            intent_type,
            combined_missing,
            attempt,
        )

        return state | {
            "validation_status": "invalid",
            "prompt": prompt,
            "missing_fields": combined_missing,
            "validation_attempt": attempt
        }


def _is_placeholder_location_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return any(marker in stripped for marker in PLACEHOLDER_LOCATION_MARKERS)


def _is_placeholder_coordinates(lat: float, lng: float) -> bool:
    pair = (round(lat, 4), round(lng, 4))
    return pair in {(round(item[0], 4), round(item[1], 4)) for item in PLACEHOLDER_COORDINATE_PAIRS}
