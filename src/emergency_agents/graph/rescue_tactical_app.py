
"""战术救援 LangGraph 子图，实现救援任务生成流程。"""

from __future__ import annotations

import asyncio
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph
from psycopg_pool import AsyncConnectionPool

from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.db.dao import (
    RescueDAO,
    RescueTaskRepository,
    serialize_dataclass,
)
from emergency_agents.db.models import (
    RescuerRecord,
    TaskCreateInput,
    TaskRoutePlanCreateInput,
)
from emergency_agents.external.amap_client import AmapClient, Coordinate, RoutePlan
from emergency_agents.external.orchestrator_client import (
    OrchestratorClient,
    OrchestratorClientError,
    RescueScenarioLocation,
    RescueScenarioPayload,
)
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
from emergency_agents.graph.kg_service import KGService
from emergency_agents.intent.schemas import RescueTaskGenerationSlots
from emergency_agents.rag.equipment_extractor import ExtractedEquipment, extract_equipment_from_cases
from emergency_agents.rag.evidence_builder import EquipmentRecommendation, build_equipment_recommendations
from emergency_agents.rag.pipe import RagPipeline, RagChunk

logger = structlog.get_logger(__name__)


class ResourceCandidate(TypedDict, total=False):
    resource_id: str
    name: str
    rescuer_type: str
    lng: float
    lat: float
    skills: List[str]
    equipment: Dict[str, Any]
    availability: bool
    status: str


class MatchedResource(TypedDict, total=False):
    resource_id: str
    name: str
    rescuer_type: str
    capability_match: str
    distance_km: float
    lack_reasons: List[str]
    equipment_summary: List[str]
    skills: List[str]
    eta_minutes: float
    cache_hit: bool
    route_id: str


class RoutePlanData(TypedDict, total=False):
    resource_id: str
    route_id: str
    distance_meters: int
    duration_seconds: int
    eta_minutes: float
    cache_hit: bool
    raw_plan: RoutePlan


class AnalysisSummary(TypedDict, total=False):
    kg_count: int
    rag_count: int
    matched_count: int
    unmatched_count: int
    cache_hits: int
    cache_misses: int


class RescueTacticalState(TypedDict, total=False):
    task_id: str
    user_id: str
    thread_id: str
    slots: RescueTaskGenerationSlots
    simulation_mode: bool
    status: str
    error: str
    resolved_location: Dict[str, Any]
    resources: List[ResourceCandidate]
    kg_requirements: List[Dict[str, Any]]
    rag_cases: List[Dict[str, Any]]
    rag_equipments: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    matched_resources: List[MatchedResource]
    unmatched_resources: List[MatchedResource]
    routes: List[RoutePlanData]
    ws_payload: Dict[str, Any]
    response_text: str
    recommendation: Dict[str, Any]
    analysis_summary: AnalysisSummary
    conversation_context: Dict[str, Any]
    incident_response: Optional[Dict[str, Any]]
    persisted_task: Dict[str, Any]
    persisted_routes: List[Dict[str, Any]]


