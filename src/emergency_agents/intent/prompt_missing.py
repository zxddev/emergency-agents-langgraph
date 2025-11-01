# Copyright 2025 msq
"""缺槽追问与补充。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langgraph.types import interrupt

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
