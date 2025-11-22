# Copyright 2025 msq
"""意图槽位校验与追问生成。"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import jsonschema
import structlog

logger = structlog.get_logger(__name__)


_DEFAULT_ROBOTDOG_ID: str | None = os.getenv("DEFAULT_ROBOTDOG_ID")


def set_default_robotdog_id(device_id: str | None) -> str | None:
    """配置机器人默认ID，便于缺省槽位时放行流程。返回旧值用于恢复。"""
    global _DEFAULT_ROBOTDOG_ID
    previous = _DEFAULT_ROBOTDOG_ID
    if device_id is None:
        _DEFAULT_ROBOTDOG_ID = None
        return previous
    normalized = device_id.strip()
    _DEFAULT_ROBOTDOG_ID = normalized or None
    return previous

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
    # 统一意图标识，避免同义写法遗漏校验
    canonical = (intent_type or "").strip().lower().replace("-", "_")
    missing: List[str] = []

    # 救援任务/模拟共用必填项，缺失时提示指挥员补充
    if canonical in {"rescue_task_generate", "rescue_task_generation", "rescue_simulation"}:
        rescue_missing: List[str] = []
        if not _has_coordinates(slots):
            rescue_missing.append("coordinates")
        if rescue_missing:
            logger.info(
                "intent_required_missing",
                intent=canonical,
                missing=rescue_missing,
            )
            missing.extend(rescue_missing)

    # 侦察任务需要明确目标与位置，缺少时提前追问
    if canonical in {"scout_task_generate", "scout_task_generation"}:
        scout_missing: List[str] = []  # 收集侦察分支缺失字段
        if not _has_non_empty_text(slots.get("target_type")):
            scout_missing.append("target_type")  # 缺少侦察目标类型，设备选型无法进行
        if not _has_location(slots):
            scout_missing.append("location")  # 没有侦察位置无法规划航线
        if not _has_detail_text(slots.get("objective_summary"), min_len=15):
            scout_missing.append("objective_summary")  # 目标概述不足将影响情报生成
        if scout_missing:
            logger.info("intent_required_missing", intent=canonical, missing=scout_missing)
            missing.extend(scout_missing)

    if canonical == "scout_task_simple":
        if not _has_coordinates(slots):
            logger.info("intent_required_missing", intent=canonical, missing=["coordinates"])
            missing.append("coordinates")

    if canonical == "hazard_report":
        if not _has_non_empty_text(slots.get("event_type")):
            missing.append("event_type")
        if not _has_location(slots):
            missing.append("location")

    if canonical == "device_control_robotdog":
        # 若未配置默认ID则强制追问，否则允许走默认配置
        robotdog_missing: List[str] = []
        device_id = slots.get("device_id")
        has_device_id = False
        if isinstance(device_id, str):
            has_device_id = bool(device_id.strip())
        elif device_id is not None:
            has_device_id = True

        if not has_device_id:
            if not _DEFAULT_ROBOTDOG_ID:
                robotdog_missing.append("device_id")

        if robotdog_missing:
            logger.info("intent_required_missing", intent=canonical, missing=robotdog_missing)
            missing.extend(robotdog_missing)

    if canonical == "task-progress-query":
        # 任务进度查询：task_id 与 task_code 至少一项
        tid = slots.get("task_id")
        tcode = slots.get("task_code")
        if not (_has_non_empty_text(str(tid) if tid is not None else "") or _has_non_empty_text(str(tcode) if tcode is not None else "")):
            # 用 task_id 作为缺失标记，后续由会话上下文谨慎自动绑定或走澄清
            missing.append("task_id")

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
        if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
            rsp = llm_client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = rsp.choices[0].message.content.strip()
        else:
            from langchain_core.messages import HumanMessage
            rsp = llm_client.invoke([HumanMessage(content=prompt)])
            content = str(rsp.content).strip()
            
        logger.info(
            "intent_prompt_generated",
            intent=intent_type,
            missing=missing_fields,
            prompt_preview=content,
        )
        return content
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
    # 兼容别名：将 video_analyze / video-analysis / video_analysis 等归并为 video-analysis
    if isinstance(intent_type, str):
        normalized = intent_type.strip().replace(" ", "").lower()
        if normalized in {"video_analyze", "videoanalyze", "video-analysis", "video_analysis"}:
            intent_type = "video-analysis"
            intent = intent | {"intent_type": intent_type}
        # 兼容 system_data_query / system-data-query
        elif normalized in {"system_data_query", "systemdataquery", "system-data-query"}:
            intent_type = "system-data-query"
            intent = intent | {"intent_type": intent_type}
    slots = intent.get("slots") or {}

    from emergency_agents.intent.schemas import INTENT_SCHEMAS
    from emergency_agents.intent.slot_normalizer import normalize_slots

    cleaned_slots = normalize_slots(intent_type, slots)
    intent = intent | {"slots": cleaned_slots}
    slots = cleaned_slots

    thread_id = str(state.get("thread_id") or "")
    user_id = str(state.get("user_id") or "")

    schema = INTENT_SCHEMAS.get(intent_type)
    if not schema:
        logger.info("intent_type=%s 无schema定义，跳过验证", intent_type)
        return state | {"validation_status": "valid"}

    skip_validation_intents = {"device-control"}
    if intent_type in skip_validation_intents:
        logger.info("intent_type=%s 跳过槽位验证（基础控制）", intent_type)
        return state | {"intent": intent, "validation_status": "valid"}

    extra_missing = _enforce_required_fields(intent_type, slots)
    sanitized_extra = _sanitize_missing_fields(extra_missing)

    try:
        jsonschema.validate(slots, schema)
        logger.info(
            "intent_validation_passed",
            intent=intent_type,
            thread_id=thread_id,
            user_id=user_id,
        )
        if sanitized_extra:
            attempt = int(state.get("validation_attempt", 0)) + 1
            logger.info(
                "intent_validation_missing_after_schema",
                intent=intent_type,
                thread_id=thread_id,
                user_id=user_id,
                missing=sanitized_extra,
                attempt=attempt,
            )
            prompt = _generate_prompt_for_missing(intent_type, sanitized_extra, llm_client, llm_model)
            return state | {
                "validation_status": "invalid",
                "prompt": prompt,
                "missing_fields": sanitized_extra,
                "validation_attempt": attempt,
            }
        return state | {"validation_status": "valid"}
    except jsonschema.ValidationError as e:
        missing = _sanitize_missing_fields(_extract_missing_fields(e, schema))
        extra_from_rules = _sanitize_missing_fields(extra_missing)
        combined_missing = sorted({*missing, *extra_from_rules})

        if not combined_missing:
            logger.warning(
                "intent_validation_missing_unknown",
                intent=intent_type,
                thread_id=thread_id,
                user_id=user_id,
                error=e.message,
            )
            combined_missing = ["未知字段"]

        attempt = int(state.get("validation_attempt", 0)) + 1

        if attempt > 3:
            logger.warning(
                "intent_validation_attempt_exceeded",
                intent=intent_type,
                thread_id=thread_id,
                user_id=user_id,
                attempt=attempt,
                missing=combined_missing,
            )
            return state | {
                "validation_status": "failed",
                "validation_attempt": attempt,
                "last_error": {"validator": "max_attempts_exceeded", "missing": combined_missing}
            }

        prompt = _generate_prompt_for_missing(intent_type, combined_missing, llm_client, llm_model)

        logger.info(
            "intent_validation_missing_after_schema_error",
            intent=intent_type,
            thread_id=thread_id,
            user_id=user_id,
            missing=combined_missing,
            attempt=attempt,
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
