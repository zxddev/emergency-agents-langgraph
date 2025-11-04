from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

import json
import math
import os
import time
import itertools
import logging

from fastapi import APIRouter, HTTPException, Request
from anyio import to_thread
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import DictRow
from pydantic import BaseModel, Field, ValidationError

from emergency_agents.planner import (
    HazardPackLoader,
    ResourceMatcher,
    RescueTaskPlanRequest as PlannerTaskPlanRequest,
    TaskTemplateEngine,
)
from emergency_agents.planner.models import (
    GeoPoint as PlannerGeoPoint,
    PlannedMission,
    ResourceCandidate,
    ResourcePlanningResult,
)
from emergency_agents.external.recon_gateway import PostgresReconGateway
from emergency_agents.planner.recon_models import ReconDevice


# =============================
# 强类型数据模型（Pydantic）
# =============================


class GeoPoint(BaseModel):
    """经纬度点位，WGS84 坐标。"""

    lon: float = Field(..., ge=-180.0, le=180.0, description="经度")
    lat: float = Field(..., ge=-90.0, le=90.0, description="纬度")


class IncidentModel(BaseModel):
    """事件基本信息。"""

    id: str = Field(..., description="事件ID（UUID 字符串）")
    type: Literal["rescue", "recon"] = Field(..., description="事件大类")
    coords: GeoPoint = Field(..., description="事件位置（中心点）")
    severity: Optional[int] = Field(None, ge=0, le=100, description="严重程度(0-100)")
    hazards: List[str] = Field(default_factory=list, description="已识别风险标签，如 collapse/flood/fire 等")
    victims_estimate: Optional[int] = Field(None, ge=0, description="被困人数估计")


class UnitModel(BaseModel):
    """候选执行单元（救援队/无人机/机器人等）。"""

    id: str
    name: Optional[str] = None
    kind: Literal["rescue_team", "uav", "robotic_dog", "usv", "other"] = "rescue_team"
    capabilities: List[str] = Field(default_factory=list)
    speed_kmh: Optional[float] = Field(None, ge=0)
    location: GeoPoint
    available: bool = True


class ConstraintsModel(BaseModel):
    """规划约束（简化形态，后续可扩展为禁飞区/道路阻断等多边形）。"""

    weather: Optional[str] = Field(None, description="天气摘要，如 heavy_rain/strong_wind")
    aftershock_risk: Optional[bool] = None
    roads_blocked: Optional[bool] = None
    no_fly: Optional[bool] = None


class PlanRecommendRequest(BaseModel):
    incident: IncidentModel
    units: List[UnitModel]
    constraints: ConstraintsModel = Field(default_factory=ConstraintsModel)
    max_teams: int = Field(3, ge=1, le=10)


class Assignment(BaseModel):
    unit_id: str
    role: Literal["primary", "support"] = "primary"
    task: Literal["rescue", "recon", "support"] = "rescue"
    target: str = Field(..., description="目标标识，默认传事件ID")


class COA(BaseModel):
    label: str
    teams: List[str]
    assignments: List[Assignment]


class Justification(BaseModel):
    summary: str
    factors: List[Dict[str, Any]]
    references: List[Dict[str, Any]]


class PlanRecommendResponse(BaseModel):
    coas: Dict[str, COA]
    recommend: str
    justification: Justification
    constraints_applied: ConstraintsModel
    explain_mode: Literal["primary", "fallback"] = "primary"


router = APIRouter(prefix="/ai/plan", tags=["ai-plan"])

logger = logging.getLogger(__name__)

_HAZARD_LOADER = HazardPackLoader()
_TASK_ENGINE = TaskTemplateEngine()
_RESOURCE_MATCHER = ResourceMatcher()

# 依赖注入: 由 main.py 在startup时写入
_pg_pool_async: Optional[AsyncConnectionPool[DictRow]] = None
_recon_gateway: Optional[PostgresReconGateway] = None


# =============================
# 纯函数：评分与距离
# =============================


def _haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """球面距离（公里）。"""

    r: float = 6371.0
    d_lat: float = math.radians(b.lat - a.lat)
    d_lon: float = math.radians(b.lon - a.lon)
    lat1: float = math.radians(a.lat)
    lat2: float = math.radians(b.lat)
    h: float = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * (math.sin(d_lon / 2) ** 2)
    )
    return 2 * r * math.asin(math.sqrt(h))


