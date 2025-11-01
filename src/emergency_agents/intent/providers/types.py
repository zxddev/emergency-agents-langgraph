from __future__ import annotations

from typing import Any, TypedDict


class IntentCandidate(TypedDict, total=False):
    """意图候选项结构。"""

    intent: str
    confidence: float


class IntentPrediction(TypedDict, total=False):
    """意图识别结果结构，供运行时与上层图谱使用。"""

    intent: str
    confidence: float
    margin: float
    slots: dict[str, Any]
    need_confirm: bool
    source: str
    ranking: list[IntentCandidate]
    raw: dict[str, Any]


__all__ = ["IntentCandidate", "IntentPrediction"]
