import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Sequence

import pytest

from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.risk.service import RiskCacheManager


class StubIncidentDAO:
    def __init__(self, responses: Sequence[List[RiskZoneRecord]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def list_active_risk_zones(self, *, reference_time=None):
        index = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        return list(self._responses[index])


def _build_zone(zone_id: str, severity: int) -> RiskZoneRecord:
    now = datetime.now(timezone.utc)
    return RiskZoneRecord(
        zone_id=zone_id,
        zone_name=f"zone-{zone_id}",
        hazard_type="flood",
        severity=severity,
        description=None,
        geometry_geojson={"type": "Polygon", "coordinates": []},
        properties={},
        valid_from=now,
        valid_until=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_prefetch_and_get_returns_cached_data() -> None:
    zones = [_build_zone("a", 3)]
    dao = StubIncidentDAO([zones])
    cache = RiskCacheManager(incident_dao=dao, ttl_seconds=60.0)

    await cache.prefetch()
    assert dao.calls == 1

    cached = await cache.get_active_zones()
    assert cached == zones
    assert dao.calls == 1  # 未过期，不应重复查询


@pytest.mark.asyncio
async def test_get_triggers_refresh_after_ttl() -> None:
    first = [_build_zone("a", 2)]
    second = [_build_zone("b", 4)]
    dao = StubIncidentDAO([first, second])
    cache = RiskCacheManager(incident_dao=dao, ttl_seconds=0.05)

    await cache.prefetch()
    assert await cache.get_active_zones() == first
    await asyncio.sleep(0.06)
    zones_after = await cache.get_active_zones()
    assert zones_after == second
    assert dao.calls >= 2


@pytest.mark.asyncio
async def test_force_refresh_ignores_cache() -> None:
    first = [_build_zone("a", 1)]
    second = [_build_zone("b", 5)]
    dao = StubIncidentDAO([first, second])
    cache = RiskCacheManager(incident_dao=dao, ttl_seconds=60.0)

    await cache.prefetch()
    zones_before = await cache.get_active_zones()
    assert zones_before == first

    zones_after = await cache.get_active_zones(force_refresh=True)
    assert zones_after == second
    assert dao.calls == 2