def _capability_score(hazards: List[str], capabilities: List[str]) -> float:
    """基于危害标签与能力标签的简单匹配分数。"""

    if not hazards:
        return 0.0
    caps = {c.strip().lower() for c in capabilities}
    score: float = 0.0
    for hz in hazards:
        h = hz.strip().lower()
        if h in caps:
            score += 1.0
        # 常见语义映射
        if h == "collapse" and ("urban_search" in caps or "usarl" in caps):
            score += 0.5
        if h == "flood" and ("water_rescue" in caps or "usv" in caps):
            score += 0.5
        if h == "fire" and ("firefighting" in caps):
            score += 0.5
    return score


def _score_unit(incident: IncidentModel, u: UnitModel, constraints: ConstraintsModel) -> Tuple[float, Dict[str, Any]]:
    """计算单元综合分：能力匹配 + 距离倒数 + 可用性，返回(分数, 因子)。"""

    p_inc: GeoPoint = incident.coords
    dist_km: float = _haversine_km(p_inc, u.location)
    dist_score: float = 0.0 if dist_km <= 0 else 1.0 / dist_km
    cap_score: float = _capability_score(incident.hazards, u.capabilities)
    avail_score: float = 1.0 if u.available else 0.0

    # 天气/禁飞等简单折扣
    penalty: float = 0.0
    if constraints.no_fly and u.kind in ("uav",):
        penalty += 1.0
    if constraints.roads_blocked and u.kind == "rescue_team":
        penalty += 0.2

    # 线性权重（可配置）
    alpha: float = 0.6  # 能力
    beta: float = 0.3   # 距离
    gamma: float = 0.2  # 可用性
    score: float = alpha * cap_score + beta * dist_score + gamma * avail_score - penalty

    factors: Dict[str, Any] = {
        "unit_id": u.id,
        "distance_km": round(dist_km, 3),
        "distance_score": round(dist_score, 3),
        "capability_score": round(cap_score, 3),
        "availability": u.available,
        "penalty": round(penalty, 3),
        "weights": {"alpha": alpha, "beta": beta, "gamma": gamma},
    }
    return score, factors


def _rank_units(req: PlanRecommendRequest) -> List[Tuple[float, UnitModel, Dict[str, Any]]]:
    """为全部候选单位打分并按降序排列。"""

    ranked: List[Tuple[float, UnitModel, Dict[str, Any]]] = []
    for unit in req.units:
        score, factor = _score_unit(req.incident, unit, req.constraints)
        enriched = dict(factor)
        enriched["score"] = round(score, 3)
        ranked.append((score, unit, enriched))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def _generate_coa_indices(
    ranked: List[Tuple[float, UnitModel, Dict[str, Any]]],
    max_teams: int,
    max_plans: int = 3,
) -> List[Tuple[int, ...]]:
    """生成若干套分数最高的队伍组合。"""

    if max_teams <= 0:
        return []

    candidate_count = min(len(ranked), max_teams + 2)
    if candidate_count < max_teams:
        return []

    combos = list(itertools.combinations(range(candidate_count), max_teams))
    combos.sort(key=lambda combo: sum(ranked[i][0] for i in combo), reverse=True)
    return combos[:max_plans]


def _build_coa(
    label: str,
    indices: Tuple[int, ...],
    ranked: List[Tuple[float, UnitModel, Dict[str, Any]]],
    incident: IncidentModel,
) -> Tuple[COA, List[Dict[str, Any]]]:
    """根据指定索引组合生成 COA 与因子列表。"""

    selected = sorted(indices, key=lambda idx: ranked[idx][0], reverse=True)
    teams: List[str] = []
    assignments: List[Assignment] = []
    factors: List[Dict[str, Any]] = []

    for rank, idx in enumerate(selected):
        score, unit, factor = ranked[idx]
        teams.append(unit.id)
        assignments.append(
            Assignment(
                unit_id=unit.id,
                role="primary" if rank == 0 else "support",
                task="rescue" if incident.type == "rescue" else "recon",
                target=incident.id,
            )
        )
        enriched_factor = dict(factor)
        enriched_factor["coa"] = label
        enriched_factor["unit_rank"] = rank + 1
        factors.append(enriched_factor)

    return COA(label=label, teams=teams, assignments=assignments), factors


