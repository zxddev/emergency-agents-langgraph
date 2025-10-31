# Copyright 2025 msq
"""统一意图处理模块：合并意图分类和槽位验证为单次LLM调用。

本模块实现统一意图识别架构，通过一次LLM调用同时完成：
1. 意图分类（intent classification）
2. 槽位提取（slot extraction）
3. 槽位验证（slot validation）
4. 置信度评估（confidence scoring）

设计目标：
- 性能提升：减少LLM调用次数（从2次降至1次）
- 降低延迟：单次调用延迟从27.6秒降至10-18秒
- 保持准确率：≥93%（使用glm-4.5-air模型）
"""
from __future__ import annotations

import json
import os
import structlog
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, ValidationError
from emergency_agents.llm.endpoint_manager import LLMEndpointsExhaustedError
from emergency_agents.intent.schemas import INTENT_SCHEMAS

logger = structlog.get_logger(__name__)

PLACEHOLDER_MISSING_FIELDS: set[str] = {
    "未知字段",
    "unknown_field",
    "unknown",
    "missing_field",
    "未知槽位",
}

ALLOWED_EVENT_TYPES: List[str] = [
    "people_trapped",
    "secondary_hazard",
    "infrastructure_failure",
    "resource_request",
    "external_info",
    "transit_update",
    "communication",
    "sensor_data",
    "uav_intelligence",
    "road_condition",
    "position_report",
]


class UnifiedIntentResult(BaseModel):
    """统一意图识别结果（强类型）。

    Attributes:
        intent_type: 意图类型，如'RESCUE_TASK_GENERATION'或'UNKNOWN'
        slots: 槽位数据字典
        confidence: 置信度（0.0-1.0），用于判断是否触发专家咨询
        validation_status: 验证状态
            - valid: 所有必填字段都有值
            - invalid: 缺少必填字段
            - unknown: 无法识别意图
        missing_fields: 缺失的必填字段列表
        prompt: 补充信息提示（validation_status=invalid时生成）
    """
    intent_type: str = Field(..., description="意图类型")
    slots: Dict[str, Any] = Field(default_factory=dict, description="槽位数据")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度（0.0-1.0）")
    validation_status: Literal["valid", "invalid", "unknown"] = Field(..., description="验证状态")
    missing_fields: List[str] = Field(default_factory=list, description="缺失字段列表")
    prompt: str | None = Field(None, description="补充信息提示")
    canonical_intent_type: str | None = Field(
        default=None, description="内部使用的规范化意图类型（小写/中划线形式）"
    )


INTENT_DISPLAY_OVERRIDES: Dict[str, str] = {
    "rescue_task_generate": "RESCUE_TASK_GENERATION",
    "rescue-task-generate": "RESCUE_TASK_GENERATION",
    "rescue_simulation": "RESCUE_SIMULATION",
    "rescue-simulation": "RESCUE_SIMULATION",
    "hazard_report": "HAZARD_REPORT",
    "trapped_report": "TRAPPED_REPORT",
}
INTENT_DISPLAY_MAP: Dict[str, str] = {}
DISPLAY_TO_CANONICAL: Dict[str, str] = {}
for canonical_name in INTENT_SCHEMAS.keys():
    display_name = INTENT_DISPLAY_OVERRIDES.get(
        canonical_name, canonical_name.upper().replace("-", "_")
    )
    INTENT_DISPLAY_MAP[canonical_name] = display_name
for canonical_name, display_name in INTENT_DISPLAY_MAP.items():
    DISPLAY_TO_CANONICAL.setdefault(display_name, canonical_name)
    # 允许模型直接返回小写原始值
    DISPLAY_TO_CANONICAL.setdefault(canonical_name, canonical_name)


def _has_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_coordinates(slots: Dict[str, Any]) -> bool:
    coordinates = slots.get("coordinates")
    if isinstance(coordinates, dict):
        lat = coordinates.get("lat")
        lng = coordinates.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            return True
    lat = slots.get("lat")
    lng = slots.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return True
    return False


def _has_location(slots: Dict[str, Any]) -> bool:
    location_keys = ["location_name", "location_text", "location"]
    if any(_has_non_empty_text(slots.get(key)) for key in location_keys):
        return True
    return _has_coordinates(slots)


