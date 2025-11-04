from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import asyncio
import json
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.rows import DictRow, dict_row
from psycopg import errors
from psycopg_pool import AsyncConnectionPool

from emergency_agents.config import AppConfig
from emergency_agents.db.dao import IncidentDAO
from emergency_agents.db.models import QueryParams
from emergency_agents.llm.client import get_openai_client
from openai import OpenAI
import httpx


logger = structlog.get_logger(__name__)


router = APIRouter(prefix="/ai/rescue", tags=["ai-rescue"])

# 依赖在 main.py 中注入
_pg_pool_async: Optional[AsyncConnectionPool[DictRow]] = None


class GeoPoint(BaseModel):
    lon: float = Field(..., ge=-180.0, le=180.0)
    lat: float = Field(..., ge=-90.0, le=90.0)


class OverallPlanRequest(BaseModel):
    incident_id: str = Field(..., description="事件ID(UUID)")
    time_range_hours: int = Field(24, ge=1, le=168, description="统计窗口(小时)")


class OperationalPeriod(BaseModel):
    start_iso: str
    end_iso: str


class DeviceAssignment(BaseModel):
    device_id: str
    choose: bool
    mission: str
    target_points: List[GeoPoint] = Field(default_factory=list)
    area_radius_m: Optional[int] = None
    rationale: str
    # 关联 recon_priority_targets（更真实的侦察目标约束）
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    target_type: Optional[str] = None
    # 可执行参数（让方案可落地执行）
    pattern: Optional[str] = Field(
        default=None, description="执行轨迹：grid|lawnmower|spiral|point_hold"
    )
    duration_min: Optional[int] = Field(default=None, ge=1)
    speed_kmh: Optional[float] = Field(default=None, ge=0)
    altitude_m: Optional[int] = Field(default=None, ge=0)
    depth_m: Optional[int] = Field(default=None, ge=0)
    sensors: Optional[List[str]] = None
    comms_channel: Optional[str] = None


class OverallPlanResponse(BaseModel):
    operational_period: OperationalPeriod
    assignments: List[DeviceAssignment]
    plan_summary: str


async def _fetch_selected_devices(pool: AsyncConnectionPool[DictRow]) -> List[Dict[str, Any]]:
    """按照既定业务规则查询“被选中且可作为侦察/救援投入”的设备列表。

    规则：
    - device.is_recon = TRUE
    - 存在 car_device_select 选中记录，且对应 car_supply_select 也有选中记录（同一 car_id）
    """
    sql = (
        "SELECT d.id, d.name, d.device_type, d.is_recon "
        "FROM operational.device d "
        "WHERE d.is_recon IS TRUE "
        "  AND (COALESCE(d.in_task_use, 0) = 0) "
        "  AND EXISTS ("
        "    SELECT 1 FROM operational.car_device_select cds "
        "    JOIN operational.car_supply_select css ON css.car_id = cds.car_id AND css.is_selected = 1 "
        "    WHERE cds.device_id = d.id AND cds.is_selected = 1"
        "  )"
    )
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            try:
                await cur.execute(sql)
            except errors.UndefinedColumn as exc:
                raise HTTPException(status_code=500, detail="device.in_task_use 字段缺失，请先执行数据库升级脚本") from exc
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def _fetch_device_capabilities(pool: AsyncConnectionPool[DictRow], device_ids: List[str]) -> Dict[str, List[str]]:
    if not device_ids:
        return {}
    sql = (
        "SELECT device_id, capability FROM operational.device_capability WHERE device_id = ANY(%s)"
    )
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (device_ids,))
            rows = await cur.fetchall()
    caps: Dict[str, List[str]] = {}
    for device_id, capability in rows:
        caps.setdefault(str(device_id), []).append(str(capability))
    return caps


def _centroid_from_geometry(geometry: Dict[str, Any]) -> Optional[GeoPoint]:
    gtype = str(geometry.get("type") or "").lower()
    if gtype == "point":
        coords = geometry.get("coordinates") or []
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            return GeoPoint(lon=float(coords[0]), lat=float(coords[1]))
        return None
    coords_list: List[Tuple[float, float]] = []
    def _collect(o: Any) -> None:
        if isinstance(o, (list, tuple)):
            if len(o) == 2 and all(isinstance(v, (int, float)) for v in o):
                coords_list.append((float(o[0]), float(o[1])))
            else:
                for item in o:
                    _collect(item)
    if gtype in {"polygon", "multipolygon", "linestring"}:
        _collect(geometry.get("coordinates"))
    if coords_list:
        lon = sum(p[0] for p in coords_list) / len(coords_list)
        lat = sum(p[1] for p in coords_list) / len(coords_list)
        return GeoPoint(lon=lon, lat=lat)
    return None


async def _incident_candidate_points(pool: AsyncConnectionPool[DictRow], incident_id: str) -> List[GeoPoint]:
    dao = IncidentDAO.create(pool)
    details = await dao.list_entities_with_details(incident_id)
    candidates: List[GeoPoint] = []
    for item in details:
        geom = dict(item.entity.geometry_geojson)
        pt = _centroid_from_geometry(geom)
        if pt is not None:
            candidates.append(pt)
    return candidates


