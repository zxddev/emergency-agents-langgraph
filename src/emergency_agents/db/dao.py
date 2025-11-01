from __future__ import annotations

import time
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

import structlog
from prometheus_client import Counter, Histogram

from psycopg.rows import class_row, dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from typing_extensions import Self

from emergency_agents.db.models import (
    DeviceSummary,
    EntityLocation,
    EntityRecord,
    EventLocation,
    IncidentEntityCreateInput,
    IncidentEntityDetail,
    IncidentEntityLink,
    IncidentRecord,
    IncidentSnapshotCreateInput,
    IncidentSnapshotRecord,
    PoiLocation,
    QueryParams,
    RescuerRecord,
    RiskZoneRecord,
    TaskCreateInput,
    TaskLogEntry,
    TaskRecord,
    TaskRoutePlan,
    TaskRoutePlanCreateInput,
    TaskRoutePlanRecord,
    TaskSummary,
    VideoDevice,
)

logger = structlog.get_logger(__name__)

DAO_CALL_TOTAL = Counter("dao_call_total", "DAO 调用次数", ["dao", "method", "result"])
DAO_CALL_LATENCY = Histogram("dao_call_duration_seconds", "DAO 调用耗时（秒）", ["dao", "method"])


class LocationDAO:
    """提供事件、队伍、POI 的定位查询。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> Self:
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def fetch_event_location(self, params: QueryParams) -> EventLocation | None:
        start = time.perf_counter()
        conditions: list[str] = []
        sql_params: dict[str, Any] = {}
        event_id = params.get("event_id")
        event_code = params.get("event_code")
        if event_id:
            conditions.append("e.id = %(event_id)s::uuid")
            sql_params["event_id"] = event_id
        if event_code:
            conditions.append("e.event_code = %(event_code)s")
            sql_params["event_code"] = event_code
        if not conditions:
            raise ValueError("缺少事件定位参数（event_id / event_code）")

        query = (
            "SELECT e.title AS name, "
            "       ST_X((ent.geometry)::geometry) AS lng, "
            "       ST_Y((ent.geometry)::geometry) AS lat "
            "  FROM operational.events e "
            "  LEFT JOIN operational.event_entities ee ON ee.event_id = e.id "
            "  LEFT JOIN operational.entities ent ON ent.id = ee.entity_id "
            f" WHERE {' OR '.join(conditions)} "
            " ORDER BY ee.display_priority DESC NULLS LAST, e.updated_at DESC "
            " LIMIT 1"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(EventLocation)) as cur:
                await cur.execute(query, sql_params)
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("location", "fetch_event").observe(duration)
        DAO_CALL_TOTAL.labels("location", "fetch_event", "found" if record else "not_found").inc()
        logger.info(
            "dao_location_fetch_event",
            duration_ms=duration * 1000,
            has_event_id=bool(event_id),
            has_event_code=bool(event_code),
            found=record is not None,
        )
        return record

    async def fetch_team_location(self, params: QueryParams) -> EntityLocation | None:
        start = time.perf_counter()
        conditions: list[str] = ["ent.type = 'rescue_team'"]
        sql_params: dict[str, Any] = {}
        team_id = params.get("team_id")
        team_name = params.get("team_name")
        if team_id:
            conditions.append("ent.id = %(team_id)s::uuid")
            sql_params["team_id"] = team_id
        if team_name:
            conditions.append("ent.properties->>'name' ILIKE %(team_name)s")
            sql_params["team_name"] = f"%{team_name}%"
        if len(conditions) == 1:
            raise ValueError("缺少救援队伍参数（team_id / team_name）")

        query = (
            "SELECT ent.properties->>'name' AS name, "
            "       ST_X((ent.geometry)::geometry) AS lng, "
            "       ST_Y((ent.geometry)::geometry) AS lat "
            "  FROM operational.entities ent "
            f" WHERE {' AND '.join(conditions)} "
            " ORDER BY ent.updated_at DESC "
            " LIMIT 1"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(EntityLocation)) as cur:
                await cur.execute(query, sql_params)
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("location", "fetch_team").observe(duration)
        DAO_CALL_TOTAL.labels("location", "fetch_team", "found" if record else "not_found").inc()
        logger.info(
            "dao_location_fetch_team",
            duration_ms=duration * 1000,
            has_team_id=bool(team_id),
            has_team_name=bool(team_name),
            found=record is not None,
        )
        return record

    async def fetch_poi_location(self, params: QueryParams) -> PoiLocation | None:
        poi_name = params.get("poi_name")
        if not poi_name:
            raise ValueError("缺少 POI 名称参数")
        start = time.perf_counter()

        pattern = poi_name if "%" in poi_name else f"%{poi_name}%"
        query = (
            "SELECT name, "
            "       ST_X(geom::geometry) AS lng, "
            "       ST_Y(geom::geometry) AS lat "
            "  FROM operational.poi_points "
            " WHERE name ILIKE %(name)s "
            " ORDER BY updated_at DESC "
            " LIMIT 1"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(PoiLocation)) as cur:
                await cur.execute(query, {"name": pattern})
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("location", "fetch_poi").observe(duration)
        DAO_CALL_TOTAL.labels("location", "fetch_poi", "found" if record else "not_found").inc()
        logger.info(
            "dao_location_fetch_poi",
            duration_ms=duration * 1000,
            name=poi_name,
            pattern=pattern,
            found=record is not None,
        )
        return record


class DeviceDAO:
    """设备层查询。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> Self:
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def fetch_device(self, device_id: str) -> DeviceSummary | None:
        start = time.perf_counter()
        query = (
            "SELECT id::text AS id, device_type, name "
            "  FROM operational.device "
            " WHERE id = %(device_id)s OR id = %(device_id)s::uuid"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(DeviceSummary)) as cur:
                await cur.execute(query, {"device_id": device_id})
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("device", "fetch_device").observe(duration)
        DAO_CALL_TOTAL.labels("device", "fetch_device", "found" if record else "not_found").inc()
        logger.info(
            "dao_device_fetch",
            duration_ms=duration * 1000,
            device_id=device_id,
            found=record is not None,
        )
        return record

    async def fetch_video_device(self, device_id: str) -> VideoDevice | None:
        start = time.perf_counter()
        query = """
            SELECT d.id::text AS id,
                   d.device_type,
                   d.name,
                   dd.device_detail->>'stream_url' AS stream_url
              FROM operational.device d
              LEFT JOIN operational.device_detail dd
                     ON dd.device_id = d.id
             WHERE d.id = %(device_id)s
        """
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(VideoDevice)) as cur:
                await cur.execute(query, {"device_id": device_id})
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("device", "fetch_video").observe(duration)
        DAO_CALL_TOTAL.labels("device", "fetch_video", "found" if record else "not_found").inc()
        logger.info(
            "dao_device_fetch_video",
            duration_ms=duration * 1000,
            device_id=device_id,
            has_stream=bool(record and record.stream_url),
        )
        return record


