from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Sequence

import structlog

from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.risk.repository import RiskDataRepository
from emergency_agents.risk.service import RiskCacheManager


@dataclass(slots=True)
class RiskPredictionResult:
    total_zones: int
    high_severity_zones: int
    hazard_types: List[str]
    refreshed_at: datetime


class RiskPredictor:
    """基于危险区域数据生成风险摘要，并可定时刷新。"""

    def __init__(
        self,
        repository: RiskDataRepository,
        cache_manager: RiskCacheManager,
        *,
        high_severity_threshold: int = 4,
    ) -> None:
        self._repository = repository
        self._cache_manager = cache_manager
        self._threshold = max(high_severity_threshold, 1)
        self._logger = structlog.get_logger(__name__)
        self._last_result: RiskPredictionResult | None = None

    @property
    def last_result(self) -> RiskPredictionResult | None:
        return self._last_result

    async def analyze(self) -> RiskPredictionResult:
        zones = await self._repository.list_active_zones()
        await self._cache_manager.refresh()
        high_risk = self._filter_high_severity(zones)
        hazard_types = sorted({zone.hazard_type for zone in zones})
        result = RiskPredictionResult(
            total_zones=len(zones),
            high_severity_zones=len(high_risk),
            hazard_types=hazard_types,
            refreshed_at=datetime.now(timezone.utc),
        )
        self._last_result = result
        self._logger.info(
            "risk_prediction_summary",
            total=len(zones),
            high_severity=len(high_risk),
            hazard_types=hazard_types,
        )
        return result

    async def run_periodic(self, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")
        self._logger.info("risk_predictor_started", interval_seconds=interval_seconds)
        try:
            while True:
                await self.analyze()
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            self._logger.info("risk_predictor_cancelled")
            raise

    def _filter_high_severity(self, zones: Sequence[RiskZoneRecord]) -> List[RiskZoneRecord]:
        return [zone for zone in zones if zone.severity >= self._threshold]
