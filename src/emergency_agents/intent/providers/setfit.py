from __future__ import annotations

from typing import Any, Dict, List

import structlog

from emergency_agents.intent.providers.http import HttpIntentProvider
from emergency_agents.intent.providers.types import IntentPrediction

logger = structlog.get_logger(__name__)


class SetFitIntentProvider(HttpIntentProvider):
    """调用SetFit微服务完成意图识别。"""

    def __init__(self, base_url: str, timeout: float) -> None:
        super().__init__("setfit", base_url=base_url, timeout=timeout)

    def _request(self, text: str) -> Dict[str, Any]:
        """发送预测请求并返回字典。"""
        response = self.client.post("/predict", json={"text": text})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("SetFit返回结构异常")
        return data

    @staticmethod
    def _normalize_ranking(raw: Any) -> List[Dict[str, Any]]:
        """整理概率分布信息。"""
        if isinstance(raw, list):
            ranking: List[Dict[str, Any]] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("intent")
                if not isinstance(name, str) or not name:
                    continue
                ranking.append(
                    {
                        "intent": name,
                        "confidence": float(item.get("confidence") or item.get("proba") or 0.0),
                    }
                )
            return ranking
        return []

    def predict(self, text: str) -> IntentPrediction:
        """执行SetFit预测并转换为统一结构。"""
        if not text or not text.strip():
            raise ValueError("意图识别文本为空")

        data = self._request(text)
        intent_name = str(data.get("intent") or "unknown").strip() or "unknown"
        confidence = float(data.get("proba") or data.get("confidence") or 0.0)
        margin = float(data.get("margin") or 0.0)
        ranking = self._normalize_ranking(data.get("ranking"))
        if margin == 0.0 and len(ranking) >= 2:
            margin = ranking[0]["confidence"] - ranking[1]["confidence"]
        margin = max(margin, 0.0)

        prediction: IntentPrediction = {
            "intent": intent_name,
            "confidence": confidence,
            "margin": margin,
            "slots": {},
            "need_confirm": bool(data.get("need_confirm") or False),
            "source": "setfit",
            "ranking": ranking,
            "raw": data,
        }
        logger.debug(
            "setfit_intent_prediction",
            intent=intent_name,
            confidence=confidence,
            margin=margin,
        )
        return prediction


__all__ = ["SetFitIntentProvider"]