async def _fetch_priority_targets(
    pool: AsyncConnectionPool[DictRow],
    center: GeoPoint,
    radius_km: float = 30.0,
    max_items: int = 100,
) -> List[Dict[str, Any]]:
    """读取 recon_priority_targets 中接近事件中心的重点目标（更贴近真实侦察对象）。"""
    # hazard_level 排序权重：critical>high>medium>low
    sql = (
        "SELECT id::text, name, target_type::text, hazard_level::text, hazard_focus, lon, lat, priority "
        "FROM operational.recon_priority_targets "
        "WHERE county = '茂县' "
        "  AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s) "
        "ORDER BY CASE hazard_level WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC, priority DESC "
        "LIMIT %s"
    )
    params = (center.lon, center.lat, int(radius_km * 1000), max_items)
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@router.post("/overall-plan", response_model=OverallPlanResponse)
async def generate_overall_rescue_plan(req: OverallPlanRequest, request: Request) -> OverallPlanResponse:
    """基于选中设备与事件几何，生成整体救援方案（由 LLM=glm4.6 严格按模板输出）。"""
    cfg = AppConfig.load_from_env()
    if _pg_pool_async is None:
        raise HTTPException(status_code=503, detail="pg pool unavailable")

    # 1) 查询选中设备
    devices = await _fetch_selected_devices(_pg_pool_async)
    if not devices:
        raise HTTPException(status_code=400, detail="无选中设备，无法生成整体救援方案")
    device_ids = [str(d["id"]) for d in devices]
    caps_map = await _fetch_device_capabilities(_pg_pool_async, device_ids)
    # enrich
    enriched_devices: List[Dict[str, Any]] = []
    for d in devices:
        item = dict(d)
        item["capabilities"] = caps_map.get(str(d["id"]), [])
        enriched_devices.append(item)

    # 2) 事件几何候选点（严格要求存在）与重点侦察目标
    points = await _incident_candidate_points(_pg_pool_async, req.incident_id)
    if not points:
        raise HTTPException(status_code=400, detail="事件缺少空间几何（event_entities），无法为设备规划坐标")
    center = points[0]  # 使用第一个候选点作为中心
    priority_targets = await _fetch_priority_targets(_pg_pool_async, center=center, radius_km=30.0, max_items=100)

    # 3) 作战周期 + 天气（先写死，后续接DB）
    now = datetime.now(timezone.utc)
    period = OperationalPeriod(start_iso=now.isoformat(), end_iso=(now + timedelta(hours=12)).isoformat())
    weather = {
        "phenomena": ["heavy_rain"],
        "wind_speed_mps": 8.0,
        "visibility_km": 4.0,
        "precip_mm_h": 6.0,
        "precip_24h_mm": 60.0,
        "storm_warning": False,
        "note": "固定值（后续查库）：暴雨过程，低能见度，水位上涨风险"
    }

    # 4) 构造提示词（严格模板 + 禁止臆造）
    system_msg = (
        "你是基于 ICS/IAP 的救援作战规划官。"
        "请仅使用提供的设备列表与事件候选坐标，制定下一作战周期的整体救援方案。"
        "必须严格按模板输出 JSON；禁止臆造设备/坐标/字段；每台设备如不选择必须说明原因。"
    )

    template = {
        "operational_period": {"start_iso": period.start_iso, "end_iso": period.end_iso},
        "assignments": [
            {
                "device_id": "<string>",
                "choose": True,
                "mission": "rescue|recon|support",
                "target_id": "<string_from_priority_targets>",
                "target_name": "<string>",
                "target_type": "<string>",
                "target_points": [{"lon": 0.0, "lat": 0.0}],
                "area_radius_m": 0,
                "rationale": "<string>",
                "pattern": "grid|lawnmower|spiral|point_hold",
                "duration_min": 30,
                "speed_kmh": 20.0,
                "altitude_m": 120,
                "depth_m": 0,
                "sensors": ["thermal_imaging", "gas_detection"],
                "comms_channel": "VHF-155.250"
            }
        ],
        "plan_summary": "<string>"
    }

    payload = {
        "incident_id": req.incident_id,
        "time_range_hours": req.time_range_hours,
        "selected_devices": enriched_devices,
        "candidate_points": [p.model_dump() for p in points],
        "priority_targets": priority_targets,
        "weather": weather,
        "rules": {
            "max_assignments": 12,
            "max_points_per_device": 3
        }
    }

    schema_hint = (
        "仅输出一个 JSON 对象，字段严格等于："
        "{\"operational_period\":{\"start_iso\":\"\",\"end_iso\":\"\"},"
        "\"assignments\":[{\"device_id\":\"\",\"choose\":true,\"mission\":\"rescue|recon|support\",\"target_id\":\"\",\"target_name\":\"\",\"target_type\":\"\",\"target_points\":[{\"lon\":0.0,\"lat\":0.0}],\"area_radius_m\":0,\"rationale\":\"\",\"pattern\":\"grid|lawnmower|spiral|point_hold\",\"duration_min\":30,\"speed_kmh\":20.0,\"altitude_m\":120,\"depth_m\":0,\"sensors\":[\"\"],\"comms_channel\":\"\"}],"
        "\"plan_summary\":\"\"}."
        " 所有 device_id 必须来自 selected_devices；target_id 必须来自 priority_targets；target_points 必须等于对应 target_id 的 lon/lat（不得越界/不得虚构）；"
        " choose=false 必须给出 rationale；choose=true 必须给出 mission/target_id/target_name/target_type/target_points/area_radius_m，并结合 weather 选择合适 pattern/duration/altitude/depth/sensors/comms_channel；"
        " 不得添加未定义字段；不得返回示例占位；不得输出自然语言解释。"
    )

    # 使用侦察专用的 LLM 端点（与 /recon 保持一致），确保 glm-4.6 可用
    if not cfg.recon_llm_base_url or not cfg.recon_llm_api_key:
        # 回退到默认端点（若未配置专用端点），保持显式提示
        logger.warning("overall_rescue_using_default_openai_endpoint")
        client = get_openai_client(cfg)
    else:
        timeout = httpx.Timeout(
            connect=5.0,
            read=cfg.llm_request_timeout_seconds,
            write=cfg.llm_request_timeout_seconds,
            pool=None,
        )
        http_client = httpx.Client(trust_env=False, timeout=timeout)
        client = OpenAI(
            base_url=cfg.recon_llm_base_url,
            api_key=cfg.recon_llm_api_key,
            http_client=http_client,
            timeout=cfg.llm_request_timeout_seconds,
        )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"{schema_hint}\n上下文：{json.dumps(payload, ensure_ascii=False)}\n模板：{json.dumps(template, ensure_ascii=False)}"},
    ]

    try:
        completion = client.chat.completions.create(
            model="glm-4.6",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = completion.choices[0].message.content or "{}"
        data = json.loads(content)
    except Exception as exc:
        logger.error("overall_rescue_llm_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"LLM生成失败: {exc}")

    # 5) 基本结构校验（防御性）
    try:
        assignments_raw = data.get("assignments") or []
        assignments: List[DeviceAssignment] = []
        allowed_ids = set(device_ids)
        allowed_targets = {t["id"]: t for t in priority_targets}
        for item in assignments_raw:
            did = str(item.get("device_id") or "")
            if did not in allowed_ids:
                raise ValueError(f"非法设备ID: {did}")
            # 目标校验：必须来自 priority_targets，且坐标一致
            tgt_id = item.get("target_id")
            if item.get("choose") and not tgt_id:
                raise ValueError("choose=true 时必须指定 target_id")
            tps = [GeoPoint(**tp) for tp in (item.get("target_points") or [])]
            if item.get("choose"):
                if tgt_id not in allowed_targets:
                    raise ValueError(f"非法 target_id: {tgt_id}")
                tgt = allowed_targets[str(tgt_id)]
                if not tps:
                    raise ValueError("缺少 target_points")
                # 与库中坐标一致性校验（取首点对比）
                first = tps[0]
                if abs(first.lon - float(tgt["lon"])) > 1e-4 or abs(first.lat - float(tgt["lat"])) > 1e-4:
                    raise ValueError("target_points 与 target_id 坐标不一致")
                # 基本可执行性字段存在性校验
                if not item.get("duration_min"):
                    raise ValueError("缺少 duration_min")
                # UAV 推荐 altitude_m，USV 推荐 depth_m=0，robot_dog 推荐 sensors 包含近距检测
            assignments.append(
                DeviceAssignment(
                    device_id=did,
                    choose=bool(item.get("choose")),
                    mission=str(item.get("mission") or ""),
                    target_points=tps,
                    area_radius_m=item.get("area_radius_m"),
                    rationale=str(item.get("rationale") or ""),
                    target_id=str(tgt_id) if tgt_id else None,
                    target_name=str(item.get("target_name") or None),
                    target_type=str(item.get("target_type") or None),
                    pattern=str(item.get("pattern") or None),
                    duration_min=item.get("duration_min"),
                    speed_kmh=item.get("speed_kmh"),
                    altitude_m=item.get("altitude_m"),
                    depth_m=item.get("depth_m"),
                    sensors=item.get("sensors"),
                    comms_channel=str(item.get("comms_channel") or None),
                )
            )
        plan_summary = str(data.get("plan_summary") or "")
    except Exception as exc:
        logger.error("overall_rescue_struct_invalid", error=str(exc))
        raise HTTPException(status_code=500, detail=f"返回结构不合法: {exc}")

    return OverallPlanResponse(
        operational_period=period,
        assignments=assignments,
        plan_summary=plan_summary,
    )