def _apply_required_field_validation(
    result: UnifiedIntentResult,
    canonical_intent: str | None
) -> None:
    if not canonical_intent:
        return
    if canonical_intent.upper() == "UNKNOWN":
        return

    slots = result.slots if isinstance(result.slots, dict) else {}
    missing_fields_raw = list(result.missing_fields)
    filtered_missing: List[str] = []
    for field in missing_fields_raw:
        if not isinstance(field, str):
            continue
        sanitized = field.strip().strip("“”\"' ")
        if not sanitized:
            continue
        if sanitized in PLACEHOLDER_MISSING_FIELDS:
            continue
        filtered_missing.append(sanitized)
    missing_fields: List[str] = filtered_missing

    def mark_missing(field: str) -> None:
        if field not in missing_fields:
            missing_fields.append(field)

    if canonical_intent in {
        "rescue_task_generate",
        "rescue-task-generate",
        "rescue_simulation",
        "rescue-simulation",
    }:
        mission_type = slots.get("mission_type")
        if not _has_non_empty_text(mission_type):
            mark_missing("mission_type")

        if not _has_location(slots):
            mark_missing("location")

        if missing_fields and not result.prompt:
            prompt_items: List[str] = []
            if "mission_type" in missing_fields:
                prompt_items.append("任务类型")
            if "location" in missing_fields:
                prompt_items.append("精确位置（地点名称或经纬度）")
            result.prompt = f"请补充{'和'.join(prompt_items)}，以便生成救援任务。"

    if canonical_intent == "hazard_report":
        event_type = slots.get("event_type")
        if not _has_non_empty_text(event_type) or str(event_type).strip() not in ALLOWED_EVENT_TYPES:
            mark_missing("event_type")

        if not _has_location(slots):
            mark_missing("location")

        if missing_fields and not result.prompt:
            prompt_items = []
            if "event_type" in missing_fields:
                prompt_items.append("灾害类型")
            if "location" in missing_fields:
                prompt_items.append("具体地点（地点名称或经纬度）")
            result.prompt = f"请补充{'和'.join(prompt_items)}，以便记录灾情。"

    if missing_fields:
        result.validation_status = "invalid"
        result.missing_fields = missing_fields
        return

    result.validation_status = "valid"
    result.missing_fields = []
    result.prompt = None

def _safe_json_parse(text: str) -> Dict[str, Any]:
    """容错JSON解析（复用classifier.py的实现）。

    支持多种格式：
    1. 纯JSON
    2. Markdown代码块中的JSON
    3. 文本中嵌入的JSON

    Args:
        text: LLM返回的原始文本

    Returns:
        解析后的字典，失败时返回兜底结构
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    import re

    # 尝试提取Markdown代码块中的JSON
    m = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 尝试提取文本中的JSON对象
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    logger.error("unified_intent JSON parse failed", extra={"content_preview": text[:200]})

    # 返回兜底结构
    return {
        "intent_type": "UNKNOWN",
        "slots": {},
        "confidence": 0.0,
        "validation_status": "unknown",
        "missing_fields": [],
        "prompt": None
    }


def unified_intent_node(
    state: Dict[str, Any],
    llm_client,
    llm_model: str
) -> Dict[str, Any]:
    """统一意图处理节点（合并分类+验证）。

    工作流程：
    1. 幂等性检查：如果state["unified_intent"]已存在，直接返回
    2. 提取用户输入：从messages或raw_report中获取
    3. 构建统一prompt：包含分类+验证逻辑
    4. 调用LLM：单次调用返回完整结构
    5. 解析和验证：使用Pydantic模型验证输出
    6. 槽位标准化：调用normalize_slots处理特殊字段

    Args:
        state: 图状态，期望包含messages或raw_report
        llm_client: LLM客户端（OpenAI兼容接口）
        llm_model: 模型名（推荐glm-4.5-air）

    Returns:
        更新后的state，包含unified_intent字段

    示例：
        >>> state = {"messages": [{"role": "user", "content": "地震发生了"}]}
        >>> result = unified_intent_node(state, llm_client, "glm-4.5-air")
        >>> result["unified_intent"]["intent_type"]
        'hazard_report'
    """
    # 幂等性检查（避免重复LLM调用）
    if "unified_intent" in state and state["unified_intent"]:
        logger.debug("unified_intent already exists, skipping LLM call")
        return state

    # 提取用户输入
    input_text = ""
    msgs = state.get("messages") or []
    if isinstance(msgs, list) and msgs:
        for msg in reversed(msgs):
            if isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                input_text = str(msg.get("content"))
                break

    if not input_text:
        input_text = str(state.get("raw_report") or "").strip()

    # 验证输入：过滤空字符串、None以及只有空白字符的情况
    if not input_text or not input_text.strip():
        # 无输入或只有空白字符则标记未知
        logger.warning("unified_intent_empty_or_whitespace_input",
                      input_repr=repr(input_text),
                      thread_id=state.get("thread_id"))
        result = UnifiedIntentResult(
            intent_type="UNKNOWN",
            slots={},
            confidence=0.0,
            validation_status="unknown",
            missing_fields=[],
            prompt=None
        )
        return state | {"unified_intent": result.model_dump()}

    # 构建统一prompt
    from emergency_agents.intent.schemas import INTENT_SCHEMAS

    intent_mapping_lines = "\n".join(
        f"- {display}（内部标识: {canonical}）"
        for canonical, display in sorted(INTENT_DISPLAY_MAP.items(), key=lambda item: item[1])
    )

    # 构建JSON Schema示例（帮助LLM理解输出格式）
    schema_example = {
        "intent_type": "意图类型（从可用列表中选择，或'UNKNOWN'）",
        "slots": {"slot_name": "value", "another_slot": "value"},
        "confidence": 0.95,
        "validation_status": "valid 或 invalid 或 unknown",
        "missing_fields": ["缺失字段1", "缺失字段2"],
        "prompt": "如果validation_status=invalid，生成友好的补充信息提示",
        "slots.event_type": "事件类型（只可取: " + ", ".join(ALLOWED_EVENT_TYPES) + ")",
    }

    prompt = f"""你是应急救援指挥系统的意图识别专家。请分析用户输入并返回JSON格式的结果。

