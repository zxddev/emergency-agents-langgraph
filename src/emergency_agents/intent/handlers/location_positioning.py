from __future__ import annotations

import logging

from typing_extensions import Protocol

from emergency_agents.db.dao import LocationDAO
from emergency_agents.db.models import EntityLocation, EventLocation, PoiLocation, QueryParams
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import LocationPositioningSlots
from emergency_agents.ui.actions import camera_fly_to, serialize_actions

logger = logging.getLogger(__name__)


class LocationRecord(Protocol):
    name: str
    lng: float
    lat: float


class LocationNotFoundError(RuntimeError):
    pass


class LocationPositioningHandler(IntentHandler[LocationPositioningSlots]):
    def __init__(self, location_dao: LocationDAO, amap_client: AmapClient) -> None:
        self.location_dao = location_dao
        self.amap_client = amap_client

    async def handle(self, slots: LocationPositioningSlots, state: dict[str, object]) -> dict[str, object]:
        user_id = state.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id required in state")

        logger.info(
            "intent_request",
            extra={
                "intent": "location-positioning",
                "thread_id": state.get("thread_id"),
                "user_id": user_id,
                "target": slots.target_type,
                "status": "processing",
            },
        )

        try:
            record = await self._resolve_location(slots)
        except LocationNotFoundError as exc:
            logger.warning("location_not_found", extra={"target_type": slots.target_type, "detail": str(exc)})
            return {"response_text": str(exc), "location": None}

        payload = {
            "type": f"locate_{slots.target_type}",
            "lng": record.lng,
            "lat": record.lat,
            "sourceIntent": "location-positioning",
            "displayName": record.name,
        }

        # 使用统一 UI Actions 协议通知前端移动视角
        ui_actions = serialize_actions([
            camera_fly_to(
                lng=record.lng,
                lat=record.lat,
                metadata={
                    "intent": "location-positioning",
                    "target_type": slots.target_type,
                    "user_id": user_id,
                }
            )
        ])
        logger.info(
            "location_positioning_ui_actions_emitted",
            extra={
                "intent": "location-positioning",
                "thread_id": state.get("thread_id"),
                "user_id": user_id,
                "count": len(ui_actions),
            },
        )

        message = f"已定位至 {record.name} ({record.lat:.4f}, {record.lng:.4f})"
        return {"response_text": message, "location": payload, "ui_actions": ui_actions}

    async def _resolve_location(self, slots: LocationPositioningSlots) -> LocationRecord:
        target = slots.target_type
        if target == "event":
            return await self._resolve_event(slots)
        if target == "team":
            return await self._resolve_team(slots)
        if target == "poi":
            return await self._resolve_poi(slots)
        raise LocationNotFoundError(f"不支持的定位目标类型: {target}")

    async def _resolve_event(self, slots: LocationPositioningSlots) -> EventLocation:
        params: QueryParams = {}
        if slots.event_id:
            params["event_id"] = slots.event_id
        if slots.event_code:
            params["event_code"] = slots.event_code
        if not params:
            raise LocationNotFoundError("缺少事件ID或编码")

        record = await self.location_dao.fetch_event_location(params)
        if record is None:
            raise LocationNotFoundError("未找到事件的定位信息")
        return record

    async def _resolve_team(self, slots: LocationPositioningSlots) -> EntityLocation:
        params: QueryParams = {}
        if slots.team_id:
            params["team_id"] = slots.team_id
        if slots.team_name:
            params["team_name"] = slots.team_name
        if not params:
            raise LocationNotFoundError("缺少救援队伍ID或名称")

        record = await self.location_dao.fetch_team_location(params)
        if record is None:
            raise LocationNotFoundError("未找到救援队伍位置")
        return record

    async def _resolve_poi(self, slots: LocationPositioningSlots) -> PoiLocation:
        if not slots.poi_name:
            raise LocationNotFoundError("缺少POI名称")

        record = await self.location_dao.fetch_poi_location({"poi_name": slots.poi_name})
        if record is not None:
            return record
        geocode = await self.amap_client.geocode(slots.poi_name)
        if geocode is None:
            raise LocationNotFoundError("POI 未找到，且高德地理编码失败")
        location = geocode["location"]
        return PoiLocation(name=geocode["name"], lng=location["lng"], lat=location["lat"])
