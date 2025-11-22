# Copyright 2025 msq
"""缺槽追问与补充。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from langgraph.types import interrupt

from emergency_agents.intent.schemas import ClarifyOption, ClarifyRequest

logger = logging.getLogger(__name__)


def prompt_missing_slots_node(state: Dict[str, Any], llm_client, llm_model: str) -> Dict[str, Any]:
    """中断追问缺失槽位。
    
    Args:
        state: 图状态，必含state.prompt。
        llm_client: LLM客户端。
        llm_model: 模型名。
    
    Returns:
        更新后的state，补充slots后返回空dict触发重新验证。
    """
    prompt = state.get("prompt", "请补充缺失信息")
    missing_fields = state.get("missing_fields") or []
    
    user_input = interrupt({"question": prompt, "missing_fields": missing_fields})
    
    intent = state.get("intent") or {}
    slots = intent.get("slots") or {}

    previous_summary = slots.get("situation_summary")

    补充值 = _parse_user_补充(user_input, missing_fields, llm_client, llm_model)

    slots.update(补充值)

    _merge_situation_summary(slots, supplement=补充值, previous_summary=previous_summary)

    logger.info("用户补充槽位", extra={"fields": list(补充值.keys()), "summary_length": len(str(slots.get("situation_summary") or ""))})

    return {"intent": intent | {"slots": slots}}


def prompt_missing_slots_enhanced(
    state: Dict[str, Any],
    llm_client,
    llm_model: str,
    *,
    options: List[ClarifyOption] | None = None,
) -> Dict[str, Any]:
    """增强版缺槽追问：当视频分析缺少 device_name 时，提供结构化候选供澄清。

    - 对 video-analysis：构造 ClarifyRequest（options 来源：Mem0 提示 + DB 有视频能力的设备）
    - 否则退回到通用文本追问逻辑
    """
    intent: Dict[str, Any] = state.get("intent") or {}
    intent_type = str((intent.get("intent_type") or "").strip()).lower()
    slots = intent.get("slots") or {}
    missing_fields: List[str] = list(state.get("missing_fields") or [])

    # 仅对视频分析且缺少 device_name 的场景提供结构化澄清
    if intent_type == "video-analysis" and (not slots.get("device_name") or "device_name" in missing_fields):
        clarify_options: List[ClarifyOption] = list(options or [])

        # 3) 组装 ClarifyRequest
        payload: ClarifyRequest = {
            "type": "clarify",
            "slot": "device_name",
            "options": clarify_options,
            "reason": "视频分析需指定设备名称",
        }
        if clarify_options:
            # 默认选中第一项（后续可用记忆精确排序与定位）
            payload["default_index"] = 0

        # 4) 发出中断（结构化）并携带 ui_actions 以便 API 直接展示
        interrupt(payload)
        ui_actions = [payload]  # 同步返回到 state，便于 API 端合并
        logging.getLogger(__name__).info("video_analysis_clarify_emitted", option_count=len(clarify_options))
        return {"ui_actions": ui_actions}

    # 其它意图走原有文本澄清
    return prompt_missing_slots_node(state, llm_client, llm_model)


def _parse_user_补充(user_input: Any, missing_fields: list, llm_client, llm_model: str) -> Dict[str, Any]:
    """解析用户补充内容。
    
    Args:
        user_input: 用户输入（可能是dict或str）。
        missing_fields: 缺失字段列表。
        llm_client: LLM客户端。
        llm_model: 模型名。
    
    Returns:
        解析后的槽位字典。
    """
    if isinstance(user_input, dict):
        return {k: v for k, v in user_input.items() if k in missing_fields}
    
    if not isinstance(user_input, str):
        user_input = str(user_input)
    
    try:
        parsed = json.loads(user_input)
        if isinstance(parsed, dict):
            return {k: v for k, v in parsed.items() if k in missing_fields}
    except Exception:
        pass
    
    prompt = (
        f"用户补充了以下信息：{user_input}\n"
        f"需要提取的字段：{', '.join(missing_fields)}\n"
        "请以JSON格式返回提取结果，例如 {{\"lat\": 31.68, \"lng\": 103.85}}。只返回JSON。"
    )
    
    try:
        if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
            rsp = llm_client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            content = rsp.choices[0].message.content
        else:
            from langchain_core.messages import HumanMessage
            rsp = llm_client.invoke([HumanMessage(content=prompt)])
            content = str(rsp.content)

        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return {k: v for k, v in parsed.items() if k in missing_fields}
    except Exception as e:
        logger.error("LLM解析用户补充失败: %s", e, exc_info=True)
    
    return {}


def _merge_situation_summary(
    slots: Dict[str, Any],
    *,
    supplement: Dict[str, Any],
    previous_summary: Any,
) -> None:
    """整合多轮输入确保态势描述完整。

    - 保留历史摘要与最新补充，去重后合并。
    - 自动拼接任务类型、地点、坐标等结构化信息，增强描述密度。
    """

    fragments: List[str] = []
    seen: set[str] = set()

    def _append(candidate: Optional[str]) -> None:
        if not isinstance(candidate, str):
            return
        text = candidate.strip()
        if not text or text in seen:
            return
        seen.add(text)
        fragments.append(text)

    _append(str(previous_summary) if previous_summary is not None else None)
    _append(str(supplement.get("situation_summary")) if supplement.get("situation_summary") is not None else None)

    normalized_summary = slots.get("situation_summary")
    if normalized_summary is not previous_summary:
        _append(str(normalized_summary) if normalized_summary is not None else None)

    mission_type = _first_text(slots, supplement, keys=("mission_type",))
    if mission_type:
        _append(f"任务类型：{mission_type}")

    location_name = _first_text(slots, supplement, keys=("location_name", "location"))
    if location_name:
        _append(f"地点：{location_name}")

    coordinates = _first_mapping(slots, supplement, keys=("coordinates",))
    if coordinates:
        lat = coordinates.get("lat") or coordinates.get("latitude")
        lng = coordinates.get("lng") or coordinates.get("longitude") or coordinates.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            _append(f"坐标：{lat:.6f}, {lng:.6f}")

    if fragments:
        slots["situation_summary"] = "；".join(fragments)


def _first_text(
    slots: Dict[str, Any],
    supplement: Dict[str, Any],
    *,
    keys: Sequence[str],
) -> Optional[str]:
    for container in (supplement, slots):
        for key in keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _first_mapping(
    slots: Dict[str, Any],
    supplement: Dict[str, Any],
    *,
    keys: Sequence[str],
) -> Optional[Dict[str, Any]]:
    for container in (supplement, slots):
        for key in keys:
            value = container.get(key)
            if isinstance(value, dict):
                return value
    return None