**重要提示**：这是应急救援业务系统，只处理救援相关的业务请求。

返回时 `intent_type` 必须使用下面列表中的大写枚举值（保持大小写完全一致）：
{intent_mapping_lines}
如果你认为用户请求超出业务范围或意图不明确，请使用 `UNKNOWN`。

合法事件类型：{ALLOWED_EVENT_TYPES}

意图判定要点：
- **RESCUE_TASK_GENERATION**：用户明确请求“制定/生成/安排救援或侦察行动”，通常包含“需要去”“安排任务”“生成方案”等措辞，并且围绕执行动作；优先判为救援任务生成而不是灾情汇报。
- **HAZARD_REPORT**：用户仅汇报已发生的灾情、二次灾害或现场状态，不涉及让系统生成行动方案。
- 其他意图按照名称匹配业务含义；无法归类时返回 `UNKNOWN`。

用户输入：{input_text}

请返回以下JSON结构（必须严格遵守格式）：
{json.dumps(schema_example, ensure_ascii=False, indent=2)}

意图识别规则：
1. **只有明确的应急救援业务请求才匹配具体意图**（confidence ≥ 0.7）
   - 例如：灾情报告、设备控制、路线查询、任务生成等
2. **以下情况必须返回 UNKNOWN**（intent_type="UNKNOWN"，validation_status="unknown"）：
   - 通用问候：你好、在吗、能听见我吗等
   - 闲聊：天气怎么样、吃了吗等
   - 测试语句：测试、试试看等
   - 模糊查询：看一下XX、了解一下XX（没有明确的查询对象）
   - 超出应急救援范围的请求
3. 槽位验证：根据意图类型的必填字段检查
   - 所有必填字段都有值 → validation_status="valid"
   - 缺少必填字段 → validation_status="invalid"，列出missing_fields，生成友好的prompt询问缺失信息
   - **RESCUE_TASK_GENERATION**：必须提供 `mission_type`，并且至少包含地点信息（`location`/`location_name` 或 `coordinates.lat` + `coordinates.lng`），缺失任何一项均判定为 invalid。
   - **HAZARD_REPORT**：必须包含 `event_type` 与地点信息（`location_text` 或 `coordinates.lat` + `coordinates.lng`），缺失时判定为 invalid。
