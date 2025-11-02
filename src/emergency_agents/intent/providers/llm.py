from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List

import structlog

from emergency_agents.llm.client import LLMClientProtocol
from emergency_agents.intent.providers.base import IntentProvider
from emergency_agents.intent.providers.types import IntentPrediction
from emergency_agents.intent.unified_intent import (
    ALLOWED_EVENT_TYPES,
    DISPLAY_TO_CANONICAL,
    INTENT_DISPLAY_MAP,
)

logger = structlog.get_logger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "你是应急救援指挥车的意图识别专家，需要判断指挥员的语音或文本请求属于哪个业务意图。"
    "请严格输出JSON，不要包含额外解释。"
)


def _build_prompt(text: str) -> str:
    """构造与统一意图模板一致的提示内容。"""
    intent_lines = "\n".join(
        f"- {display}（内部标识: {canonical})"
        for canonical, display in sorted(INTENT_DISPLAY_MAP.items(), key=lambda item: item[1])
    )
    schema_example = {
        "intent_type": "RESCUE_TASK_GENERATION",
        "slots": {
            "location_name": "XX县XX镇",
            "coordinates": {"lat": 31.238, "lng": 99.382},
            "mission_type": "rescue",
            "situation_summary": "现场教学楼受损，东侧12人被困，需破拆清除障碍后转运。",
            "disaster_type": "earthquake",
        },
        "meta": {
            "confidence": 0.86,
            "margin": 0.35,
            "need_confirm": False,
        },
        "ranking": [
            {"intent": "RESCUE_TASK_GENERATION", "confidence": 0.86},
            {"intent": "HAZARD_REPORT", "confidence": 0.10},
        ],
    }
    prompt = (
        "你是应急救援指挥系统的意图识别专家，请分析指挥员输入并返回严格的JSON结果。\n\n"
        "输出要求：\n"
        "1. `intent_type` 必须从以下列表中选择（全部大写，保持完全一致）：\n"
        f"{intent_lines}\n"
        "   若请求超出范围或意图不明，返回 `UNKNOWN`。\n"
        "2. `slots` 需给出结构化槽位，没有值使用 null，不要编造关键字段。\n"
        "3. `meta.confidence` 取值 0.0-1.0；`meta.margin` 为Top1与Top2置信度差值；"
        "`meta.need_confirm` 表示是否需要人工确认。\n"
        "4. 对于 `RESCUE_TASK_GENERATION` / `RESCUE_SIMULATION`，`slots` **必须包含**：\n"
        "   - `coordinates.lat` 和 `coordinates.lng`（浮点数，经纬度坐标）；\n"
        "   - `situation_summary`（不少于15个汉字的现场详细描述，用于后续态势分析）。\n"
        "   - `mission_type`（缺省写为 `rescue`，除非用户明确要求侦察）。\n"
        "   如果用户暂未给出坐标或细节，请保留为 null，让系统提示补充，不得凭空捏造。\n"
        "5. `ranking` 填写前2-3个候选意图及置信度，按置信度降序排列。\n"
        "6. 合法事件类型列表："
        f"{ALLOWED_EVENT_TYPES}，slots中出现 event_type 时必须从此列表选择。\n"
        "7. 以下场景必须返回 `intent_type=\"UNKNOWN\"`：问候、闲聊、测试语句、"
        "模糊查询或非应急救援业务。\n\n"
        "意图判定指引：\n"
        "- 语句中出现建筑/设施倒塌、人员被困、伤亡、请求支援、需要立即处置等表述，一律判定为 `RESCUE_TASK_GENERATION`，即便用户只是在汇报现象，也代表需要生成救援行动。\n"
        "- 仅在纯信息播报、无行动需求的情况下使用 `HAZARD_REPORT`。\n"
        '- 当用户给出的描述过于笼统（只提到灾种或灾点，未说明人数、障碍、危险源等细节）时，将 `situation_summary` 置为 null，交由系统追问更具体细节；例如 "XX地震，建筑倒塌" 这类单句概述视为细节不足。\\n\\n'
        f"示例结构：\n{json.dumps(schema_example, ensure_ascii=False, indent=2)}\n\n"
        f"指挥员输入：{text}\n"
        "请只返回JSON，不要附加解释。"
    )
    return prompt


def _clean_json_text(content: str) -> str:
    """从模型输出中提取纯净JSON文本。"""
    if not content:
        raise ValueError("LLM返回内容为空")

    trimmed = content.strip()
    if trimmed.startswith("```"):
        segments = [
            segment.strip("` \n")
            for segment in re.split(r"```(?:json)?", trimmed)
            if segment and segment.strip("` \n")
        ]
        if segments:
            return segments[0]
    return trimmed


def _parse_prediction(raw_text: str) -> IntentPrediction:
    """解析模型返回的JSON结果。"""
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("意图结果不是JSON对象")

    meta = payload.get("meta")
    if not isinstance(meta, dict):
        meta = {}

    ranking_raw = payload.get("ranking") or payload.get("intent_ranking") or []
    ranking: List[Dict[str, Any]] = []
    if isinstance(ranking_raw, list):
        for item in ranking_raw:
            if not isinstance(item, dict):
                continue
            intent = item.get("intent") or item.get("name")
            if not isinstance(intent, str) or not intent:
                continue
            canonical_rank = DISPLAY_TO_CANONICAL.get(intent) or DISPLAY_TO_CANONICAL.get(intent.upper(), intent)
            ranking.append(
                {
                    "intent": canonical_rank,
                    "confidence": float(item.get("confidence") or item.get("score") or 0.0),
                }
            )

    slots = payload.get("slots")
    slots_dict: Dict[str, Any] = slots if isinstance(slots, dict) else {}

    confidence = float(
        meta.get("confidence")
        or payload.get("confidence")
        or payload.get("score")
        or 0.0
    )
    margin = float(meta.get("margin") or payload.get("margin") or 1.0)

    intent_raw = (
        payload.get("intent")
        or payload.get("intent_type")
        or "unknown"
    )
    intent_str = str(intent_raw).strip() or "unknown"
    canonical_intent = (
        DISPLAY_TO_CANONICAL.get(intent_str)
        or DISPLAY_TO_CANONICAL.get(intent_str.upper())
        or intent_str
    )

    prediction: IntentPrediction = {
        "intent": str(
            canonical_intent
        ).strip().lower()
        or "unknown",
        "confidence": confidence,
        "margin": margin,
        "slots": slots_dict,
        "need_confirm": bool(meta.get("need_confirm") or payload.get("need_confirm") or False),
        "source": "llm",
        "ranking": ranking,
        "raw": payload,
    }
    return prediction


class LLMIntentProvider(IntentProvider):
    """利用LLM直接完成意图识别。"""

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        model: str,
        system_prompt: str | None = None,
    ) -> None:
        super().__init__("llm")
        self._llm_client = llm_client
        self._model = model
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

    def _build_messages(self, text: str) -> list[dict[str, str]]:
        """构造聊天消息。"""
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": _build_prompt(text)},
        ]

    def predict(self, text: str) -> IntentPrediction:
        """调用LLM完成意图识别并解析结果。"""
        if not text or not text.strip():
            raise ValueError("意图识别文本为空")

        messages = self._build_messages(text)
        logger.debug("llm_intent_request", model=self._model, message_preview=text[:80])
        response = self._llm_client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.0,
        )
        content = getattr(response.choices[0].message, "content", "")
        logger.debug("llm_intent_response", preview=content[:120])
        clean_text = _clean_json_text(content)
        prediction = _parse_prediction(clean_text)
        return prediction


__all__ = ["LLMIntentProvider"]
