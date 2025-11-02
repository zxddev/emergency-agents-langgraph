from __future__ import annotations

from typing import Callable, Dict

import structlog

from emergency_agents.config import AppConfig
from emergency_agents.intent.providers.base import IntentProvider, IntentThresholds
from emergency_agents.intent.providers.llm import LLMIntentProvider
from emergency_agents.intent.providers.rasa import RasaIntentProvider
from emergency_agents.intent.providers.setfit import SetFitIntentProvider

logger = structlog.get_logger(__name__)


def build_providers(
    cfg: AppConfig,
    llm_client,
    llm_model: str,
    device_map_getter: Callable[[], Dict[str, str]] | None = None,
) -> tuple[IntentProvider, IntentProvider, IntentThresholds]:
    """根据配置构建主提供者、兜底提供者及阈值。

    Args:
        cfg: 应用配置
        llm_client: LLM客户端
        llm_model: LLM模型名称
        device_map_getter: 设备映射获取函数（可选），用于LLM provider将设备名称解析为设备ID

    Returns:
        (主提供者, 兜底提供者, 阈值配置)
    """
    thresholds = IntentThresholds(
        confidence=max(cfg.intent_confidence_threshold, 0.0),
        margin=max(cfg.intent_margin_threshold, 0.0),
    )

    fallback = LLMIntentProvider(
        llm_client=llm_client,
        model=llm_model,
        device_map_getter=device_map_getter,
    )

    provider_key = (cfg.intent_provider or "llm").strip().lower()
    logger.info("intent_provider_selected", provider=provider_key)

    if provider_key == "rasa":
        if not cfg.intent_rasa_url:
            raise ValueError("INTENT_RASA_URL 未配置")
        primary = RasaIntentProvider(cfg.intent_rasa_url, timeout=cfg.intent_provider_timeout)
    elif provider_key == "setfit":
        if not cfg.intent_setfit_url:
            raise ValueError("INTENT_SETFIT_URL 未配置")
        primary = SetFitIntentProvider(cfg.intent_setfit_url, timeout=cfg.intent_provider_timeout)
    elif provider_key == "llm":
        primary = fallback
    else:
        logger.warning("unknown_intent_provider", provider=provider_key)
        primary = fallback

    return primary, fallback, thresholds


__all__ = ["build_providers"]