class TaskDAO:
    """任务查询接口。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> Self:
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def fetch_task(self, params: QueryParams) -> TaskSummary | None:
        start = time.perf_counter()
        conditions: list[str] = []
        sql_params: dict[str, Any] = {}
        task_id = params.get("task_id")
        task_code = params.get("task_code")
        if task_id:
            conditions.append("id = %(task_id)s::uuid")
            sql_params["task_id"] = task_id
        if task_code:
            conditions.append("code = %(task_code)s")
            sql_params["task_code"] = task_code
        if not conditions:
            raise ValueError("task 查询必须提供 task_id 或 task_code")

        query = (
            "SELECT id::text AS id, code, description, status, progress, updated_at "
            "  FROM operational.tasks "
            f" WHERE {' OR '.join(conditions)} "
            " ORDER BY updated_at DESC "
            " LIMIT 1"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(TaskSummary)) as cur:
                await cur.execute(query, sql_params)
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("task", "fetch_task").observe(duration)
        DAO_CALL_TOTAL.labels("task", "fetch_task", "found" if record else "not_found").inc()
        logger.info(
            "dao_task_fetch",
            duration_ms=duration * 1000,
            has_task_id=bool(task_id),
            has_task_code=bool(task_code),
            found=record is not None,
        )
        return record

    async def fetch_latest_log(self, task_id: str) -> TaskLogEntry | None:
        start = time.perf_counter()
        query = (
            "SELECT description, timestamp, recorder_name "
            "  FROM operational.task_log "
            " WHERE task_id = %(task_id)s "
            "    OR task_id = %(task_id)s::uuid::text "
            " ORDER BY timestamp DESC NULLS LAST "
            " LIMIT 1"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(TaskLogEntry)) as cur:
                await cur.execute(query, {"task_id": task_id})
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("task", "fetch_latest_log").observe(duration)
        DAO_CALL_TOTAL.labels("task", "fetch_latest_log", "found" if record else "not_found").inc()
        logger.info(
            "dao_task_fetch_latest_log",
            duration_ms=duration * 1000,
            task_id=task_id,
            found=record is not None,
        )
        return record

    async def fetch_routes(self, task_id: str) -> list[TaskRoutePlan]:
        start = time.perf_counter()
        query = (
            "SELECT strategy, distance_meters, duration_seconds "
            "  FROM operational.task_route_plans "
            " WHERE task_id = %(task_id)s::uuid "
            " ORDER BY created_at DESC"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(TaskRoutePlan)) as cur:
                await cur.execute(query, {"task_id": task_id})
                rows = await cur.fetchall()
                result = list(rows)

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("task", "fetch_routes").observe(duration)
        DAO_CALL_TOTAL.labels("task", "fetch_routes", "success").inc()
        logger.info(
            "dao_task_fetch_routes",
            duration_ms=duration * 1000,
            task_id=task_id,
            route_count=len(result),
        )
        return result


class IncidentDAO:
    """事件（Incident）相关只读接口。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> "IncidentDAO":
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def fetch_incident(self, *, incident_id: str | None = None, event_code: str | None = None) -> IncidentRecord | None:
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if incident_id:
            conditions.append("id = %(incident_id)s::uuid")
            params["incident_id"] = incident_id
        if event_code:
            conditions.append("event_code = %(event_code)s")
            params["event_code"] = event_code
        if not conditions:
            raise ValueError("必须提供 incident_id 或 event_code")

        query = (
            "SELECT id::text AS id, "
            "       parent_event_id::text AS parent_event_id, "
            "       event_code, "
            "       title, "
            "       type::text AS type, "
            "       priority, "
            "       status::text AS status, "
            "       description, "
            "       created_by, "
            "       updated_by, "
            "       created_at, "
            "       updated_at, "
            "       deleted_at "
            "  FROM operational.events "
            f" WHERE {' OR '.join(conditions)} "
            " ORDER BY updated_at DESC "
            " LIMIT 1"
        )

        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(IncidentRecord)) as cur:
                await cur.execute(query, params)
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident", "fetch_incident").observe(duration)
        DAO_CALL_TOTAL.labels("incident", "fetch_incident", "found" if record else "not_found").inc()
        logger.info(
            "dao_incident_fetch",
            duration_ms=duration * 1000,
            has_incident_id=bool(incident_id),
            has_event_code=bool(event_code),
            found=record is not None,
        )
        return record

    async def list_entity_links(self, incident_id: str) -> list[IncidentEntityLink]:
        query = (
            "SELECT event_id::text AS incident_id, "
            "       entity_id::text AS entity_id, "
            "       relation_type, "
            "       description AS notes, "
            "       display_priority, "
            "       created_at AS linked_at "
            "  FROM operational.event_entities "
            " WHERE event_id = %(incident_id)s::uuid "
            " ORDER BY display_priority DESC NULLS LAST, created_at DESC"
        )
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(IncidentEntityLink)) as cur:
                await cur.execute(query, {"incident_id": incident_id})
                rows = await cur.fetchall()
                result = list(rows)

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident", "list_entity_links").observe(duration)
        DAO_CALL_TOTAL.labels("incident", "list_entity_links", "success").inc()
        logger.info(
            "dao_incident_list_entity_links",
            duration_ms=duration * 1000,
            incident_id=incident_id,
            count=len(result),
        )
        return result

    async def list_entities_with_details(self, incident_id: str) -> list[IncidentEntityDetail]:
        query = (
            "SELECT ee.event_id::text AS incident_id, "
            "       ee.entity_id::text AS entity_id, "
            "       ee.relation_type, "
            "       ee.description, "
            "       ee.display_priority, "
            "       ee.created_at AS linked_at, "
            "       ent.id::text AS ent_id, "
            "       ent.type AS ent_type, "
            "       ST_AsGeoJSON(ent.geometry::geometry)::json AS geometry_geojson, "
            "       ent.properties, "
            "       ent.layer_code, "
            "       ent.properties->>'name' AS display_name, "
            "       ent.created_by, "
            "       ent.updated_by, "
            "       ent.created_at AS ent_created_at, "
            "       ent.updated_at AS ent_updated_at "
            "  FROM operational.event_entities ee "
            "  JOIN operational.entities ent ON ent.id = ee.entity_id "
            " WHERE ee.event_id = %(incident_id)s::uuid "
            " ORDER BY ee.display_priority DESC NULLS LAST, ee.created_at DESC"
        )
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, {"incident_id": incident_id})
                rows = await cur.fetchall()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident", "list_entities_with_details").observe(duration)
        DAO_CALL_TOTAL.labels("incident", "list_entities_with_details", "success").inc()

        results: list[IncidentEntityDetail] = []
        for row in rows:
            geometry_value = row["geometry_geojson"]
            geometry_mapping = _ensure_mapping(geometry_value)
            properties_mapping = _ensure_mapping(row["properties"])
            link = IncidentEntityLink(
                incident_id=row["incident_id"],
                entity_id=row["entity_id"],
                relation_type=row["relation_type"],
                notes=row["description"],
                display_priority=row["display_priority"],
                linked_at=row["linked_at"],
            )
            display_name = row["display_name"]
            if not display_name and isinstance(properties_mapping, Mapping):
                display_name = (
                    properties_mapping.get("label")
                    or properties_mapping.get("name")
                    or properties_mapping.get("title")
                )
            entity = EntityRecord(
                entity_id=row["ent_id"],
                entity_type=row["ent_type"],
                geometry_geojson=geometry_mapping,
                properties=properties_mapping,
                layer_code=row["layer_code"],
                display_name=display_name if isinstance(display_name, str) else None,
                created_by=row["created_by"],
                updated_by=row["updated_by"],
                created_at=row["ent_created_at"],
                updated_at=row["ent_updated_at"],
            )
            results.append(IncidentEntityDetail(link=link, entity=entity))

        logger.info(
            "dao_incident_list_entities_with_details",
            duration_ms=duration * 1000,
            incident_id=incident_id,
            count=len(results),
        )
        return results

    async def list_active_risk_zones(self, *, reference_time: Optional[datetime] = None) -> list[RiskZoneRecord]:
        now = reference_time or datetime.now(timezone.utc)
        query = (
            "SELECT zone_id::text AS zone_id, "
            "       zone_name, "
            "       hazard_type, "
            "       severity, "
            "       description, "
            "       ST_AsGeoJSON(area::geometry)::json AS geometry_geojson, "
            "       properties, "
            "       valid_from, "
            "       valid_until, "
            "       created_at, "
            "       updated_at "
            "  FROM operational.hazard_zones "
            " WHERE deleted_at IS NULL "
            "   AND (valid_until IS NULL OR valid_until >= %(now)s) "
            " ORDER BY severity DESC, updated_at DESC"
        )
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, {"now": now})
                rows = await cur.fetchall()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident", "list_active_risk_zones").observe(duration)
        DAO_CALL_TOTAL.labels("incident", "list_active_risk_zones", "success").inc()

        results: list[RiskZoneRecord] = []
        for row in rows:
            geometry_mapping = _ensure_mapping(row["geometry_geojson"])
            properties_mapping = _ensure_mapping(row["properties"])
            results.append(
                RiskZoneRecord(
                    zone_id=row["zone_id"],
                    zone_name=row["zone_name"],
                    hazard_type=row["hazard_type"],
                    severity=int(row["severity"]),
                    description=row["description"],
                    geometry_geojson=geometry_mapping,
                    properties=properties_mapping,
                    valid_from=row["valid_from"],
                    valid_until=row["valid_until"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        logger.info(
            "dao_incident_list_active_risk_zones",
            duration_ms=duration * 1000,
            count=len(results),
        )
        return results


class IncidentRepository:
    """事件实体与关联写入接口。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> "IncidentRepository":
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def create_entity_with_link(self, payload: IncidentEntityCreateInput) -> IncidentEntityDetail:
        created_by = payload.created_by or "system"
        source = payload.source or "system"
        style_overrides_json = _json_dumps(payload.style_overrides)
        properties_json = _json_dumps(payload.properties)
        geometry_json = json.dumps(payload.geometry_geojson)
        entity_query = (
            "INSERT INTO operational.entities "
            "  (type, geometry, properties, created_by, updated_by, layer_code, image, source, "
            "   is_visible_on_map, is_dynamic, style_overrides) "
            "VALUES "
            "  (%(type)s, ST_SetSRID(ST_GeomFromGeoJSON(%(geometry)s), 4326)::geography, %(properties)s::jsonb, "
            "   %(created_by)s, %(created_by)s, %(layer_code)s, %(image)s, %(source)s::operational.entity_source_enum, "
            "   %(visible)s, false, %(style_overrides)s::jsonb) "
            "RETURNING "
            "  id::text AS entity_id, "
            "  type, "
            "  ST_AsGeoJSON(geometry::geometry)::json AS geometry_geojson, "
            "  properties, "
            "  layer_code, "
            "  created_by, "
            "  updated_by, "
            "  created_at, "
            "  updated_at"
        )
        entity_params = {
            "type": payload.entity_type,
            "geometry": geometry_json,
            "properties": properties_json,
            "created_by": created_by,
            "layer_code": payload.layer_code,
            "image": payload.image,
            "source": source,
            "visible": payload.is_visible_on_map,
            "style_overrides": style_overrides_json,
        }

        link_query = (
            "INSERT INTO operational.event_entities "
            "  (event_id, entity_id, relation_type, description, display_priority) "
            "VALUES "
            "  (%(incident_id)s::uuid, %(entity_id)s::uuid, %(relation_type)s, %(description)s, %(display_priority)s) "
            "RETURNING "
            "  event_id::text AS incident_id, "
            "  entity_id::text AS entity_id, "
            "  relation_type, "
            "  description AS notes, "
            "  display_priority, "
            "  created_at AS linked_at"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(entity_query, entity_params)
                entity_row = await cur.fetchone()
                if entity_row is None:
                    raise RuntimeError("创建实体失败，未返回记录。")

                link_params = {
                    "incident_id": payload.incident_id,
                    "entity_id": entity_row["entity_id"],
                    "relation_type": payload.relation_type,
                    "description": payload.relation_description,
                    "display_priority": payload.display_priority,
                }
                await cur.execute(link_query, link_params)
                link_row = await cur.fetchone()
                if link_row is None:
                    raise RuntimeError("创建事件实体关联失败，未返回记录。")

        properties_mapping = _ensure_mapping(entity_row["properties"])
        display_name = properties_mapping.get("name") or properties_mapping.get("label") or properties_mapping.get("title")
        entity = EntityRecord(
            entity_id=entity_row["entity_id"],
            entity_type=entity_row["type"],
            geometry_geojson=_ensure_mapping(entity_row["geometry_geojson"]),
            properties=properties_mapping,
            layer_code=entity_row["layer_code"],
            display_name=display_name if isinstance(display_name, str) else None,
            created_by=entity_row["created_by"],
            updated_by=entity_row["updated_by"],
            created_at=entity_row["created_at"],
            updated_at=entity_row["updated_at"],
        )
        link = IncidentEntityLink(
            incident_id=link_row["incident_id"],
            entity_id=link_row["entity_id"],
            relation_type=link_row["relation_type"],
            notes=link_row["notes"],
            display_priority=link_row["display_priority"],
            linked_at=link_row["linked_at"],
        )
        logger.info(
            "incident_entity_created",
            incident_id=payload.incident_id,
            entity_id=entity.entity_id,
            relation_type=payload.relation_type,
            source=source,
        )
        return IncidentEntityDetail(link=link, entity=entity)


class IncidentSnapshotRepository:
    """事件快照写入/读取接口。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> "IncidentSnapshotRepository":
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def create_snapshot(self, payload: IncidentSnapshotCreateInput) -> IncidentSnapshotRecord:
        query = (
            "INSERT INTO operational.incident_snapshots "
            "  (incident_id, snapshot_type, payload, generated_at, created_by) "
            "VALUES "
            "  (%(incident_id)s::uuid, %(snapshot_type)s, %(payload)s::jsonb, %(generated_at)s, %(created_by)s) "
            "RETURNING "
            "  snapshot_id::text AS snapshot_id, "
            "  incident_id::text AS incident_id, "
            "  snapshot_type, "
            "  payload, "
            "  generated_at, "
            "  created_by, "
            "  created_at"
        )
        params = {
            "incident_id": payload.incident_id,
            "snapshot_type": payload.snapshot_type,
            "payload": Jsonb(payload.payload),
            "generated_at": payload.generated_at,
            "created_by": payload.created_by,
        }
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(IncidentSnapshotRecord)) as cur:
                await cur.execute(query, params)
                record = await cur.fetchone()
                if record is None:
                    raise RuntimeError("插入事件快照失败，未返回记录。")

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident_snapshot", "create_snapshot").observe(duration)
        DAO_CALL_TOTAL.labels("incident_snapshot", "create_snapshot", "success").inc()
        logger.info(
            "dao_incident_snapshot_create",
            duration_ms=duration * 1000,
            incident_id=record.incident_id,
            snapshot_id=record.snapshot_id,
        )
        return record

    async def get_snapshot(self, snapshot_id: str) -> IncidentSnapshotRecord | None:
        query = (
            "SELECT snapshot_id::text AS snapshot_id, "
            "       incident_id::text AS incident_id, "
            "       snapshot_type, "
            "       payload, "
            "       generated_at, "
            "       created_by, "
            "       created_at "
            "  FROM operational.incident_snapshots "
            " WHERE snapshot_id = %(snapshot_id)s::uuid"
        )
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(IncidentSnapshotRecord)) as cur:
                await cur.execute(query, {"snapshot_id": snapshot_id})
                record = await cur.fetchone()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident_snapshot", "get_snapshot").observe(duration)
        DAO_CALL_TOTAL.labels("incident_snapshot", "get_snapshot", "success").inc()
        if record is None:
            logger.info(
                "dao_incident_snapshot_get_empty",
                duration_ms=duration * 1000,
                snapshot_id=snapshot_id,
            )
        else:
            logger.info(
                "dao_incident_snapshot_get",
                duration_ms=duration * 1000,
                snapshot_id=record.snapshot_id,
                incident_id=record.incident_id,
            )
        return record

    async def delete_snapshot(self, snapshot_id: str) -> None:
        query = "DELETE FROM operational.incident_snapshots WHERE snapshot_id = %(snapshot_id)s::uuid"
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"snapshot_id": snapshot_id})

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident_snapshot", "delete_snapshot").observe(duration)
        DAO_CALL_TOTAL.labels("incident_snapshot", "delete_snapshot", "success").inc()
        logger.info(
            "dao_incident_snapshot_delete",
            duration_ms=duration * 1000,
            snapshot_id=snapshot_id,
        )

    async def list_snapshots(
        self,
        incident_id: str,
        *,
        snapshot_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[IncidentSnapshotRecord]:
        conditions = ["incident_id = %(incident_id)s::uuid"]
        params: dict[str, Any] = {"incident_id": incident_id, "limit": max(limit, 1)}
        if snapshot_type:
            conditions.append("snapshot_type = %(snapshot_type)s")
            params["snapshot_type"] = snapshot_type
        query = (
            "SELECT snapshot_id::text AS snapshot_id, "
            "       incident_id::text AS incident_id, "
            "       snapshot_type, "
            "       payload, "
            "       generated_at, "
            "       created_by, "
            "       created_at "
            "  FROM operational.incident_snapshots "
            f" WHERE {' AND '.join(conditions)} "
            " ORDER BY generated_at DESC "
            " LIMIT %(limit)s"
        )
        start = time.perf_counter()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(IncidentSnapshotRecord)) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                result = list(rows)

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("incident_snapshot", "list_snapshots").observe(duration)
        DAO_CALL_TOTAL.labels("incident_snapshot", "list_snapshots", "success").inc()
        logger.info(
            "dao_incident_snapshot_list",
            duration_ms=duration * 1000,
            incident_id=incident_id,
            snapshot_type=snapshot_type,
            count=len(result),
        )
        return result