4. confidence范围：0.0-1.0，评估识别的确定性
5. 若判定为救援任务相关意图（如 RESCUE_TASK_GENERATION），请在 slots 中补充 event_type 字段，取值必须来自合法事件类型列表；无法确定时返回 null 并设置 validation_status="invalid"，给出补充提示。

**示例**：
- "能否听见我说话？" → UNKNOWN（通用测试）
- "帮我看一下汶川地震的情况" → UNKNOWN（模糊查询，没有明确查询对象）
- "查询无人机XYZ的电量" → device_status_query（明确业务请求）
- "有人被困在A楼5层" → trapped_report（明确业务报告）

只返回JSON，不要其他说明文字。
"""

    try:
        logger.info("unified_intent_start", extra={
            "input_preview": input_text[:100],
            "llm_model": llm_model,
            "prompt_length": len(prompt)
        })

        # 调用LLM（添加详细日志）
        import time
        t_llm_start = time.time()

        logger.info("llm_call_starting", extra={
            "model": llm_model,
            "temperature": 0,
            "messages_count": 1
        })

        rsp = llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,  # 确保稳定性
            timeout=30  # 添加30秒超时
        )

        t_llm_done = time.time()
        llm_duration_ms = int((t_llm_done - t_llm_start) * 1000)

        content = rsp.choices[0].message.content

        logger.info("llm_call_completed", extra={
            "duration_ms": llm_duration_ms,
            "response_length": len(content),
            "response_preview": content[:200]
        })

        # 安全解析JSON
        result_dict = _safe_json_parse(content)

        # Pydantic模型验证
        try:
            result = UnifiedIntentResult(**result_dict)
        except ValidationError as e:
            logger.error("unified_intent_pydantic_validation_failed", extra={
                "error": str(e),
                "content_preview": content[:200]
            })

            # 直接返回 UNKNOWN，保持单次 LLM，避免降级与二次调用
            fallback_result = UnifiedIntentResult(
                intent_type="UNKNOWN",
                slots={},
                confidence=0.0,
                validation_status="unknown",
                missing_fields=[],
                prompt=None
            )
            return state | {"unified_intent": fallback_result.model_dump()}

        # 槽位标准化（处理特殊字段，如时间戳、坐标格式等）
        original_intent_type = result.intent_type
        slots = result.slots
        canonical_intent = result.canonical_intent_type
        if not canonical_intent:
            canonical_intent = DISPLAY_TO_CANONICAL.get(result.intent_type, result.intent_type)
        display_intent = INTENT_DISPLAY_MAP.get(canonical_intent, result.intent_type)
        result.intent_type = display_intent
        result.canonical_intent_type = canonical_intent

        normalization_key = canonical_intent or original_intent_type
        if isinstance(slots, dict) and normalization_key != "UNKNOWN":
            from emergency_agents.intent.slot_normalizer import normalize_slots

            normalized_slots = normalize_slots(normalization_key, slots)
            result.slots = normalized_slots

        _apply_required_field_validation(result, canonical_intent)

        logger.info("unified_intent_success", extra={
            "intent_type": result.intent_type,
            "confidence": result.confidence,
            "validation_status": result.validation_status,
            "has_missing_fields": len(result.missing_fields) > 0
        })

        return state | {"unified_intent": result.model_dump()}

    except LLMEndpointsExhaustedError as exc:
        logger.error(
            "unified_intent_llm_overloaded",
            extra={"error": str(exc), "states": getattr(exc, "states", {})},
        )
        fallback_result = UnifiedIntentResult(
            intent_type="UNKNOWN",
            slots={},
            confidence=0.0,
            validation_status="unknown",
            missing_fields=[],
            prompt="当前模型繁忙，请稍后重试。"
        )
        return state | {
            "unified_intent": fallback_result.model_dump(),
            "llm_overload": {"reason": "rate_limit", "message": "模型限流"},
        }

    except Exception as e:
        logger.error("unified_intent_failed", extra={"error": str(e)}, exc_info=True)

        # 返回兜底结构
        fallback_result = UnifiedIntentResult(
            intent_type="UNKNOWN",
            slots={},
            confidence=0.0,
            validation_status="unknown",
            missing_fields=[],
            prompt=None
        )

        return state | {"unified_intent": fallback_result.model_dump()}