def _write_audit_file(incident_id: str, payload: Dict[str, Any]) -> None:
    """写审计文件，便于追溯（不抛异常）。"""

    try:
        ts: int = int(time.time())
        base_dir: str = os.getenv("AGENTS_PLAN_AUDIT_DIR", "temp")
        os.makedirs(base_dir, exist_ok=True)
        path: str = os.path.join(base_dir, f"plan_{incident_id}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # 审计失败不影响业务返回
        pass


@router.post("/recommend", response_model=PlanRecommendResponse)
def recommend_plan(req: PlanRecommendRequest) -> PlanRecommendResponse:
    """生成结构化救援/侦察方案（强类型，返回非空）。

    - 输入：事件 + 候选单元 + 约束
    - 策略：基于能力匹配/距离/可用性的线性评分，选取前N个队伍
    - 产出：COA-A（默认）+ 详细因子与引用，满足“可解释/可审计”
    """

    try:
        # pydantic 校验已完成，这里只进行显式业务校验
        if not req.units:
            logger.info(
                "plan_recommend_units_missing",
                extra={
                    "incident_id": req.incident.id,
                    "incident_type": req.incident.type,
                },
            )
            empty_response = PlanRecommendResponse(
                coas={"A": COA(label="COA-A", teams=[], assignments=[])},
                recommend="A",
                justification=Justification(
                    summary="未检测到可用救援单元，请补录救援队伍或检查数据源后重试。",
                    factors=[],
                    references=[
                        {"type": "diagnostic", "items": ["missing_units"]},
                        {"type": "incident", "items": [req.incident.id]},
                    ],
                ),
                constraints_applied=req.constraints,
                explain_mode="fallback",
            )
            _write_audit_file(
                req.incident.id,
                {
                    "incident": req.incident.model_dump(),
                    "selected": empty_response.model_dump(),
                },
            )
            return empty_response
    except ValidationError as e:  # pragma: no cover - FastAPI会先行处理
        raise HTTPException(status_code=422, detail=str(e)) from e

    ranked_units = _rank_units(req)
    coa_indices = _generate_coa_indices(ranked_units, req.max_teams, max_plans=3)
    if not coa_indices:
        raise HTTPException(status_code=400, detail="队伍数量不足以生成 COA")

    coas: Dict[str, COA] = {}
    justification_factors: List[Dict[str, Any]] = []
    labels = ["A", "B", "C"]
    for label, indices in zip(labels, coa_indices):
        coa, factors = _build_coa(label, indices, ranked_units, req.incident)
        coas[label] = coa
        justification_factors.extend(factors)

    recommend_label = next(iter(coas.keys()))
    justification = Justification(
        summary=(
            "生成多套救援方案，默认推荐 COA-A（综合能力匹配、距离、可用性）；"
            "COA-B、COA-C 提供备选队伍，可在面板中人工调度。"
        ),
        factors=justification_factors,
        references=[
            {"type": "hazards", "items": req.incident.hazards},
            {"type": "constraints", "items": req.constraints.model_dump()},
        ],
    )

    response = PlanRecommendResponse(
        coas=coas,
        recommend=recommend_label,
        justification=justification,
        constraints_applied=req.constraints,
        explain_mode="primary",
    )

    _write_audit_file(
        req.incident.id,
        {
            "incident": req.incident.model_dump(),
            "selected": response.model_dump(),
        },
    )

    logger.info(
        "plan_recommend_scored_units",
        extra={
            "incident_id": req.incident.id,
            "incident_type": req.incident.type,
            "units_requested": len(req.units),
            "units_selected": len(coas[recommend_label].teams),
            "team_ids": coas[recommend_label].teams,
        },
    )

    logger.info(
        "plan_recommend_response_built",
        extra={
            "incident_id": req.incident.id,
            "incident_type": req.incident.type,
            "plan_labels": list(coas.keys()),
            "explain_mode": response.explain_mode,
        },
    )

    return response


# =============================
# 基于任务进度生成救援方案(专业版)
# =============================


class FromProgressRequest(BaseModel):
    incident_id: str = Field(..., description="事件ID (UUID)")
    time_range_hours: int = Field(24, ge=1, le=168, description="统计范围(小时)")


class OperationalPeriod(BaseModel):
    start_iso: str
    end_iso: str


class FromProgressResponse(PlanRecommendResponse):
    plan_summary: str
    operational_period: OperationalPeriod


def _centroid_from_geometry(geometry: Dict[str, Any]) -> GeoPoint:
    """从GeoJSON几何计算近似中心点。"""
    gtype = str(geometry.get("type") or "").lower()
    if gtype == "point":
        coords = geometry.get("coordinates") or []
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            return GeoPoint(lon=float(coords[0]), lat=float(coords[1]))
    coords_list: List[Tuple[float, float]] = []
    if gtype in {"polygon", "multipolygon"}:
        def _collect(o: Any) -> None:
            if isinstance(o, (list, tuple)):
                if len(o) == 2 and all(isinstance(v, (int, float)) for v in o):
                    coords_list.append((float(o[0]), float(o[1])))
                else:
                    for item in o:
                        _collect(item)
        _collect(geometry.get("coordinates"))
    if coords_list:
        lon = sum(p[0] for p in coords_list) / len(coords_list)
        lat = sum(p[1] for p in coords_list) / len(coords_list)
        return GeoPoint(lon=lon, lat=lat)
    raise ValueError("geometry 无法计算中心点")


async def _incident_center(incident_id: str, pool: AsyncConnectionPool[DictRow]) -> GeoPoint:
    from emergency_agents.db.dao import IncidentDAO
    dao = IncidentDAO.create(pool)
    details = await dao.list_entities_with_details(incident_id)
    for item in details:
        ent_type = (item.entity.entity_type or "").lower()
        if ent_type in {"event_point", "event_range", "markup_point", "markup_polygon"}:
            return _centroid_from_geometry(dict(item.entity.geometry_geojson))
    raise ValueError("事件缺少几何实体(需要event_point或event_range)")


def _map_device_to_unit(device: ReconDevice) -> UnitModel:
    kind_map: Dict[str, str] = {
        "uav": "uav",
        "robot_dog": "robotic_dog",
        "usv": "usv",
        "sensor": "other",
        "other": "other",
    }
    location = device.location or PlannerGeoPoint(lon=0.0, lat=0.0)
    return UnitModel(
        id=device.device_id,
        name=device.name,
        kind=kind_map.get(device.category, "other"),
        capabilities=device.capabilities,
        speed_kmh=None,
        location=GeoPoint(lon=location.lon, lat=location.lat),
        available=device.available,
    )


@router.post("/from-progress", response_model=FromProgressResponse)
async def generate_plan_from_progress(req: FromProgressRequest, request: Request) -> FromProgressResponse:
    """根据任务进度与可用资源,生成下一个作战周期的救援方案(专业版)。"""
    if _pg_pool_async is None:
        raise HTTPException(status_code=503, detail="pg pool unavailable")
    if _recon_gateway is None:
        raise HTTPException(status_code=503, detail="recon gateway unavailable")

    # 1) 计算作战周期与事件中心
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    start_iso = (now).isoformat()
    end_iso = (now + timedelta(hours=12)).isoformat()
    logger.info(
        "from_progress_start",
        extra={
            "incident_id": req.incident_id,
            "time_range_hours": req.time_range_hours,
        },
    )
    try:
        center = await _incident_center(req.incident_id, _pg_pool_async)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"incident geometry missing: {exc}")

    # 2) 加载任务进度(按事件)
    from emergency_agents.db.dao import TaskDAO
    task_dao = TaskDAO.create(_pg_pool_async)
    try:
        # 事件过滤查询(若无则抛400)
        tasks = await task_dao.list_tasks_by_event(req.incident_id, req.time_range_hours)  # type: ignore[attr-defined]
    except AttributeError:
        # DAO版本不支持该方法
        raise HTTPException(status_code=500, detail="TaskDAO.list_tasks_by_event 未实现")

    if not tasks:
        raise HTTPException(status_code=400, detail="事件无任务进度,无法生成救援方案")

    # 3) 设备资源(基于事件上下文),避免阻塞事件循环,放入线程调用
    try:
        devices: List[ReconDevice] = await to_thread.run_sync(
            lambda: _recon_gateway.fetch_available_devices(req.incident_id)  # type: ignore[union-attr]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"设备加载失败: {exc}")
    units: List[UnitModel] = [_map_device_to_unit(d) for d in devices if d.available]
    if not units:
        raise HTTPException(status_code=400, detail="无可用救援单元,无法生成救援方案")

    # 4) 生成COA方案(复用已实现逻辑)
    incident = IncidentModel(
        id=req.incident_id,
        type="rescue",
        coords=center,
        severity=None,
        hazards=[],
    )
    rec_req = PlanRecommendRequest(
        incident=incident,
        units=units,
        constraints=ConstraintsModel(),
        max_teams=min(3, len(units)),
    )
    rec: PlanRecommendResponse = recommend_plan(rec_req)

    # 5) 方案摘要(中文)
    co = rec.coas.get(rec.recommend)
    top_units = ", ".join(co.teams[:3]) if co else ""
    in_progress = [t for t in tasks if (t.status or "").lower() in {"in_progress", "running"}]
    blocked = [t for t in tasks if (t.status or "").lower() in {"blocked", "on_hold"}]
    plan_summary = (
        f"作战周期: {start_iso} → {end_iso}\n"
        f"作战目标: 聚焦恢复进行中任务{len(in_progress)}个, 清理阻塞{len(blocked)}个; 建立安全/通信基线.\n"
        f"建议投入: {top_units or '待定'}\n"
        f"任务总览: 近{req.time_range_hours}小时内共{len(tasks)}个任务样本, 进行中{len(in_progress)}, 阻塞{len(blocked)}."
    )

    resp = FromProgressResponse(
        coas=rec.coas,
        recommend=rec.recommend,
        justification=rec.justification,
        constraints_applied=rec.constraints_applied,
        explain_mode=rec.explain_mode,
        plan_summary=plan_summary,
        operational_period=OperationalPeriod(start_iso=start_iso, end_iso=end_iso),
    )
    logger.info(
        "from_progress_completed",
        extra={
            "incident_id": req.incident_id,
            "teams": len(rec.coas.get(rec.recommend).teams) if rec.coas.get(rec.recommend) else 0,
            "tasks_total": len(tasks),
        },
    )
    return resp


# =============================
# 多灾种任务规划入口
# =============================


class ResourceCandidatePayload(ResourceCandidate):
    """复用规划模块的数据结构，保持JSON字段一致。"""

    pass


class MultiHazardPlanRequest(BaseModel):
    """多灾种规划请求。"""

    incident_id: str = Field(..., description="事件ID (UUID)")
    hazard_type: str = Field(..., description="灾种标识，如 bridge_collapse")
    severity_score: float = Field(60.0, ge=0.0, le=100.0, description="严重程度评分")
    hazard_version: Optional[str] = Field(None, description="知识包版本号")
    incident_point: Optional[PlannerGeoPoint] = None
    candidates: List[ResourceCandidatePayload] = Field(..., min_length=1)
    metadata: Dict[str, str] = Field(default_factory=dict)


class MultiHazardPlanResponse(BaseModel):
    """多灾种规划响应。"""

    plan: PlannerTaskPlanRequest
    unmatched_tasks: List[str]
    unused_resources: List[str]


@router.post("/multi-hazard", response_model=MultiHazardPlanResponse)
def generate_multi_hazard_plan(req: MultiHazardPlanRequest) -> MultiHazardPlanResponse:
    """加载知识包→生成任务树→匹配资源。"""

    try:
        pack = _HAZARD_LOADER.load_pack(req.hazard_type, req.hazard_version)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"hazard pack invalid: {exc}") from exc

    mission: PlannedMission = _TASK_ENGINE.build_plan(pack, req.severity_score)
    planning: ResourcePlanningResult = _RESOURCE_MATCHER.match(
        mission.tasks,
        req.candidates,
        incident_point=req.incident_point,
    )
    plan_request: PlannerTaskPlanRequest = PlannerTaskPlanRequest.from_plan(
        incident_id=req.incident_id,
        mission=mission,
        resource_matches=planning.matches,
        metadata=req.metadata,
    )

    logger.info(
        "multi_hazard_plan_generated",
        extra={
            "incident_id": req.incident_id,
            "hazard_type": req.hazard_type,
            "severity": req.severity_score,
            "task_count": len(mission.tasks),
            "match_count": len(planning.matches),
            "unmatched": planning.unmatched_tasks,
        },
    )

    return MultiHazardPlanResponse(
        plan=plan_request,
        unmatched_tasks=planning.unmatched_tasks,
        unused_resources=planning.unused_resources,
    )
