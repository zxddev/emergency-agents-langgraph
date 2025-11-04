# Copyright 2025 msq
"""缺槽追问与补充。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

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
    
    补充值 = _parse_user_补充(user_input, missing_fields, llm_client, llm_model)
    
    slots.update(补充值)
    
    logger.info("用户补充槽位: %s", 补充值)
    
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
        rsp = llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = rsp.choices[0].message.content
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return {k: v for k, v in parsed.items() if k in missing_fields}
    except Exception as e:
        logger.error("LLM解析用户补充失败: %s", e, exc_info=True)
    
    return {}
