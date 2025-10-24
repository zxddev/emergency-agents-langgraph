# Copyright 2025 msq
from __future__ import annotations

"""ASR 服务门面（单提供方策略，无降级）。

当前项目需求：严格按环境变量选择一个提供方使用，不实现任何自动切换或降级。
"""

import os
from typing import Final

import structlog

from .base import ASRConfig, ASRProvider, ASRResult
from .aliyun_provider import AliyunASRProvider
from .local_provider import LocalFunASRProvider

logger = structlog.get_logger(__name__)


class ASRService:
    """ASR 服务门面（单一提供方）。

    通过 `ASR_PROVIDER` 环境变量选择提供方：`aliyun` 或 `local`。
    不实现任何降级，若所选提供方不可用则抛出异常。
    """

    _ENV_PROVIDER: Final[str] = os.getenv("ASR_PROVIDER", "aliyun")

    def __init__(self) -> None:
        self._provider: ASRProvider | None = None
        self._provider_key = self._ENV_PROVIDER.strip().lower()
        logger.info("asr_service_created", provider=self._provider_key)

    @property
    def provider_name(self) -> str:
        """返回当前选择的提供方名称。"""
        prov = self._ensure_provider()
        return prov.name

    async def recognize(self, audio_data: bytes, config: ASRConfig | None = None) -> ASRResult:
        """执行语音识别（严格使用指定提供方）。

        Args:
            audio_data: 原始音频二进制。
            config: 识别配置。

        Returns:
            ASRResult: 识别结果。
        """

        prov = self._ensure_provider()
        return await prov.recognize(audio_data, config)

    async def health_check(self) -> bool:
        """检查所选提供方健康状态。"""

        prov = self._ensure_provider()
        return await prov.health_check()

    def _ensure_provider(self) -> ASRProvider:
        """惰性初始化提供方，避免在启动阶段因缺少环境而失败。

        Returns:
            ASRProvider: 已初始化的提供方实例。

        Raises:
            ValueError: 环境变量配置不正确或依赖缺失时抛出。
        """

        if self._provider is not None:
            return self._provider
        if self._provider_key == "aliyun":
            self._provider = AliyunASRProvider()
        elif self._provider_key == "local":
            self._provider = LocalFunASRProvider()
        else:
            raise ValueError("ASR_PROVIDER must be 'aliyun' or 'local'")
        logger.info("asr_provider_initialized", provider=self._provider.name)
        return self._provider


