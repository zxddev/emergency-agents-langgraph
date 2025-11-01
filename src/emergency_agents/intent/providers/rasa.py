from __future__ import annotations

from typing import Any, Dict, List

import structlog

from emergency_agents.intent.providers.http import HttpIntentProvider
from emergency_agents.intent.providers.types import IntentPrediction

logger = structlog.get_logger(__name__)


class RasaIntentProvider(HttpIntentProvider):
    """调用Rasa NLU服务完成意图识别。"""

    def __init__(self, base_url: str, timeout: float) -> None:
        super().__init__("rasa", base_url=base_url, timeout=timeout)

    def _request(self, text: str) -> Dict[str, Any]:
        """向Rasa发送解析请求并返回JSON。"""
        payload = {"text": text}
        response = self.client.post("/model/parse", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Rasa返回结构异常")
        return data

    @staticmethod
    def _build_slots(entities: Any) -> Dict[str, Any]:
        """根据实体列表提取槽位字典。"""
        if not isinstance(entities, list):
            return {}
        slots: Dict[str, Any] = {}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            key = entity.get("entity")
            value = entity.get("value")
            if isinstance(key, str) and key:
                slots[key] = value
        return slots

    @staticmethod
    def _build_ranking(intent_ranking: Any) -> List[Dict[str, Any]]:
        """构建候选意图列表。"""
        ranking: List[Dict[str, Any]] = []
        if not isinstance(intent_ranking, list):
            return ranking
        for item in intent_ranking:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name:
                continue
            ranking.append(
                {
                    "intent": name,
                    "confidence": float(item.get("confidence") or 0.0),
                }
            )
        return ranking

    def predict(self, text: str) -> IntentPrediction:
        """执行Rasa意图识别并规范化输出。"""
        if not text or not text.strip():
            raise ValueError("意图识别文本为空")

        data = self._request(text)
        intent_block = data.get("intent") if isinstance(data.get("intent"), dict) else {}
        intent_name = str(intent_block.get("name") or "unknown").strip() or "unknown"
        confidence = float(intent_block.get("confidence") or 0.0)

        ranking = self._build_ranking(data.get("intent_ranking"))
        if len(ranking) >= 2:
            margin = ranking[0]["confidence"] - ranking[1]["confidence"]
        elif ranking:
            margin = ranking[0]["confidence"]
        else:
            margin = confidence
        margin = max(margin, 0.0)

        slots = self._build_slots(data.get("entities"))

        prediction: IntentPrediction = {
            "intent": intent_name,
            "confidence": confidence,
            "margin": margin,
            "slots": slots,
            "need_confirm": False,
            "source": "rasa",
            "ranking": ranking,
            "raw": data,
        }
        logger.debug(
            "rasa_intent_prediction",
            intent=intent_name,
            confidence=confidence,
            margin=margin,
            ranking_count=len(ranking),
        )
        return prediction


__all__ = ["RasaIntentProvider"]
