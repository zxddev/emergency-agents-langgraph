from __future__ import annotations

from typing import Sequence

from emergency_agents.db.dao import IncidentDAO
from emergency_agents.db.models import RiskZoneRecord


class RiskDataRepository:
    """封装危险区域查询，便于预测器与缓存共用。"""

    def __init__(self, incident_dao: IncidentDAO) -> None:
        self._incident_dao = incident_dao

    async def list_active_zones(self) -> list[RiskZoneRecord]:
        zones: Sequence[RiskZoneRecord] = await self._incident_dao.list_active_risk_zones()
        return list(zones)

    async def find_zones_near(self, *, lng: float, lat: float, radius_meters: float) -> list[RiskZoneRecord]:
        """查询指定坐标附近的活跃风险区域（用于risk_overlay_task）"""
        zones: list[RiskZoneRecord] = await self._incident_dao.find_zones_near(
            lng=lng,
            lat=lat,
            radius_meters=radius_meters,
        )
        return zones
