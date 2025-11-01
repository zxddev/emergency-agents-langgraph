from __future__ import annotations

import logging
from typing import Any, Optional

import pytest

pytest.importorskip("psycopg")

from emergency_agents.external.amap_client import AmapClient, GeocodeResult
from emergency_agents.db.models import EntityLocation, EventLocation, PoiLocation
from emergency_agents.intent.handlers.location_positioning import (
    LocationNotFoundError,
    LocationPositioningHandler,
)
from emergency_agents.intent.schemas import LocationPositioningSlots


class _FakeLocationDAO:
    def __init__(
        self,
        *,
        event: Optional[EventLocation] = None,
        team: Optional[EntityLocation] = None,
        poi: Optional[PoiLocation] = None,
    ) -> None:
        self._event = event
        self._team = team
        self._poi = poi

    async def fetch_event_location(self, params: dict[str, Any]) -> EventLocation | None:
        return self._event

    async def fetch_team_location(self, params: dict[str, Any]) -> EntityLocation | None:
        return self._team

    async def fetch_poi_location(self, params: dict[str, Any]) -> PoiLocation | None:
        return self._poi


class _DummyAmap(AmapClient):
    def __init__(self, result: GeocodeResult | None) -> None:
        self._result = result

    async def geocode(self, place: str) -> GeocodeResult | None:
        return self._result


@pytest.mark.asyncio
async def test_location_handler_event_from_database(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    dao = _FakeLocationDAO(
        event=EventLocation(name="映秀事件", lng=103.85, lat=31.68),
    )
    handler = LocationPositioningHandler(
        location_dao=dao,
        amap_client=_DummyAmap(None),
    )
    slots = LocationPositioningSlots(target_type="event", event_code="EQ-DEBUG-FIXED")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert "映秀事件" in result["response_text"]
    assert result["location"]["type"] == "locate_event"
    assert any("location_positioning_todo_notify" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_location_handler_team_missing() -> None:
    dao = _FakeLocationDAO(team=None)
    handler = LocationPositioningHandler(
        location_dao=dao,
        amap_client=_DummyAmap(None),
    )
    slots = LocationPositioningSlots(target_type="team")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert result["location"] is None
    assert "缺少救援队伍ID" in result["response_text"]


@pytest.mark.asyncio
async def test_location_handler_poi_fallback_amap(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    amap_result: GeocodeResult = {
        "name": "高德映秀中学",
        "location": {"lng": 103.851, "lat": 31.681},
        "level": "poi",
    }
    handler = LocationPositioningHandler(
        location_dao=_FakeLocationDAO(poi=None),
        amap_client=_DummyAmap(amap_result),
    )
    slots = LocationPositioningSlots(target_type="poi", poi_name="映秀中学")
    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert "高德映秀中学" in result["response_text"]
    assert result["location"]["type"] == "locate_poi"
    assert any("location_positioning_todo_notify" in record.message for record in caplog.records)
