"""全新侦察方案接口（优先目标约束）。

设计原则：
- 强类型（Pydantic）+ 明确错误（不兜底、不降级）。
- 设备筛选：仅使用 is_recon=TRUE 且 in_task_use=0 的"已选中设备"（EXISTS 车+补给）。
- 目标来源：仅使用 operational.recon_priority_targets 表（真实重点目标），半径与数量可调。
- 模型：固定使用 glm-4.6（Zhipu）。
- 配置回退：优先使用 RECON_LLM_*，未配置时回退到项目通用配置 OPENAI_*。
- 模板：严格 JSON schema，choose=false 也必须有 rationale；choose=true 必须含 mission/target_* 与可执行参数。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Set, Iterable

import json
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from psycopg import errors
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from emergency_agents.config import AppConfig
from emergency_agents.db.dao import IncidentDAO


logger = structlog.get_logger(__name__)


router = APIRouter(prefix="/ai/recon", tags=["ai-recon"])

# 由 main.py 在应用启动时注入（同 overall_rescue 的做法）
_pg_pool_async: Optional[AsyncConnectionPool[DictRow]] = None


class GeoPoint(BaseModel):
    """经纬度点位（WGS84）。"""

    lon: float = Field(..., ge=-180.0, le=180.0)
    lat: float = Field(..., ge=-90.0, le=90.0)


class ReconPriorityPlanRequest(BaseModel):
    """请求体：侦察方案生成。"""

    incident_id: str = Field(..., description="事件ID(UUID)")
    time_range_hours: int = Field(24, ge=1, le=168, description="统计窗口(小时)")
    hazard_scenario: str = Field(
        ..., description="灾情场景关键词，如 flood/chemical_leak/landslide 等"
    )
    radius_km: float = Field(30.0, ge=1.0, le=80.0, description="目标检索半径（公里）")
    max_targets: int = Field(60, ge=1, le=200, description="最多取多少重点目标")


class OperationalPeriod(BaseModel):
    """作战周期描述。"""

    start_iso: str
    end_iso: str


class DeviceAssignment(BaseModel):
    """设备分配与执行参数（严格用于“侦察”）。"""

    device_id: str
    choose: bool
    mission: str = Field("recon", pattern="^(recon)$")
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    target_type: Optional[str] = None
    target_points: List[GeoPoint] = Field(default_factory=list)
    area_radius_m: Optional[int] = None
    rationale: str
    # 可执行参数
    pattern: Optional[str] = Field(
        default=None, description="轨迹：grid|lawnmower|spiral|point_hold"
    )
    duration_min: Optional[int] = Field(default=None, ge=1)
    speed_kmh: Optional[float] = Field(default=None, ge=0)
    altitude_m: Optional[int] = Field(default=None, ge=0)
    depth_m: Optional[int] = Field(default=None, ge=0)
    sensors: Optional[List[str]] = None
    comms_channel: Optional[str] = None


class ReconPriorityPlanResponse(BaseModel):
    operational_period: OperationalPeriod
    assignments: List[DeviceAssignment]
    plan_summary: str


class RecommendedEquipment(BaseModel):
    """大模型推荐的装备条目。"""

    category: str = Field(..., description="装备类别，如 usv/uav/robot_dog")
    capabilities: List[str] = Field(default_factory=list, description="能力标签")
    suggested_quantity: int = Field(..., ge=1, description="建议数量")
    rationale: str = Field(..., description="推荐理由")
    source: str = Field(..., description="来源说明：如 'LLM(glm-4.6)+domain_rules(flood)'")


class ReconPriorityPlanResponse(BaseModel):  # type: ignore[no-redef]
    operational_period: OperationalPeriod
    assignments: List[DeviceAssignment]
    plan_summary: str
    no_suitable_equipment: bool | None = Field(default=None, description="若为True表示本轮没有可用装备")
    recommendations: List[RecommendedEquipment] | None = Field(default=None, description="推荐装备清单（已按场景策略过滤）")


async def _fetch_selected_devices(pool: AsyncConnectionPool[DictRow]) -> List[Dict[str, Any]]:
    """查询“被选中且可用于侦察”的设备。

    规则：
    - d.is_recon IS TRUE
    - COALESCE(d.in_task_use,0)=0
    - EXISTS 选中车辆与补给（同车）
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
    """读取设备能力标签集合。"""

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
    """从 GeoJSON 计算近似中心点。"""

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


