from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import pytest

from emergency_agents.db.dao import RescueDAO, RescueTaskRepository
from emergency_agents.db.models import (
    RescuerRecord,
    TaskCreateInput,
    TaskRecord,
    TaskRoutePlanCreateInput,
    TaskRoutePlanRecord,
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

    async def fetchall(self) -> list[Any]:
        return list(self._rows)

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None


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
async def test_rescue_dao_list_available_rescuers() -> None:
    record = RescuerRecord(
        rescuer_id="rescuer-1",
        name="消防车A1",
        rescuer_type="firefighter",
        status="available",
        availability=True,
        lng=120.123,
        lat=30.456,
        skills=["firefighting", "rescue"],
        equipment={"vehicle": "fire_truck"},
    )
    cursor = _FakeCursor([record])
    dao = RescueDAO(_FakePool(cursor))  # type: ignore[arg-type]

    results = await dao.list_available_rescuers(limit=10)

    assert len(results) == 1
    item = results[0]
    assert item.rescuer_id == "rescuer-1"
    assert item.skills == ["firefighting", "rescue"]
    assert item.equipment == {"vehicle": "fire_truck"}
    assert cursor.params == {"limit": 10}
    assert "FROM operational.rescuers" in (cursor.sql or "")


@pytest.mark.asyncio
async def test_rescue_task_repository_create_task() -> None:
    now = datetime.now(timezone.utc)
    task_record = TaskRecord(
        id="task-1",
        task_type="rescue_target",
        status="pending",
        priority=70,
        description="调派消防车A1",
        deadline=None,
        progress=0,
        event_id="event-1",
        code="TASK-001",
        created_at=now,
        updated_at=now,
    )
    cursor = _FakeCursor([task_record])
    repo = RescueTaskRepository(_FakePool(cursor))  # type: ignore[arg-type]

    payload = TaskCreateInput(
        task_type="rescue_target",
        status="pending",
        priority=70,
        description="调派消防车A1",
        deadline=None,
        target_entity_id=None,
        event_id="event-1",
        created_by="commander",
        updated_by="commander",
        code="TASK-001",
    )

    record = await repo.create_task(payload)

    assert record.id == "task-1"
    assert cursor.params is not None
    assert cursor.params["type"] == "rescue_target"
    assert cursor.params["created_by"] == "commander"


@pytest.mark.asyncio
async def test_rescue_task_repository_create_route_plan() -> None:
    now = datetime.now(timezone.utc)
    route_record = TaskRoutePlanRecord(
        id="route-1",
        task_id="task-1",
        status="USED",
        strategy="FASTEST",
        origin_geojson={"type": "Point", "coordinates": [120.0, 30.0]},
        destination_geojson={"type": "Point", "coordinates": [120.2, 30.2]},
        polyline_geojson=None,
        distance_meters=1200.0,
        duration_seconds=600,
        estimated_arrival_time=now + timedelta(seconds=600),
        avoid_polygons=None,
        created_at=now,
        updated_at=now,
    )
    cursor = _FakeCursor([route_record])
    repo = RescueTaskRepository(_FakePool(cursor))  # type: ignore[arg-type]

    payload = TaskRoutePlanCreateInput(
        task_id="task-1",
        status="USED",
        strategy="FASTEST",
        origin_geojson={"type": "Point", "coordinates": [120.0, 30.0]},
        destination_geojson={"type": "Point", "coordinates": [120.2, 30.2]},
        polyline_geojson=None,
        distance_meters=1200.0,
        duration_seconds=600,
        estimated_arrival_time=now + timedelta(seconds=600),
        avoid_polygons=None,
    )

    record = await repo.create_route_plan(payload)

    assert record.id == "route-1"
    assert cursor.params is not None
    assert cursor.params["task_id"] == "task-1"
    assert cursor.params["status"] == "USED"
