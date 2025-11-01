from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.risk.predictor import RiskPredictor
from emergency_agents.risk.repository import RiskDataRepository


class _StubIncidentDAO:
    def __init__(self, zones: List[RiskZoneRecord]) -> None:
        self._zones = zones
        self.calls = 0

    async def list_active_risk_zones(self) -> List[RiskZoneRecord]:
        self.calls += 1
        return list(self._zones)


class _StubRiskCacheManager:
    def __init__(self) -> None:
        self.refresh_calls = 0

    async def refresh(self) -> None:
        self.refresh_calls += 1


@pytest.mark.anyio
async def test_risk_predictor_analyze() -> None:
    now = datetime.now(timezone.utc)
    zones = [
        RiskZoneRecord(
            zone_id="z1",
            zone_name="危险区1",
            hazard_type="landslide",
            severity=4,
            description="高风险",
            geometry_geojson={"type": "Point", "coordinates": [120.0, 30.0]},
            properties={},
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=1),
            created_at=now - timedelta(hours=1),
            updated_at=now,
        ),
        RiskZoneRecord(
            zone_id="z2",
            zone_name="危险区2",
            hazard_type="flood",
            severity=2,
            description="中风险",
            geometry_geojson={"type": "Point", "coordinates": [120.1, 30.1]},
            properties={},
            valid_from=now - timedelta(hours=2),
            valid_until=now + timedelta(hours=3),
            created_at=now - timedelta(hours=2),
            updated_at=now,
        ),
    ]
    incident_dao = _StubIncidentDAO(zones)
    repository = RiskDataRepository(incident_dao)  # type: ignore[arg-type]
    cache_manager = _StubRiskCacheManager()
    predictor = RiskPredictor(repository, cache_manager, high_severity_threshold=3)
    result = await predictor.analyze()
    assert result.total_zones == 2
    assert result.high_severity_zones == 1
    assert sorted(result.hazard_types) == ["flood", "landslide"]
    assert cache_manager.refresh_calls == 1