async def _incident_center(pool: AsyncConnectionPool[DictRow], incident_id: str) -> GeoPoint:
    """获取事件空间中心点（从 event_entities 求质心，若多个取第一个）。"""

    dao = IncidentDAO.create(pool)
    details = await dao.list_entities_with_details(incident_id)
    for item in details:
        geom = dict(item.entity.geometry_geojson)
        pt = _centroid_from_geometry(geom)
        if pt is not None:
            return pt
    raise HTTPException(status_code=400, detail="事件缺少空间几何（event_entities），无法规划侦察坐标")


async def _fetch_priority_targets(
    pool: AsyncConnectionPool[DictRow], *, center: GeoPoint, radius_km: float, max_items: int
) -> List[Dict[str, Any]]:
    """读取 recon_priority_targets（限定茂县，半径过滤，按 hazard_level/priority 排序）。"""

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


@router.post("/priority-plan", response_model=ReconPriorityPlanResponse)
async def generate_recon_priority_plan(
    req: ReconPriorityPlanRequest, request: Request
) -> ReconPriorityPlanResponse:
    """生成“全新侦察方案”（优先目标约束，固定 glm-4.6）。"""

    cfg = AppConfig.load_from_env()
    if _pg_pool_async is None:
        raise HTTPException(status_code=503, detail="pg pool unavailable")

    # 配置回退逻辑：优先使用专用配置，未配置时回退到项目通用配置
    recon_base_url = cfg.recon_llm_base_url or cfg.openai_base_url
    recon_api_key = cfg.recon_llm_api_key or cfg.openai_api_key

    if not recon_base_url or not recon_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM配置缺失：RECON_LLM_* 和 OPENAI_* 均未配置，无法调用 glm-4.6"
        )

    # 1) 设备筛选
    devices = await _fetch_selected_devices(_pg_pool_async)
    if not devices:
        raise HTTPException(status_code=400, detail="无选中可用侦察设备（is_recon=true 且 in_task_use=0）")
    device_ids = [str(d["id"]) for d in devices]
    caps_map = await _fetch_device_capabilities(_pg_pool_async, device_ids)
    enriched_devices: List[Dict[str, Any]] = []
    for d in devices:
        item = dict(d)
        item["capabilities"] = caps_map.get(str(d["id"]), [])
        enriched_devices.append(item)

    # 2) 事件中心 + 重点目标
    center = await _incident_center(_pg_pool_async, req.incident_id)
    targets = await _fetch_priority_targets(
        _pg_pool_async, center=center, radius_km=req.radius_km, max_items=req.max_targets
    )
    if not targets:
        raise HTTPException(status_code=400, detail="周边无重点侦察目标，无法规划侦察任务")

    # 3) 作战周期 + 天气（先写死）
    now = datetime.now(timezone.utc)
    period = OperationalPeriod(start_iso=now.isoformat(), end_iso=(now + timedelta(hours=8)).isoformat())
    weather = {
        "phenomena": ["heavy_rain"],
        "wind_speed_mps": 8.0,
        "visibility_km": 4.0,
        "precip_mm_h": 6.0,
        "precip_24h_mm": 60.0,
        "storm_warning": False,
        "note": "固定：暴雨过程，低能见度，水位上涨风险"
    }

    # 4) 提示词与模板（严格 JSON）
    system_msg = (
        "你是 ICS/IAP 侦察作战规划官。只能选择提供的设备与 recon_priority_targets 目标，不得臆造坐标或设备。"
        "根据 hazard_scenario 与设备 capabilities 进行匹配：洪水/水域→USV；化工→RobotDog(具 hazmat/gas)；广域→UAV。"
        "choose=false 必须写清理由；choose=true 必须给 mission/target*/points/area 与可执行参数。"
    )
    template = {
        "operational_period": {"start_iso": period.start_iso, "end_iso": period.end_iso},
        "assignments": [
            {
                "device_id": "<string>",
                "choose": True,
                "mission": "recon",
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
        "hazard_scenario": req.hazard_scenario,
        "selected_devices": enriched_devices,
        "priority_targets": targets,
        "weather": weather,
        "rules": {"max_assignments": 10, "max_points_per_device": 2}
    }
    schema_hint = (
        "仅输出一个 JSON 对象，字段严格等于："
        "{\"operational_period\":{\"start_iso\":\"\",\"end_iso\":\"\"},"
        "\"assignments\":[{\"device_id\":\"\",\"choose\":true,\"mission\":\"recon\",\"target_id\":\"\",\"target_name\":\"\",\"target_type\":\"\",\"target_points\":[{\"lon\":0.0,\"lat\":0.0}],\"area_radius_m\":0,\"rationale\":\"\",\"pattern\":\"grid|lawnmower|spiral|point_hold\",\"duration_min\":30,\"speed_kmh\":20.0,\"altitude_m\":120,\"depth_m\":0,\"sensors\":[\"\"],\"comms_channel\":\"\"}],"
        "\"plan_summary\":\"\"}."
        " device_id 必须来自 selected_devices；target_id 必须来自 priority_targets；target_points 必须精确等于 target_id 的 lon/lat；"
        " choose=false 必须给 rationale；choose=true 必须包含所有执行参数并与 weather 合理匹配；不得添加未定义字段；不得输出自然语言解释。"
    )

    timeout = httpx.Timeout(connect=5.0, read=cfg.llm_request_timeout_seconds, write=cfg.llm_request_timeout_seconds)
    http_client = httpx.Client(trust_env=False, timeout=timeout)
    client = OpenAI(
        base_url=recon_base_url,
        api_key=recon_api_key,
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
    except Exception as exc:  # pragma: no cover
        logger.error("recon_priority_llm_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"LLM生成失败: {exc}")

    # 5) 解析与严格校验
    try:
        assignments_raw = data.get("assignments") or []
        if not isinstance(assignments_raw, list):
            raise ValueError("assignments 非数组")
        allowed_ids = set(device_ids)
        allowed_targets = {t["id"]: t for t in targets}
        parsed: List[DeviceAssignment] = []
        for item in assignments_raw:
            did = str(item.get("device_id") or "")
            if did not in allowed_ids:
                raise ValueError(f"非法设备ID: {did}")
            choose = bool(item.get("choose"))
            rat = str(item.get("rationale") or "")
            if not rat:
                raise ValueError("rationale 必填")
            tps = [GeoPoint(**tp) for tp in (item.get("target_points") or [])]
            tgt_id = item.get("target_id")
            if choose:
                if not tgt_id or tgt_id not in allowed_targets:
                    raise ValueError(f"非法 target_id: {tgt_id}")
                tgt = allowed_targets[str(tgt_id)]
                if not tps:
                    raise ValueError("缺少 target_points")
                first = tps[0]
                if abs(first.lon - float(tgt["lon"])) > 1e-4 or abs(first.lat - float(tgt["lat"])) > 1e-4:
                    raise ValueError("target_points 与 target_id 坐标不一致")
                if not item.get("duration_min"):
                    raise ValueError("缺少 duration_min")
            parsed.append(
                DeviceAssignment(
                    device_id=did,
                    choose=choose,
                    mission=str(item.get("mission") or "recon"),
                    target_id=str(tgt_id) if tgt_id else None,
                    target_name=str(item.get("target_name") or None),
                    target_type=str(item.get("target_type") or None),
                    target_points=tps,
                    area_radius_m=item.get("area_radius_m"),
                    rationale=rat,
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
    except (ValidationError, ValueError, TypeError) as exc:
        logger.error("recon_priority_struct_invalid", error=str(exc))
        raise HTTPException(status_code=500, detail=f"返回结构不合法: {exc}")

    # 若无任何被选中的设备任务：不报错，解释且给出推荐装备清单
    chosen_count = sum(1 for a in parsed if a.choose)
    if chosen_count == 0:
        logger.info("recon_priority_no_suitable_equipment", incident_id=req.incident_id)
        recs = _recommend_equipment_when_none(
            client=client,
            hazard=req.hazard_scenario,
            targets=targets,
            weather=weather,
        )
        filtered = _filter_recommendations_by_hazard(
            hazard=req.hazard_scenario, recs=recs
        )
        note = (
            "当前无合适装备：模型与规则未能将现有设备匹配到目标；已返回按场景策略过滤后的推荐装备清单。"
        )
        return ReconPriorityPlanResponse(
            operational_period=period,
            assignments=parsed,
            plan_summary=note,
            no_suitable_equipment=True,
            recommendations=filtered,
        )

    return ReconPriorityPlanResponse(
        operational_period=period,
        assignments=parsed,
        plan_summary=plan_summary,
    )


def _hazard_policy(hazard: str) -> Tuple[Set[str], Set[str]]:
    """根据灾情返回(允许的装备类别, 核心能力标签)。

    - flood → (usv, water_recon/sonar/thermal_imaging)
    - chemical_leak → (robot_dog, hazmat_detection/gas_detection)
    - landslide → (uav, slope_monitoring/thermal_imaging)
    其余：放宽但仍返回一组合理的默认。
    """
    h = hazard.strip().lower()
    if h in {"flood", "flooding", "water"}:
        return {"usv"}, {"water_recon", "sonar", "thermal_imaging"}
    if h in {"chemical", "chemical_leak", "hazmat"}:
        return {"robot_dog"}, {"hazmat_detection", "gas_detection"}
    if h in {"landslide", "slope", "debris_flow"}:
        return {"uav"}, {"slope_monitoring", "thermal_imaging"}
    # 默认广域侦察
    return {"uav", "robot_dog", "usv"}, {"thermal_imaging"}


def _filter_recommendations_by_hazard(*, hazard: str, recs: List[RecommendedEquipment]) -> List[RecommendedEquipment]:
    """按场景策略过滤不合适的装备（不符合类别或缺少关键能力的剔除）。"""
    allowed_categories, required_caps = _hazard_policy(hazard)
    result: List[RecommendedEquipment] = []
    for r in recs:
        cat = r.category.strip().lower()
        caps = {c.strip().lower() for c in r.capabilities}
        if cat not in allowed_categories:
            continue
        if not caps & required_caps:
            continue
        result.append(r)
    return result


def _recommend_equipment_when_none(*, client: OpenAI, hazard: str, targets: List[Dict[str, Any]], weather: Dict[str, Any]) -> List[RecommendedEquipment]:
    """当没有可用装备时，请求 LLM 推荐装备（后续再按场景过滤）。"""
    allowed_categories, required_caps = _hazard_policy(hazard)
    sys_msg = (
        "你是应急侦察装备推荐官。根据灾情/目标/天气推荐 1-4 条装备类型，"
        "每条包含 category/capabilities/suggested_quantity/rationale/source。"
        "必须遵循：category 取自 {allowed} 的子集；capabilities 应包含或接近 {req_caps} 中的要点；"
        "仅输出 JSON 对象，不得添加未定义字段或自然语言解释。"
    ).format(allowed=sorted(allowed_categories), req_caps=sorted(required_caps))
    templ = {
        "recommended_equipment": [
            {
                "category": "usv|uav|robot_dog",
                "capabilities": ["water_recon", "sonar"],
                "suggested_quantity": 2,
                "rationale": "<string>",
                "source": "LLM(glm-4.6)+domain_rules({hazard})".format(hazard=hazard),
            }
        ]
    }
    payload = {
        "hazard_scenario": hazard,
        "targets": targets,
        "weather": weather,
        "policy": {
            "allowed_categories": sorted(allowed_categories),
            "required_capabilities": sorted(required_caps),
        },
    }
    messages = [
        {"role": "system", "content": sys_msg},
        {
            "role": "user",
            "content": (
                "仅输出 {\"recommended_equipment\":[{\"category\":\"\",\"capabilities\":[\"\"],\"suggested_quantity\":1,\"rationale\":\"\",\"source\":\"\"}]}\n"
                f"上下文：{json.dumps(payload, ensure_ascii=False)}\n模板：{json.dumps(templ, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        resp = client.chat.completions.create(
            model="glm-4.6",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        items = data.get("recommended_equipment") or []
        recs: List[RecommendedEquipment] = []
        for it in items:
            try:
                recs.append(
                    RecommendedEquipment(
                        category=str(it.get("category") or ""),
                        capabilities=[str(c) for c in (it.get("capabilities") or [])],
                        suggested_quantity=int(it.get("suggested_quantity") or 1),
                        rationale=str(it.get("rationale") or ""),
                        source=str(it.get("source") or f"LLM(glm-4.6)+domain_rules({hazard})"),
                    )
                )
            except Exception:
                # 略过坏条目，保持鲁棒，不影响主流程
                continue
        return recs
    except Exception as exc:  # pragma: no cover
        logger.error("recon_priority_recommend_llm_failed", error=str(exc))
        return []
