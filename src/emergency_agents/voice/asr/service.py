# Copyright 2025 msq
from __future__ import annotations

import structlog

from .base import ASRConfig, ASRResult
from .manager import ASRManager

logger = structlog.get_logger(__name__)


class ASRService:
    def __init__(self) -> None:
        self._manager = ASRManager()
        logger.info("asr_service_created")

    @property
    def provider_name(self) -> str:
        primary = self._manager._ENV_PRIMARY
        return f"{primary}(primary)" if primary in self._manager._providers else "unknown"

    async def recognize(self, audio_data: bytes, config: ASRConfig | None = None) -> ASRResult:
        return await self._manager.recognize(audio_data, config)

    async def start_health_check(self) -> None:
        await self._manager.start_health_check()

    async def stop_health_check(self) -> None:
        await self._manager.stop_health_check()

    @property
    def provider_status(self) -> dict[str, bool]:
        return self._manager.provider_status


