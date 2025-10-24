# Copyright 2025 msq
from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _safe_json_parse(text: str) -> Dict[str, Any]:
    """容错JSON解析。

    Args:
        text: LLM返回的原始文本。

    Returns:
        解析后的字典，失败时给出兜底结构。
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    import re
    m = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    logger.error("intent classify JSON parse failed: %s", text[:200])
    return {"intent_type": "unknown", "slots": {}, "meta": {"need_confirm": False}}


def intent_classifier_node(state: Dict[str, Any], llm_client, llm_model: str) -> Dict[str, Any]:
    """意图分类节点：若state中无intent则尝试基于文本进行分类。

    Args:
        state: 图状态，期望包含 messages 或 raw_report。
        llm_client: LLM客户端。
        llm_model: 模型名。

    Returns:
        更新后的state，确保存在 state["intent"] 字段。
    """
    if state.get("intent"):
        return state

    # 输入优先级：messages最后一条用户文本 > raw_report > 空
    input_text = ""
    msgs = state.get("messages") or []
    if isinstance(msgs, list) and msgs:
        for msg in reversed(msgs):
            if isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                input_text = str(msg.get("content"))
                break
    if not input_text:
        input_text = str(state.get("raw_report") or "").strip()

    if not input_text:
        # 无输入则标记未知
        return state | {"intent": {"intent_type": "unknown", "slots": {}, "meta": {"need_confirm": False}}}

    prompt = (
        "请将以下用户输入分类为预定义意图，并抽取槽位，以JSON返回：\n"
        "意图集合示例：recon_minimal, device_control_robotdog, trapped_report, hazard_report, route_safe_point_query, \n"
        "annotation_sign, geo_annotate, device_status_query, plan_task_approval, rfa_request, event_update。\n"
        "返回JSON结构：{\"intent_type\": str, \"slots\": {..}, \"meta\": {\"need_confirm\": bool}}。\n"
        f"用户输入：{input_text}\n"
        "只返回JSON。"
    )

    try:
        rsp = llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = rsp.choices[0].message.content
        intent = _safe_json_parse(content)
        if not isinstance(intent, dict):
            intent = {"intent_type": "unknown", "slots": {}, "meta": {"need_confirm": False}}
        if "meta" not in intent:
            intent["meta"] = {"need_confirm": False}
        return state | {"intent": intent}
    except Exception as e:
        logger.error("intent classify failed: %s", e, exc_info=True)
        return state | {"intent": {"intent_type": "unknown", "slots": {}, "meta": {"need_confirm": False}}}


