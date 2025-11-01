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
