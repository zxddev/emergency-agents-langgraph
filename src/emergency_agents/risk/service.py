from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Sequence

import structlog

from emergency_agents.db.dao import IncidentDAO
from emergency_agents.db.models import RiskZoneRecord


@dataclass(slots=True)
class RiskCacheState:
    """缓存状态，用于记录最近一次刷新结果。"""

    zones: List[RiskZoneRecord]
    refreshed_at: datetime


class RiskCacheManager:
    """负责拉取并缓存危险区域，供多个子图复用。"""

    def __init__(
        self,
        incident_dao: IncidentDAO,
        *,
        ttl_seconds: float,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0")
        self._incident_dao = incident_dao
        self._ttl = timedelta(seconds=ttl_seconds)
        self._state: RiskCacheState | None = None
        self._lock = asyncio.Lock()
        self._logger = structlog.get_logger(__name__)

    async def prefetch(self) -> None:
        """首次预热缓存。"""
        async with self._lock:
            await self._refresh_locked()

    async def get_active_zones(self, *, force_refresh: bool = False) -> List[RiskZoneRecord]:
        """返回当前有效危险区域，必要时自动刷新。"""
        state = self._state
        if not force_refresh and state is not None and not self._is_expired(state.refreshed_at):
            return list(state.zones)
        async with self._lock:
            if not force_refresh:
                state = self._state
                if state is not None and not self._is_expired(state.refreshed_at):
                    return list(state.zones)
            await self._refresh_locked()
            assert self._state is not None
            return list(self._state.zones)

    async def refresh(self) -> None:
        """主动刷新缓存。"""
        async with self._lock:
            await self._refresh_locked()

    async def periodic_refresh(self, interval_seconds: float) -> None:
        """循环刷新任务，可在 FastAPI 启动时调度。"""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")
        self._logger.info("risk_cache_periodic_refresh_started", interval_seconds=interval_seconds)
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                await self.refresh()
        except asyncio.CancelledError:
            self._logger.info("risk_cache_periodic_refresh_cancelled")
            raise

    def snapshot(self) -> RiskCacheState | None:
        """返回当前缓存的快照，不触发刷新。"""
        state = self._state
        if state is None:
            return None
        return RiskCacheState(list(state.zones), state.refreshed_at)

    def _is_expired(self, refreshed_at: datetime) -> bool:
        return datetime.now(timezone.utc) - refreshed_at >= self._ttl

    async def _refresh_locked(self) -> None:
        zones: Sequence[RiskZoneRecord] = await self._incident_dao.list_active_risk_zones()
        refreshed_at = datetime.now(timezone.utc)
        # list() 复制，避免调用者修改内部状态
        cache_state = RiskCacheState(list(zones), refreshed_at)
        self._state = cache_state
        self._logger.info(
            "risk_cache_refreshed",
            zone_count=len(zones),
            refreshed_at=refreshed_at.isoformat(),
        )