class RescueDAO:
    """战术救援资源读取。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> "RescueDAO":
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def list_available_rescuers(self, *, limit: int = 25) -> list[RescuerRecord]:
        start = time.perf_counter()
        query = (
            "SELECT rescuer_id::text AS rescuer_id, "
            "       name, "
            "       rescuer_type, "
            "       status, "
            "       availability, "
            "       ST_X(current_location::geometry) AS lng, "
            "       ST_Y(current_location::geometry) AS lat, "
            "       skills, "
            "       equipment "
            "  FROM operational.rescuers "
            " WHERE availability IS TRUE "
            "   AND deleted_at IS NULL "
            " ORDER BY updated_at DESC "
            " LIMIT %(limit)s"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(RescuerRecord)) as cur:
                await cur.execute(query, {"limit": max(limit, 1)})
                rows = await cur.fetchall()

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("rescue", "list_rescuers").observe(duration)
        DAO_CALL_TOTAL.labels("rescue", "list_rescuers", "success").inc()
        logger.info(
            "dao_rescue_list_rescuers",
            duration_ms=duration * 1000,
            limit=limit,
            returned=len(rows),
        )
        return [
            RescuerRecord(
                rescuer_id=row.rescuer_id,
                name=row.name,
                rescuer_type=row.rescuer_type,
                status=row.status,
                availability=bool(row.availability),
                lng=float(row.lng) if row.lng is not None else None,
                lat=float(row.lat) if row.lat is not None else None,
                skills=list(row.skills or []),
                equipment=dict(row.equipment or {}),
            )
            for row in rows
        ]


class RescueTaskRepository:
    """战术救援任务写入接口。"""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    def create(cls, pool: AsyncConnectionPool[Any]) -> "RescueTaskRepository":
        if pool is None:
            raise ValueError("pool 不能为空")
        return cls(pool)

    async def create_task(self, payload: TaskCreateInput) -> TaskRecord:
        start = time.perf_counter()
        query = (
            "INSERT INTO operational.tasks "
            "  (type, status, priority, description, deadline, result, progress, target_entity_id, "
            "   created_by, updated_by, event_id, code) "
            "VALUES "
            "  (%(type)s, %(status)s, %(priority)s, %(description)s, %(deadline)s, NULL, 0, %(target_entity_id)s, "
            "   %(created_by)s, %(updated_by)s, %(event_id)s, %(code)s) "
            "RETURNING "
            "  id::text AS id, "
            "  type::text AS task_type, "
            "  status::text AS status, "
            "  priority, "
            "  description, "
            "  deadline, "
            "  progress, "
            "  event_id::text AS event_id, "
            "  code, "
            "  created_at, "
            "  updated_at"
        )
        params = {
            "type": payload.task_type,
            "status": payload.status,
            "priority": payload.priority,
            "description": payload.description,
            "deadline": payload.deadline,
            "target_entity_id": payload.target_entity_id,
            "created_by": payload.created_by,
            "updated_by": payload.updated_by,
            "event_id": payload.event_id,
            "code": payload.code,
        }
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(TaskRecord)) as cur:
                await cur.execute(query, params)
                record = await cur.fetchone()
                if record is None:
                    raise RuntimeError("插入任务失败，未返回记录。")

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("rescue", "create_task").observe(duration)
        DAO_CALL_TOTAL.labels("rescue", "create_task", "success").inc()
        logger.info(
            "dao_rescue_create_task",
            duration_ms=duration * 1000,
            task_id=record.id,
            event_id=record.event_id,
        )
        return record

    async def create_route_plan(self, payload: TaskRoutePlanCreateInput) -> TaskRoutePlanRecord:
        start = time.perf_counter()
        query = (
            "INSERT INTO operational.task_route_plans "
            "  (task_id, status, strategy, origin_geojson, destination_geojson, polyline_geojson, "
            "   distance_meters, duration_seconds, estimated_arrival_time, avoid_polygons) "
            "VALUES "
            "  (%(task_id)s, %(status)s, %(strategy)s, %(origin_geojson)s::jsonb, %(destination_geojson)s::jsonb, "
            "   %(polyline_geojson)s::jsonb, %(distance_meters)s, %(duration_seconds)s, %(estimated_arrival_time)s, "
            "   %(avoid_polygons)s::jsonb) "
            "RETURNING "
            "  id::text AS id, "
            "  task_id::text AS task_id, "
            "  status, "
            "  strategy, "
            "  origin_geojson, "
            "  destination_geojson, "
            "  polyline_geojson, "
            "  distance_meters, "
            "  duration_seconds, "
            "  estimated_arrival_time, "
            "  avoid_polygons, "
            "  created_at, "
            "  updated_at"
        )
        params = {
            "task_id": payload.task_id,
            "status": payload.status,
            "strategy": payload.strategy,
            "origin_geojson": _optional_json(payload.origin_geojson),
            "destination_geojson": _optional_json(payload.destination_geojson),
            "polyline_geojson": _optional_json(payload.polyline_geojson),
            "distance_meters": payload.distance_meters,
            "duration_seconds": payload.duration_seconds,
            "estimated_arrival_time": payload.estimated_arrival_time,
            "avoid_polygons": _optional_json(payload.avoid_polygons),
        }
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(TaskRoutePlanRecord)) as cur:
                await cur.execute(query, params)
                record = await cur.fetchone()
                if record is None:
                    raise RuntimeError("插入任务路线失败，未返回记录。")

        duration = time.perf_counter() - start
        DAO_CALL_LATENCY.labels("rescue", "create_route_plan").observe(duration)
        DAO_CALL_TOTAL.labels("rescue", "create_route_plan", "success").inc()
        logger.info(
            "dao_rescue_create_route_plan",
            duration_ms=duration * 1000,
            task_id=record.task_id,
            route_id=record.id,
        )
        return record


def _optional_json(value: Mapping[str, Any] | None) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value)


def _json_dumps(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value))


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise TypeError(f"无法解析为 JSON 对象: {value!r}") from exc
        if isinstance(parsed, Mapping):
            return dict(parsed)
        raise TypeError(f"JSON 内容不是对象: {parsed!r}")
    raise TypeError(f"不支持的 JSON 类型: {type(value)!r}")


def serialize_dataclass(instance: Any) -> dict[str, Any]:
    """统一的 dataclass 序列化方法。"""

    result = asdict(instance)
    for key, value in list(result.items()):
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()  # type: ignore[assignment]
    return result


def serialize_iter(items: Iterable[Any]) -> list[dict[str, Any]]:
    """序列化 dataclass 列表。"""

    return [serialize_dataclass(item) for item in items]
