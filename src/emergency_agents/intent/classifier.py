from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict

import structlog

from emergency_agents.config import AppConfig
from emergency_agents.intent.providers.base import IntentProvider, IntentThresholds
from emergency_agents.intent.providers.factory import build_providers
from emergency_agents.intent.providers.types import IntentPrediction

logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)


def _extract_text_from_state(state: Dict[str, Any]) -> str:
    """从状态中提取最新用户文本。"""
    raw_text = state.get("raw_text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text.strip()

    messages = state.get("messages") or []
    if isinstance(messages, list):
        for message in reversed(messages):
            role: str | None = None
            content: Any = None
            if isinstance(message, dict):
                role = str(message.get("role") or "").strip() or None
                content = message.get("content")
            else:
                content = getattr(message, "content", None)
                role_attr = getattr(message, "role", None)
                type_attr = getattr(message, "type", None)
                role_candidate = role_attr or type_attr
                if isinstance(role_candidate, str):
                    role = role_candidate.strip()
            if role == "user" and isinstance(content, str) and content.strip():
                return content.strip()

    raw_report = state.get("raw_report")
    if isinstance(raw_report, str) and raw_report.strip():
        return raw_report.strip()

    structured_logger.warning(
        "intent_text_missing",
        state_keys=list(state.keys()),
        message_count=len(messages) if isinstance(messages, list) else 0,
    )
    return ""


@dataclass
class IntentClassifierRuntime:
    """封装意图识别运行时依赖。"""

    provider: IntentProvider
    fallback: IntentProvider
    thresholds: IntentThresholds

    def classify_text(self, text: str) -> IntentPrediction:
        try:
            return self.provider.predict(text)
        except Exception as exc:  # pragma: no cover - 极端网络错误兜底
            structured_logger.warning(
                "intent_provider_error",
                provider=getattr(self.provider, "__class__", type(self.provider)).__name__,
                error=str(exc),
            )
            return self.fallback.predict(text)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        text = _extract_text_from_state(state)
        if not text:
            intent_stub = {
                "intent_type": "unknown",
                "slots": {},
                "meta": {"need_confirm": True, "confidence": 0.0, "margin": 0.0, "source": "unknown"},
            }
            return state | {"intent": intent_stub}

        prediction = self.classify_text(text)
        confidence = float(prediction.get("confidence", 0.0) or 0.0)
        margin = float(prediction.get("margin", 0.0) or 0.0)
        source = prediction.get("source", "unknown")
        need_confirm = bool(prediction.get("need_confirm", False))
        if confidence < self.thresholds.confidence or margin < self.thresholds.margin:
            need_confirm = True

        intent_raw = str(prediction.get("intent") or "unknown").strip() or "unknown"
        # 将意图名称统一为小写下划线，方便与内部枚举、schema 对齐
        intent_name = (
            intent_raw.lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        slots = prediction.get("slots") if isinstance(prediction.get("slots"), dict) else {}

        if intent_name in {"rescue_task_generate", "rescue-task-generate"} and isinstance(slots, dict):
            summary_value = slots.get("situation_summary")
            if isinstance(summary_value, str):
                summary_clean = summary_value.strip()
                if not summary_clean or summary_clean == text.strip() or len(summary_clean) < 25:
                    slots["situation_summary"] = ""
                    if isinstance(prediction.get("slots"), dict):
                        prediction["slots"]["situation_summary"] = ""

        intent_payload = {
            "intent_type": intent_name if not need_confirm else "unknown",
            "slots": slots,
            "meta": {
                "need_confirm": need_confirm,
                "confidence": confidence,
                "margin": margin,
                "source": source,
            },
        }
        structured_logger.info(
            "intent_classifier_prediction",
            raw_intent=intent_name,
            final_intent=intent_payload["intent_type"],
            confidence=confidence,
            margin=margin,
            need_confirm=need_confirm,
            ranking=prediction.get("ranking", []),
        )

        structured_logger.info(
            "intent_classified",
            intent=intent_payload["intent_type"],
            confidence=confidence,
            margin=margin,
            source=source,
        )
        return state | {"intent": intent_payload, "intent_prediction": dict(prediction)}


def build_intent_classifier_runtime(
    cfg: AppConfig,
    llm_client,
    llm_model: str,
    device_map_getter: Callable[[], Dict[str, str]] | None = None,
) -> IntentClassifierRuntime:
    """构建意图分类运行时

    Args:
        cfg: 应用配置
        llm_client: LLM客户端
        llm_model: LLM模型名称
        device_map_getter: 设备映射获取函数（可选），用于将设备名称解析为设备ID

    Returns:
        IntentClassifierRuntime实例
    """
    provider, fallback, thresholds = build_providers(cfg, llm_client, llm_model, device_map_getter)
    return IntentClassifierRuntime(provider=provider, fallback=fallback, thresholds=thresholds)


_default_runtime: IntentClassifierRuntime | None = None


def intent_classifier_node(
    state: Dict[str, Any],
    llm_client=None,
    llm_model: str | None = None,
    runtime: IntentClassifierRuntime | None = None,
    device_map_getter: Callable[[], Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """意图分类入口。runtime 明确传入时优先使用，否则使用全局默认。

    Args:
        state: LangGraph状态
        llm_client: LLM客户端（可选）
        llm_model: LLM模型名称（可选）
        runtime: 预先构建的runtime（可选）
        device_map_getter: 设备映射获取函数（可选）

    Returns:
        更新后的状态
    """
    global _default_runtime
    if runtime is not None:
        return runtime(state)

    if _default_runtime is None:
        if llm_client is None or llm_model is None:
            raise ValueError("intent_classifier_node requires runtime or (llm_client, llm_model)")
        cfg = AppConfig.load_from_env()
        _default_runtime = build_intent_classifier_runtime(cfg, llm_client, llm_model, device_map_getter)
    return _default_runtime(state)
