from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import pytest

from emergency_agents.db.dao import IncidentDAO, IncidentSnapshotRepository
from emergency_agents.db.models import (
    IncidentEntityDetail,
    IncidentEntityLink,
    IncidentRecord,
    IncidentSnapshotCreateInput,
    IncidentSnapshotRecord,
    RiskZoneRecord,
)


class _FakeCursor:
    def __init__(self, rows: Iterable[Any]) -> None:
        self._rows = list(rows)
        self.sql: Optional[str] = None
        self.params: Optional[dict[str, Any]] = None

    async def __aenter__(self) -> "_FakeCursor":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, sql: str, params: dict[str, Any]) -> None:
        self.sql = sql
        self.params = params

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> "_FakeConnection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self, *args: Any, **kwargs: Any) -> _FakeCursor:
        return self._cursor


class _FakePool:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def connection(self) -> _FakeConnection:
        return _FakeConnection(self._cursor)


@pytest.mark.asyncio
async def test_incident_dao_fetch_incident() -> None:
    now = datetime.now(timezone.utc)
    record = IncidentRecord(
        id="incident-1",
        parent_event_id=None,
        event_code="INC-001",
        title="演练事件",
        type="people_trapped",
        priority=80,
        status="active",
        description="示例事件",
        created_by="system",
        updated_by="system",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    cursor = _FakeCursor([record])
    dao = IncidentDAO(_FakePool(cursor))  # type: ignore[arg-type]

    result = await dao.fetch_incident(incident_id="incident-1")

    assert result is not None
    assert result.id == "incident-1"
    assert cursor.params == {"incident_id": "incident-1"}
    assert "FROM operational.events" in (cursor.sql or "")


@pytest.mark.asyncio
async def test_incident_dao_list_entities_with_details() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "incident_id": "incident-1",
        "entity_id": "entity-1",
        "relation_type": "primary",
        "description": "核心目标",
        "display_priority": 100,
        "linked_at": now,
        "ent_id": "entity-1",
        "ent_type": "rescue_target",
        "geometry_geojson": {"type": "Point", "coordinates": [120.0, 30.0]},
        "properties": {"name": "被困人员"},
        "layer_code": "layer.dispose",
        "display_name": None,
        "created_by": "system",
        "updated_by": "system",
        "ent_created_at": now,
        "ent_updated_at": now,
    }
    cursor = _FakeCursor([row])
    dao = IncidentDAO(_FakePool(cursor))  # type: ignore[arg-type]

    items = await dao.list_entities_with_details("incident-1")

    assert len(items) == 1
    detail = items[0]
    assert isinstance(detail, IncidentEntityDetail)
    assert isinstance(detail.link, IncidentEntityLink)
    assert detail.link.relation_type == "primary"
    assert detail.entity.display_name == "被困人员"
    assert detail.entity.geometry_geojson["type"] == "Point"


@pytest.mark.asyncio
async def test_incident_dao_list_active_risk_zones() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "zone_id": "zone-1",
        "zone_name": "风险区A",
        "hazard_type": "landslide",
        "severity": 7,
        "description": "山体滑坡隐患",
        "geometry_geojson": {"type": "Polygon", "coordinates": []},
        "properties": {"source": "sensor"},
        "valid_from": now,
        "valid_until": None,
        "created_at": now,
        "updated_at": now,
    }
    cursor = _FakeCursor([row])
    dao = IncidentDAO(_FakePool(cursor))  # type: ignore[arg-type]

    zones = await dao.list_active_risk_zones()

    assert len(zones) == 1
    zone = zones[0]
    assert isinstance(zone, RiskZoneRecord)
    assert zone.zone_name == "风险区A"
    assert zone.properties["source"] == "sensor"


@pytest.mark.asyncio
async def test_incident_snapshot_repository_create_and_list() -> None:
    now = datetime.now(timezone.utc)
    record = IncidentSnapshotRecord(
        snapshot_id="snap-1",
        incident_id="incident-1",
        snapshot_type="tactical_overview",
        payload={"summary": "当前态势稳定"},
        generated_at=now,
        created_by="ai-agent",
        created_at=now,
    )
    create_cursor = _FakeCursor([record])
    repo = IncidentSnapshotRepository(_FakePool(create_cursor))  # type: ignore[arg-type]

    payload = IncidentSnapshotCreateInput(
        incident_id="incident-1",
        snapshot_type="tactical_overview",
        payload={"summary": "当前态势稳定"},
        generated_at=now,
        created_by="ai-agent",
    )

    created = await repo.create_snapshot(payload)

    assert created.snapshot_id == "snap-1"
    assert create_cursor.params is not None
    assert create_cursor.params["payload"] == {"summary": "当前态势稳定"}

    list_cursor = _FakeCursor([record])
    list_repo = IncidentSnapshotRepository(_FakePool(list_cursor))  # type: ignore[arg-type]
    results = await list_repo.list_snapshots("incident-1", snapshot_type="tactical_overview", limit=5)

    assert len(results) == 1
    assert results[0].snapshot_type == "tactical_overview"
    assert list_cursor.params == {
        "incident_id": "incident-1",
        "snapshot_type": "tactical_overview",
        "limit": 5,
    }