class RescueTacticalGraph:
    """封装战术救援 LangGraph，可被 REST 或子图调用。"""

    def __init__(
        self,
        *,
        pool: AsyncConnectionPool,
        kg_service: KGService,
        rag_pipeline: RagPipeline,
        amap_client: AmapClient,
        llm_client: Any,
        llm_model: str,
        orchestrator: OrchestratorClient | None,
        rag_timeout: float,
        notify: bool = True,
        postgres_dsn: str,
        checkpoint_schema: str = "rescue_tactical_checkpoint",
        resource_dao: RescueDAO,
        task_repository: RescueTaskRepository,
    ) -> None:
        self._pool = pool
        self._kg_service = kg_service
        self._rag_pipeline = rag_pipeline
        self._amap_client = amap_client
        self._llm_client = llm_client
        self._llm_model = llm_model
        self._orchestrator = orchestrator
        self._rag_timeout = max(rag_timeout, 0.5)
        self._notify = notify
        if not postgres_dsn:
            raise ValueError("RescueTacticalGraph 需要 POSTGRES_DSN，当前未配置。")
        self._postgres_dsn = postgres_dsn
        self._checkpoint_schema = checkpoint_schema
        self._resource_dao = resource_dao
        self._task_repository = task_repository
        self._graph = self._build_graph()
        self._checkpointer: Optional[AsyncPostgresSaver] = None
        self._checkpoint_close: Optional[Callable[[], Awaitable[None]]] = None
        self._compiled: Optional[Any] = None

    @classmethod
    async def build(
        cls,
        *,
        pool: AsyncConnectionPool,
        kg_service: KGService,
        rag_pipeline: RagPipeline,
        amap_client: AmapClient,
        llm_client: Any,
        llm_model: str,
        orchestrator: OrchestratorClient | None,
        rag_timeout: float,
        notify: bool = True,
        postgres_dsn: str,
        checkpoint_schema: str = "rescue_tactical_checkpoint",
        resource_dao: Optional[RescueDAO] = None,
        task_repository: Optional[RescueTaskRepository] = None,
    ) -> "RescueTacticalGraph":
        """异步构建战术救援子图，绑定Postgres checkpointer。"""
        logger.info("rescue_tactical_graph_init", schema=checkpoint_schema)
        resource_dao = resource_dao or RescueDAO.create(pool)
        task_repository = task_repository or RescueTaskRepository.create(pool)
        instance = cls(
            pool=pool,
            kg_service=kg_service,
            rag_pipeline=rag_pipeline,
            amap_client=amap_client,
            llm_client=llm_client,
            llm_model=llm_model,
            orchestrator=orchestrator,
            rag_timeout=rag_timeout,
            notify=notify,
            postgres_dsn=postgres_dsn,
            checkpoint_schema=checkpoint_schema,
            resource_dao=resource_dao,
            task_repository=task_repository,
        )
        checkpointer, close_cb = await create_async_postgres_checkpointer(
            dsn=postgres_dsn,
            schema=checkpoint_schema,
            min_size=1,
            max_size=5,
        )
        instance._checkpointer = checkpointer
        instance._checkpoint_close = close_cb
        instance._compiled = instance._graph.compile(checkpointer=checkpointer)
        logger.info("rescue_tactical_graph_ready", schema=checkpoint_schema)
        return instance

    async def close(self) -> None:
        if self._checkpoint_close is not None:
            await self._checkpoint_close()
            self._checkpoint_close = None

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(RescueTacticalState)

        async def resolve_location(state: RescueTacticalState) -> Dict[str, Any]:
            slots = state["slots"]
            coordinates = slots.coordinates or {}
            if {"lng", "lat"} <= coordinates.keys():
                resolved = {
                    "name": slots.location_name or "目标区域",
                    "lng": float(coordinates["lng"]),
                    "lat": float(coordinates["lat"]),
                    "confidence": "user",
                }
                logger.info("rescue_location_resolved", source="user_coordinates", resolved=resolved)
                return {"status": "ok", "resolved_location": resolved}

            if slots.location_name:
                geocode = await self._amap_client.geocode(slots.location_name)
                if geocode:
                    resolved = {
                        "name": geocode["name"],
                        "lng": geocode["location"]["lng"],
                        "lat": geocode["location"]["lat"],
                        "confidence": "geocode",
                    }
                    logger.info("rescue_location_resolved", source="amap_geocode", resolved=resolved)
                    return {"status": "ok", "resolved_location": resolved}
                logger.warning("rescue_location_not_found", location=slots.location_name)
                return {"status": "error", "error": "未找到指定地点，请提供经纬度。"}
            return {"status": "error", "error": "缺少地点信息，请提供地名或经纬度。"}

        async def query_resources(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            records = await self._resource_dao.list_available_rescuers(limit=25)
            resources: List[ResourceCandidate] = []
            for record in records:
                candidate = _rescuer_to_candidate(record)
                if candidate is not None:
                    resources.append(candidate)

            if not resources:
                logger.error("rescue_resources_empty")
                return {"status": "error", "error": "当前无可用救援力量，请先录入资源。"}

            return {"resources": resources}

        async def kg_reasoning(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            slots = state["slots"]
            disaster_type = slots.disaster_type or "general_rescue"
            try:
                requirements = await asyncio.to_thread(
                    self._kg_service.get_equipment_requirements,
                    [disaster_type],
                )
            except Exception as exc:  # pragma: no cover
                logger.exception("kg_query_failed")
                return {"status": "error", "error": f"知识图谱查询失败：{exc}"}

            if len(requirements) < 3:
                logger.warning("kg_requirements_insufficient", count=len(requirements))
                return {
                    "status": "error",
                    "error": "缺少知识图谱支撑，无法生成救援任务。",
                    "kg_requirements": requirements,
                }
            return {"kg_requirements": requirements}

        async def rag_analysis(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            kg_requirements = state.get("kg_requirements") or []
            if not kg_requirements:
                return {"status": "error", "error": "缺少知识图谱支撑，无法进行案例分析。"}

            slots = state["slots"]
            disaster_type = slots.disaster_type or "general_rescue"
            mission = slots.mission_type or "rescue"
            summary_text = (slots.situation_summary or "").strip()
            if summary_text:
                query = f"{summary_text} {mission} {disaster_type} 历史案例 最佳实践"
            else:
                query = f"{mission} {disaster_type} 历史案例 最佳实践"

            try:
                rag_future = asyncio.to_thread(
                    self._rag_pipeline.query,
                    question=query,
                    domain="案例",
                    top_k=5,
                )
                rag_chunks: List[RagChunk] = await asyncio.wait_for(rag_future, timeout=self._rag_timeout)
            except Exception as exc:  # pragma: no cover
                logger.exception("rag_query_failed")
                return {"status": "error", "error": f"历史案例检索失败：{exc}"}

            if len(rag_chunks) < 2:
                logger.warning("rag_cases_insufficient", count=len(rag_chunks))
                summary = AnalysisSummary(
                    kg_count=len(kg_requirements),
                    rag_count=len(rag_chunks),
                    matched_count=0,
                    unmatched_count=0,
                    cache_hits=0,
                    cache_misses=0,
                )
                return {
                    "rag_cases": [chunk.__dict__ for chunk in rag_chunks],
                    "analysis_summary": summary,
                    "recommendations": [],
                    "rag_equipments": [],
                }

            try:
                extraction_future = asyncio.to_thread(
                    extract_equipment_from_cases,
                    rag_chunks,
                    self._llm_client,
                    self._llm_model,
                )
                extracted: List[ExtractedEquipment] = await asyncio.wait_for(extraction_future, timeout=self._rag_timeout)
            except Exception as exc:  # pragma: no cover
                logger.exception("rag_equipment_extraction_failed")
                extracted = []

            recommendations: List[EquipmentRecommendation] = []
            if extracted:
                try:
                    recommendation_future = asyncio.to_thread(
                        build_equipment_recommendations,
                        kg_requirements,
                        rag_chunks,
                        extracted,
                        [disaster_type],
                    )
                    recommendations = await asyncio.wait_for(recommendation_future, timeout=self._rag_timeout)
                except Exception as exc:  # pragma: no cover
                    logger.exception("equipment_recommendation_failed")
                    recommendations = []

            summary = AnalysisSummary(
                kg_count=len(kg_requirements),
                rag_count=len(rag_chunks),
                matched_count=0,
                unmatched_count=0,
                cache_hits=0,
                cache_misses=0,
            )

            return {
                "rag_cases": [chunk.__dict__ for chunk in rag_chunks],
                "rag_equipments": [equip.__dict__ for equip in extracted],
                "recommendations": [rec.to_dict() for rec in recommendations],
                "analysis_summary": summary,
            }

        async def match_resources(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            resources = state.get("resources") or []
            recommendations = state.get("recommendations") or []
            resolved = state.get("resolved_location")
            if not resources or not resolved:
                return {"status": "error", "error": "缺少可匹配的资源或定位信息。"}

            required = _required_equipment_set(recommendations)
            destination = Coordinate(lng=float(resolved["lng"]), lat=float(resolved["lat"]))
            matched: List[MatchedResource] = []
            unmatched: List[MatchedResource] = []

            for resource in resources:
                capability_match, lack_reasons = _evaluate_resource(resource, required)
                distance = _distance_km(
                    Coordinate(lng=resource["lng"], lat=resource["lat"]),
                    destination,
                )
                record = MatchedResource(
                    resource_id=resource["resource_id"],
                    name=resource.get("name", resource["resource_id"]),
                    rescuer_type=resource.get("rescuer_type", "unknown"),
                    capability_match=capability_match,
                    distance_km=distance,
                    lack_reasons=lack_reasons,
                    equipment_summary=_equipment_summary(resource),
                    skills=resource.get("skills", []),
                    eta_minutes=float("inf"),
                    cache_hit=False,
                    route_id="",
                )
                if capability_match == "none":
                    unmatched.append(record)
                else:
                    matched.append(record)

            summary = state.get("analysis_summary") or AnalysisSummary()
            summary["matched_count"] = len(matched)
            summary["unmatched_count"] = len(unmatched)

            if not matched:
                logger.warning("resource_match_empty")
                return {
                    "status": "error",
                    "error": "未匹配到合适的救援资源。",
                    "matched_resources": [],
                    "unmatched_resources": unmatched,
                    "analysis_summary": summary,
                }

            matched.sort(key=lambda item: (item["capability_match"] != "full", item["distance_km"]))
            return {
                "matched_resources": matched,
                "unmatched_resources": unmatched,
                "analysis_summary": summary,
            }

        async def route_planning(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            matched = state.get("matched_resources") or []
            if not matched:
                return {}
            destination = state.get("resolved_location")
            if not destination:
                return {}

            dest_coord = Coordinate(lng=float(destination["lng"]), lat=float(destination["lat"]))
            routes: List[RoutePlanData] = []
            updated_matched: List[MatchedResource] = []
            updated_unmatched = list(state.get("unmatched_resources") or [])
            summary = state.get("analysis_summary") or AnalysisSummary()
            cache_hits = summary.get("cache_hits", 0)
            cache_misses = summary.get("cache_misses", 0)

            for item in matched:
                resource = next(
                    (res for res in state.get("resources", []) if res["resource_id"] == item["resource_id"]),
                    None,
                )
                if resource is None:
                    continue
                origin = Coordinate(lng=resource["lng"], lat=resource["lat"])
                try:
                    plan = await self._amap_client.direction(origin=origin, destination=dest_coord, mode="driving")
                except Exception as exc:
                    reason = f"路径规划失败: {exc}"
                    logger.warning("amap_direction_failed", resource_id=item["resource_id"], error=str(exc))
                    failed = dict(item)
                    failed["capability_match"] = "none"
                    failed.setdefault("lack_reasons", []).append(reason)
                    updated_unmatched.append(failed)  # type: ignore[arg-type]
                    continue

                eta_minutes = plan["duration_seconds"] / 60 if plan["duration_seconds"] else float("inf")
                cache_hit = bool(plan.get("cache_hit"))
                if cache_hit:
                    cache_hits += 1
                else:
                    cache_misses += 1
                route_id = f"gaode:route:{item['resource_id']}:{uuid.uuid4()}"
                updated_item = dict(item)
                updated_item["eta_minutes"] = eta_minutes
                updated_item["cache_hit"] = cache_hit
                updated_item["route_id"] = route_id
                if plan["distance_meters"]:
                    updated_item["distance_km"] = plan["distance_meters"] / 1000
                updated_matched.append(updated_item)  # type: ignore[arg-type]
                routes.append(
                    RoutePlanData(
                        resource_id=item["resource_id"],
                        route_id=route_id,
                        distance_meters=plan["distance_meters"],
                        duration_seconds=plan["duration_seconds"],
                        eta_minutes=eta_minutes,
                        cache_hit=cache_hit,
                        raw_plan=plan,
                    )
                )

            summary["cache_hits"] = cache_hits
            summary["cache_misses"] = cache_misses

            if not updated_matched:
                return {
                    "status": "error",
                    "error": "路径规划失败，未找到可达的救援力量。",
                    "matched_resources": [],
                    "unmatched_resources": updated_unmatched,
                    "routes": routes,
                    "analysis_summary": summary,
                }

            updated_matched.sort(key=lambda item: (item["capability_match"] != "full", item["eta_minutes"]))
            return {
                "matched_resources": updated_matched,
                "unmatched_resources": updated_unmatched,
                "routes": routes,
                "analysis_summary": summary,
            }

        async def persist_task(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            if state.get("simulation_mode"):
                return {}
            auto_persist = bool(state.get("auto_persist", True))
            if not auto_persist:
                return {}
            matched = state.get("matched_resources") or []
            routes = state.get("routes") or []
            if not matched:
                return {}

            recommendation = matched[0]
            slots = state["slots"]
            mission_type = getattr(slots, "mission_type", None)
            task_type = _map_mission_type(mission_type)
            description = slots.situation_summary or f"调派 {recommendation.get('name', recommendation['resource_id'])} 执行救援任务"
            context = state.get("conversation_context") or {}
            incident_id = context.get("incident_id") or RESCUE_DEMO_INCIDENT_ID
            actor = state.get("user_id") or "system"
            origin_resource = next(
                (res for res in state.get("resources", []) if res.get("resource_id") == recommendation["resource_id"]),
                None,
            )
            task_input = TaskCreateInput(
                task_type=task_type,
                status="pending",
                priority=70,
                description=description,
                deadline=None,
                target_entity_id=None,
                event_id=incident_id,
                created_by=actor,
                updated_by=actor,
                code=state.get("task_id"),
            )
            try:
                task_record = await self._task_repository.create_task(task_input)
            except Exception as exc:  # pragma: no cover
                logger.error("rescue_task_persist_failed", error=str(exc))
                return {"status": "error", "error": f"任务写入失败：{exc}"}

            persisted_routes: List[Dict[str, Any]] = []
            selected_route = _select_route_for_resource(recommendation["resource_id"], routes)
            if selected_route is not None:
                origin_geojson = _point_geojson(
                    origin_resource.get("lng") if isinstance(origin_resource, dict) else None,
                    origin_resource.get("lat") if isinstance(origin_resource, dict) else None,
                )
                destination = state.get("resolved_location") or {}
                destination_geojson = _point_geojson(
                    destination.get("lng"),
                    destination.get("lat"),
                )
                eta_seconds = selected_route.get("duration_seconds")
                eta = None
                if isinstance(eta_seconds, int):
                    eta = datetime.now(timezone.utc) + timedelta(seconds=eta_seconds)
                route_input = TaskRoutePlanCreateInput(
                    task_id=task_record.id,
                    status="USED",
                    strategy="FASTEST",
                    origin_geojson=origin_geojson,
                    destination_geojson=destination_geojson,
                    polyline_geojson=None,
                    distance_meters=selected_route.get("distance_meters"),
                    duration_seconds=selected_route.get("duration_seconds"),
                    estimated_arrival_time=eta,
                    avoid_polygons=None,
                )
                try:
                    route_record = await self._task_repository.create_route_plan(route_input)
                    persisted_routes.append(serialize_dataclass(route_record))
                except Exception as exc:  # pragma: no cover
                    logger.warning("rescue_route_persist_failed", error=str(exc), task_id=task_record.id)

            return {
                "persisted_task": serialize_dataclass(task_record),
                "persisted_routes": persisted_routes,
            }

        async def prepare_response(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            matched = state.get("matched_resources") or []
            if not matched:
                return {}

            recommendation = matched[0]
            resolved = state.get("resolved_location") or {}
            summary = state.get("analysis_summary") or AnalysisSummary()
            persisted_task = state.get("persisted_task") or {}
            payload = {
                "type": "show_task_list",
                "taskId": persisted_task.get("id") or state.get("task_id"),
                "missionType": state["slots"].mission_type,
                "resolvedLocation": resolved,
                "items": [
                    {
                        "resourceId": item["resource_id"],
                        "resourceType": item.get("rescuer_type", "unknown"),
                        "etaMinutes": item["eta_minutes"],
                        "distanceKm": item["distance_km"],
                        "capabilityMatch": item["capability_match"],
                        "equipmentSummary": item.get("equipment_summary", []),
                        "lackReasons": item.get("lack_reasons", []),
                        "routeId": item.get("route_id"),
                    }
                    for item in matched
                ],
                "unmatched": [
                    {
                        "resourceId": item["resource_id"],
                        "resourceType": item.get("rescuer_type", "unknown"),
                        "lackReasons": item.get("lack_reasons", []),
                    }
                    for item in state.get("unmatched_resources") or []
                ],
                "recommendedId": recommendation["resource_id"],
            }

            lines: List[str] = []
            for item in matched:
                desc = (
                    f"{item['name']}（{item.get('rescuer_type', 'unknown')}）：ETA {item['eta_minutes']:.1f} 分钟，匹配度 {item['capability_match']}"
                )
                if item.get("lack_reasons"):
                    desc += f"，缺口：{'、'.join(item['lack_reasons'])}"
                lines.append(desc)

            if state.get("simulation_mode"):
                narrative = (
                    f"模拟结果：推荐调派 {recommendation['name']}，预计 {recommendation['eta_minutes']:.1f} 分钟抵达。"
                    f" 共评估 {summary.get('matched_count', 0)} 支力量，缺口说明："
                )
                if summary.get("unmatched_count"):
                    narrative += f"{summary['unmatched_count']} 支力量因装备不足或路径不可达未能匹配。"
                else:
                    narrative += "无明显缺口。"
                response_text = narrative
            else:
                response_text = "已生成推荐救援资源：\n" + "\n".join(lines)

            return {
                "ws_payload": payload,
                "response_text": response_text,
                "recommendation": recommendation,
                "analysis_summary": summary,
            }

        async def ws_notify(state: RescueTacticalState) -> Dict[str, Any]:
            if state.get("status") == "error":
                return {}
            if not self._notify or self._orchestrator is None:
                return {"incident_context": state.get("conversation_context") or {}}

            payload = state.get("ws_payload")
            if payload:
                intent_label = "rescue-task-generate" if not state.get("simulation_mode") else "rescue-simulation"
                logger.info(
                    "rescue_task_todo_notify",
                    intent=intent_label,
                    user_id=state.get("user_id"),
                    thread_id=state.get("thread_id"),
                    payload_keys=list(payload.keys()),
                )

            context: Dict[str, Any] = dict(state.get("conversation_context") or {})
            try:
                incident_id = context.get("incident_id") or RESCUE_DEMO_INCIDENT_ID
                context["incident_id"] = incident_id
                scenario_payload = _build_rescue_scenario_payload(state, incident_id, context)
                if scenario_payload is not None:
                    try:
                        scenario_response = self._orchestrator.publish_rescue_scenario(scenario_payload)
                        logger.info("rescue_scenario_publish_success", incident_id=incident_id, response=scenario_response)
                    except OrchestratorClientError as exc:
                        logger.warning("rescue_scenario_publish_failed", incident_id=incident_id, error=str(exc))
                return {
                    "incident_context": context,
                    "incident_response": None,
                }
            except OrchestratorClientError as exc:
                logger.error("rescue_incident_orchestrator_failed", error=str(exc))
                return {"status": "error", "error": str(exc)}

        graph.add_node("resolve_location", resolve_location)
        graph.add_node("query_resources", query_resources)
        graph.add_node("kg_reasoning", kg_reasoning)
        graph.add_node("rag_analysis", rag_analysis)
        graph.add_node("match_resources", match_resources)
        graph.add_node("route_planning", route_planning)
        graph.add_node("persist_task", persist_task)
        graph.add_node("prepare_response", prepare_response)
        graph.add_node("ws_notify", ws_notify)
        graph.set_entry_point("resolve_location")
        graph.add_edge("resolve_location", "query_resources")
        graph.add_edge("query_resources", "kg_reasoning")
        graph.add_edge("kg_reasoning", "rag_analysis")
        graph.add_edge("rag_analysis", "match_resources")
        graph.add_edge("match_resources", "route_planning")
        graph.add_edge("route_planning", "persist_task")
        graph.add_edge("persist_task", "prepare_response")
        if self._notify:
            graph.add_edge("prepare_response", "ws_notify")
            graph.add_edge("ws_notify", "__end__")
        else:
            graph.add_edge("prepare_response", "__end__")
        return graph

    async def invoke(self, state: RescueTacticalState) -> RescueTacticalState:
        if self._compiled is None:
            raise RuntimeError("RescueTacticalGraph 尚未初始化完成")
        return await self._compiled.ainvoke(
            state,
            config={"configurable": {"thread_id": state["thread_id"]}},
        )


async def build_rescue_tactical_graph(
    *,
    pool: AsyncConnectionPool,
    kg_service: KGService,
    rag_pipeline: RagPipeline,
    amap_client: AmapClient,
    llm_client: Any,
    llm_model: str,
    orchestrator: OrchestratorClient | None,
    rag_timeout: float,
    notify: bool = True,
    postgres_dsn: str,
    checkpoint_schema: str = "rescue_tactical_checkpoint",
) -> RescueTacticalGraph:
    return await RescueTacticalGraph.build(
        pool=pool,
        kg_service=kg_service,
        rag_pipeline=rag_pipeline,
        amap_client=amap_client,
        llm_client=llm_client,
        llm_model=llm_model,
        orchestrator=orchestrator,
        rag_timeout=rag_timeout,
        notify=notify,
        postgres_dsn=postgres_dsn,
        checkpoint_schema=checkpoint_schema,
        resource_dao=RescueDAO.create(pool),
        task_repository=RescueTaskRepository.create(pool),
    )


def _distance_km(origin: Coordinate, destination: Coordinate) -> float:
    lat1, lon1 = origin["lat"], origin["lng"]
    lat2, lon2 = destination["lat"], destination["lng"]
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _equipment_summary(resource: ResourceCandidate) -> List[str]:
    names: List[str] = []
    equipment_data = resource.get("equipment")
    if isinstance(equipment_data, dict):
        for key, value in equipment_data.items():
            names.append(str(key).lower())
            if isinstance(value, str):
                names.append(value.lower())
            elif isinstance(value, list):
                names.extend(str(item).lower() for item in value)
    return names


def _required_equipment_set(recommendations: List[Dict[str, Any]]) -> set[str]:
    required: set[str] = set()
    for rec in recommendations:
        items = rec.get("required_equipment") or rec.get("matched_equipment")
        if isinstance(items, list):
            required.update(str(item).lower() for item in items)
    return required


def _rescuer_to_candidate(record: RescuerRecord) -> Optional[ResourceCandidate]:
    if record.lng is None or record.lat is None:
        return None
    return ResourceCandidate(
        resource_id=record.rescuer_id,
        name=record.name,
        rescuer_type=record.rescuer_type,
        lng=record.lng,
        lat=record.lat,
        skills=list(record.skills),
        equipment=dict(record.equipment),
        availability=record.availability,
        status=record.status or "unknown",
    )


def _map_mission_type(mission_type: Optional[str]) -> str:
    normalized = (mission_type or "").strip().lower()
    mapping = {
        "rescue": "rescue_target",
        "rescue_target": "rescue_target",
        "material": "material_transport",
        "material_transport": "material_transport",
        "transport": "material_transport",
        "recon": "uav_recon",
        "reconnaissance": "uav_recon",
        "perimeter": "set_perimeter",
        "assessment": "damage_assessment",
    }
    return mapping.get(normalized, "rescue_target")


def _select_route_for_resource(resource_id: str, routes: List[RoutePlanData]) -> Optional[RoutePlanData]:
    for route in routes:
        if route.get("resource_id") == resource_id:
            return route
    return routes[0] if routes else None


def _point_geojson(lng: Any, lat: Any) -> Optional[Dict[str, Any]]:
    try:
        lon = float(lng)
        lat_value = float(lat)
    except (TypeError, ValueError):
        return None
    return {"type": "Point", "coordinates": [lon, lat_value]}


def _evaluate_resource(resource: ResourceCandidate, required: set[str]) -> Tuple[str, List[str]]:
    equipment = set(_equipment_summary(resource))
    if not required:
        return ("partial", [])
    missing = sorted(required - equipment)
    if not missing:
        return ("full", [])
    if len(missing) < len(required):
        return ("partial", missing)
    return ("none", missing)


def _safe_float(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _build_rescue_scenario_payload(
    state: RescueTacticalState,
    incident_id: str,
    context: Dict[str, Any],
) -> Optional[RescueScenarioPayload]:
    slots = state["slots"]
    resolved = state.get("resolved_location") or {}
    longitude = _safe_float(resolved.get("lng") or resolved.get("longitude"))
    latitude = _safe_float(resolved.get("lat") or resolved.get("latitude"))
    if longitude is None or latitude is None:
        coordinates = getattr(slots, "coordinates", None)
        if isinstance(coordinates, dict):
            longitude = longitude or _safe_float(coordinates.get("lng") or coordinates.get("longitude"))
            latitude = latitude or _safe_float(coordinates.get("lat") or coordinates.get("latitude"))
    if longitude is None or latitude is None:
        return None

    location_name = (
        resolved.get("name")
        or getattr(slots, "location_name", None)
        or context.get("incident_title")
        or "救援现场"
    )
    location = RescueScenarioLocation(longitude=longitude, latitude=latitude, name=str(location_name))

    response_text = state.get("response_text")
    if not isinstance(response_text, str) or not response_text.strip():
        response_text = "已生成救援方案，请注意调度力量。"

    matched_resources = state.get("matched_resources") or []
    summary_lines: List[str] = []
    for item in matched_resources or []:
        name = item.get("name") or item.get("resource_id")
        rescuer_type = item.get("rescuer_type") or "unknown"
        eta_minutes = item.get("eta_minutes")
        line = f"{name}（{rescuer_type}）"
        if isinstance(eta_minutes, (int, float)):
            line += f" ETA {eta_minutes:.1f} 分钟"
        lack = item.get("lack_reasons") or []
        if lack:
            line += f"，缺口：{'、'.join(lack)}"
        summary_lines.append(line)

    content = response_text + ("\n" + "\n".join(summary_lines) if summary_lines else "")
    hazards: List[str] = []
    disaster_type = getattr(state["slots"], "disaster_type", None)
    if disaster_type:
        hazards.append(str(disaster_type))

    return RescueScenarioPayload(
        event_id=incident_id,
        location=location,
        title=context.get("incident_title") or "救援方案",
        content=content,
        hazards=hazards or None,
        scope=["commander"],
    )
