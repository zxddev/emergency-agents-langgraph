from __future__ import annotations

import asyncio
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, TypedDict, cast, Literal

import structlog
from psycopg_pool import AsyncConnectionPool

from emergency_agents.db.dao import IncidentDAO, IncidentRepository
from emergency_agents.db.models import (
    IncidentEntityCreateInput,
    IncidentEntityDetail,
    RiskZoneRecord,
)
from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.kg_service import KGService
from emergency_agents.graph.rescue_tactical_app import (
    AnalysisSummary,
    RescueTacticalGraph,
    RescueTacticalState,
    build_rescue_tactical_graph,
)
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import RescueTaskGenerationSlots
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.services import RescueDraftService
from emergency_agents.ui.actions import (
    camera_fly_to,
    focus_entity,
    open_panel,
    serialize_actions,
    show_risk_warning,
    show_toast,
)
from emergency_agents.risk.service import RiskCacheManager

logger = structlog.get_logger(__name__)


class RescuePlanOverview(TypedDict, total=False):
    taskId: str
    incidentId: str
    situationSummary: str
    missionType: Optional[str]
    location: Dict[str, Any]
    riskOutline: Optional[str]
    analysis: AnalysisSummary
    recommendedResourceId: Optional[str]


class RescuePlanLine(TypedDict, total=False):
    lineId: str
    title: str
    primaryResourceId: Optional[str]
    etaMinutes: Optional[float]
    route: Dict[str, Any]
    objectives: List[str]


class RescuePlanResourceEntry(TypedDict, total=False):
    resourceId: str
    resourceType: Literal["team", "equipment"]
    name: str
    capabilityMatch: Optional[str]
    etaMinutes: Optional[float]
    distanceKm: Optional[float]
    recommendedQuantity: Optional[int]
    reasoning: Optional[str]
    confidenceLevel: Optional[str]
    lackReasons: List[str]
    evidenceIds: List[str]
    attributes: Dict[str, Any]


class RescuePlanRiskEntry(TypedDict, total=False):
    zoneId: str
    zoneName: str
    hazardType: str
    severity: Optional[str]
    description: Optional[str]
    validFrom: Optional[str]
    validUntil: Optional[str]
    geometry: Dict[str, Any]


class RescuePlanEvidenceEntry(TypedDict, total=False):
    evidenceId: str
    category: Literal["kg", "rag", "recommendation"]
    source: str
    summary: str
    confidence: Optional[float]
    relatedResourceId: Optional[str]


class RescuePlanRouteWarning(TypedDict, total=False):
    zoneId: str
    hazardType: str
    severity: Optional[str]
    message: str
    distanceKm: Optional[float]
    resourceIds: List[str]


class RescuePlan(TypedDict):
    overview: RescuePlanOverview
    lines: List[RescuePlanLine]
    resources: List[RescuePlanResourceEntry]
    risks: List[RescuePlanRiskEntry]
    evidenceTrace: List[RescuePlanEvidenceEntry]
    routeWarnings: List[RescuePlanRouteWarning]


@dataclass
class RescueTaskGenerationHandler(IntentHandler[RescueTaskGenerationSlots]):
    pool: AsyncConnectionPool
    kg_service: KGService
    rag_pipeline: RagPipeline
    amap_client: AmapClient
    llm_client: Any
    llm_model: str
    orchestrator_client: OrchestratorClient | None
    rag_timeout: float
    postgres_dsn: str

    def __post_init__(self) -> None:
        self._graph: Optional[RescueTacticalGraph] = None
        self._graph_lock = asyncio.Lock()
        self._incident_repository: IncidentRepository = IncidentRepository.create(self.pool)
        self._incident_dao: IncidentDAO = IncidentDAO.create(self.pool)
        self._risk_cache: RiskCacheManager | None = None
        self._draft_service: RescueDraftService | None = None
        self._simple_graph: Any | None = None
        self._simple_graph_lock = asyncio.Lock()
        self._legacy_fallback_enabled: bool = False

    async def _ensure_graph(self, notify: bool) -> RescueTacticalGraph:
        if self._graph is not None:
            return self._graph
        async with self._graph_lock:
            if self._graph is None:
                self._graph = await build_rescue_tactical_graph(
                    pool=self.pool,
                    kg_service=self.kg_service,
                    rag_pipeline=self.rag_pipeline,
                    amap_client=self.amap_client,
                    llm_client=self.llm_client,
                    llm_model=self.llm_model,
                    orchestrator=self.orchestrator_client,
                    rag_timeout=self.rag_timeout,
                    notify=notify,
                    postgres_dsn=self.postgres_dsn,
                )
        return self._graph

    async def aclose(self) -> None:
        if self._graph is not None:
            await self._graph.close()
            self._graph = None

    def attach_risk_cache(self, risk_cache: RiskCacheManager | None) -> None:
        """记录共享风险缓存，供日志与计划生成复用。"""
        self._risk_cache = risk_cache

    def attach_draft_service(self, draft_service: RescueDraftService | None) -> None:
        """挂载救援方案草稿服务。"""
        self._draft_service = draft_service

    def attach_simple_graph(self, graph: Any | None) -> None:
        """注入简化救援子图。"""
        self._simple_graph = graph

    def set_legacy_fallback(self, enabled: bool) -> None:
        """控制是否允许回退到完整战术子图。"""
        self._legacy_fallback_enabled = bool(enabled)

    def _determine_entity_source(self, metadata: Mapping[str, Any]) -> str:
        source_raw = str(metadata.get("source", "")).lower()
        if source_raw in {"manual", "voice"}:
            return "manual"
        return "system"

    def _point_geometry(self, lng: float, lat: float) -> Dict[str, Any]:
        return {
            "type": "Point",
            "coordinates": [float(lng), float(lat)],
        }

    async def _create_rescue_entity(
        self,
        *,
        incident_id: str,
        resolved_location: Mapping[str, Any],
        slots: RescueTaskGenerationSlots,
        recommendation: Mapping[str, Any],
        metadata: Mapping[str, Any],
        user_id: str,
    ) -> Optional[IncidentEntityDetail]:
        lng = resolved_location.get("lng")
        lat = resolved_location.get("lat")
        if lng is None or lat is None:
            return None
        properties: Dict[str, Any] = {
            "name": resolved_location.get("name") or slots.location_name or "救援目标",
            "confidence": resolved_location.get("confidence"),
            "missionType": getattr(slots, "mission_type", None),
            "eventType": getattr(slots, "event_type", None),
            "situationSummary": slots.situation_summary,
            "entrySource": metadata.get("source"),
            "recommendedResourceId": recommendation.get("resource_id"),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        create_input = IncidentEntityCreateInput(
            incident_id=incident_id,
            entity_type="rescue_target",
            layer_code="layer.dispose",
            geometry_geojson=self._point_geometry(float(lng), float(lat)),
            properties=properties,
            relation_type="primary",
            relation_description=slots.situation_summary,
            display_priority=100,
            created_by=user_id or "system",
            source=self._determine_entity_source(metadata),
            is_visible_on_map=True,
        )
        try:
            return await self._incident_repository.create_entity_with_link(create_input)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "rescue_entity_create_failed",
                incident_id=incident_id,
                error=str(exc),
            )
            return None

    async def _fetch_risk_zones(
        self,
        *,
        incident_id: str,
    ) -> Tuple[List[RiskZoneRecord], str, datetime | None]:
        """拉取危险区域数据，优先使用缓存。"""
        risk_cache = self._risk_cache
        if risk_cache is not None:
            try:
                zones = await risk_cache.get_active_zones()
                snapshot = risk_cache.snapshot()
                refreshed_at = snapshot.refreshed_at if snapshot is not None else None
                return list(zones), "cache", refreshed_at
            except Exception as cache_exc:  # pragma: no cover
                logger.warning(
                    "risk_cache_access_failed",
                    incident_id=incident_id,
                    error=str(cache_exc),
                )
        try:
            zones = await self._incident_dao.list_active_risk_zones()
        except Exception as exc:  # pragma: no cover
            logger.warning("risk_assessment_unavailable", incident_id=incident_id, error=str(exc))
            return [], "unavailable", None
        return list(zones), "dao", None

    def _serialize_risk_zones(self, zones: Sequence[RiskZoneRecord]) -> List[Dict[str, Any]]:
        """转换危险区域，确保 JSON 序列化安全。"""
        serialized: List[Dict[str, Any]] = []
        for zone in zones:
            serialized.append(
                {
                    "zoneId": zone.zone_id,
                    "zoneName": zone.zone_name,
                    "hazardType": zone.hazard_type,
                    "severity": zone.severity,
                    "description": zone.description,
                    "geometry": dict(zone.geometry_geojson),
                    "properties": dict(zone.properties),
                    "validFrom": zone.valid_from.isoformat(),
                    "validUntil": zone.valid_until.isoformat() if zone.valid_until else None,
                    "updatedAt": zone.updated_at.isoformat(),
                }
            )
        return serialized

    def _summarize_and_log_risks(
        self,
        *,
        incident_id: str,
        zones: Sequence[RiskZoneRecord],
        source: str,
        refreshed_at: datetime | None,
    ) -> Dict[str, Any]:
        """汇总危险区域并写日志，便于排查。"""
        hazard_types = sorted({zone.hazard_type for zone in zones})
        summary: Dict[str, Any] = {
            "count": len(zones),
            "hazardTypes": hazard_types,
            "source": source,
        }
        if refreshed_at is not None:
            summary["refreshedAt"] = refreshed_at.isoformat()
        logger.info(
            "risk_assessment_summary",
            incident_id=incident_id,
            active_zone_count=summary["count"],
            hazard_types=hazard_types,
            source=source,
            refreshed_at=summary.get("refreshedAt"),
        )
        return summary

    async def _prepare_risk_context(self, *, incident_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """提供危险区序列化结果与摘要。"""
        zones, source, refreshed_at = await self._fetch_risk_zones(incident_id=incident_id)
        summary = self._summarize_and_log_risks(
            incident_id=incident_id,
            zones=zones,
            source=source,
            refreshed_at=refreshed_at,
        )
        serialized = self._serialize_risk_zones(zones)
        return serialized, summary

    def _build_plan_payload(
        self,
        *,
        task_id: str,
        incident_id: str,
        slots: RescueTaskGenerationSlots,
        resolved_location: Mapping[str, Any],
        entity: Optional[IncidentEntityDetail],
        recommendation: Mapping[str, Any],
        handler_result: Mapping[str, Any],
        risk_zones: Sequence[Mapping[str, Any]],
        risk_summary: Mapping[str, Any],
    ) -> RescuePlan:
        analysis_summary = dict(handler_result.get("analysis_summary") or {})
        matched_resources = self._ensure_mapping_list(handler_result.get("matched_resources"))
        unmatched_resources = self._ensure_mapping_list(handler_result.get("unmatched_resources"))
        routes = self._serialize_routes(handler_result.get("routes"))
        equipment_recommendations = self._ensure_mapping_list(handler_result.get("recommendations"))

        overview = self._build_plan_overview(
            task_id=task_id,
            incident_id=incident_id,
            slots=slots,
            resolved_location=resolved_location,
            analysis_summary=analysis_summary,
            risk_summary=risk_summary,
            recommendation=recommendation,
        )
        line_entries = self._build_plan_lines(
            task_id=task_id,
            resolved_location=resolved_location,
            matched_resources=matched_resources,
            routes=routes,
        )
        team_resources, team_evidence = self._build_team_resource_entries(
            matched_resources=matched_resources,
            unmatched_resources=unmatched_resources,
        )
        equipment_resources, equipment_evidence = self._build_equipment_entries(equipment_recommendations)
        risk_entries = self._build_plan_risk_entries(risk_zones)
        route_warnings = self._build_route_warnings(
            matched_resources=matched_resources,
            routes=routes,
            risk_zones=risk_zones,
            resolved_location=resolved_location,
        )
        evidence_entries = self._deduplicate_evidence(team_evidence + equipment_evidence)

        plan: RescuePlan = {
            "overview": overview,
            "lines": line_entries,
            "resources": team_resources + equipment_resources,
            "risks": risk_entries,
            "evidenceTrace": evidence_entries,
            "routeWarnings": route_warnings,
        }
        return plan

    @staticmethod
    def _ensure_mapping_list(value: Any) -> List[Dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, Mapping):
            return [dict(value)]
        if isinstance(value, Iterable):
            result: List[Dict[str, Any]] = []
            for item in value:
                if isinstance(item, Mapping):
                    result.append(dict(item))
            return result
        return []

    @staticmethod
    def _safe_float(value: Any, *, divisor: Optional[float] = None) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
            if divisor:
                if divisor == 0:
                    return None
                numeric = numeric / divisor
            if math.isnan(numeric) or math.isinf(numeric):
                return None
            return numeric
        except (TypeError, ValueError):
            return None

    def _build_plan_overview(
        self,
        *,
        task_id: str,
        incident_id: str,
        slots: RescueTaskGenerationSlots,
        resolved_location: Mapping[str, Any],
        analysis_summary: Mapping[str, Any],
        risk_summary: Mapping[str, Any],
        recommendation: Mapping[str, Any],
    ) -> RescuePlanOverview:
        location_payload: Dict[str, Any] = {}
        name_fields = [
            resolved_location.get("name"),
            resolved_location.get("poi"),
            resolved_location.get("address"),
        ]
        chosen_name = next((str(item) for item in name_fields if isinstance(item, str) and item.strip()), None)
        if chosen_name:
            location_payload["name"] = chosen_name
        lng = self._safe_float(resolved_location.get("lng"))
        lat = self._safe_float(resolved_location.get("lat"))
        if lng is not None:
            location_payload["lng"] = lng
        if lat is not None:
            location_payload["lat"] = lat
        if resolved_location.get("address"):
            location_payload["address"] = resolved_location.get("address")
        overview: RescuePlanOverview = {
            "taskId": task_id,
            "incidentId": incident_id,
            "situationSummary": slots.situation_summary or "",
            "missionType": getattr(slots, "mission_type", None),
            "location": location_payload,
            "analysis": cast(AnalysisSummary, dict(analysis_summary)),
            "riskOutline": self._build_risk_outline(risk_summary),
            "recommendedResourceId": recommendation.get("resource_id") if isinstance(recommendation, Mapping) else None,
        }
        return overview

    def _build_risk_outline(self, risk_summary: Mapping[str, Any]) -> Optional[str]:
        count = risk_summary.get("count")
        hazard_types = risk_summary.get("hazardTypes") or []
        try:
            count_int = int(count) if count is not None else 0
        except (TypeError, ValueError):
            count_int = 0
        if count_int <= 0:
            return None
        hazards_text = "、".join(str(item) for item in hazard_types if item)
        if hazards_text:
            return f"附近识别 {count_int} 处危险区域（{hazards_text}）。"
        return f"附近识别 {count_int} 处危险区域，需现场确认具体风险。"

    def _build_plan_lines(
        self,
        *,
        task_id: str,
        resolved_location: Mapping[str, Any],
        matched_resources: Sequence[Mapping[str, Any]],
        routes: Sequence[Mapping[str, Any]],
    ) -> List[RescuePlanLine]:
        if not matched_resources:
            return []
        location_name = next(
            (
                str(resolved_location.get(field))
                for field in ("name", "poi", "address")
                if isinstance(resolved_location.get(field), str) and resolved_location.get(field)
            ),
            "目标区域",
        )
        route_lookup = self._route_by_resource(routes)
        lines: List[RescuePlanLine] = []
        for index, resource in enumerate(matched_resources):
            resource_id = str(resource.get("resource_id"))
            eta_minutes = self._safe_float(resource.get("eta_minutes"))
            objectives: List[str] = [
                f"调派 {resource.get('name', resource_id)} 前往 {location_name}",
            ]
            if eta_minutes is not None:
                objectives.append(f"预计 {eta_minutes:.1f} 分钟到达现场")
            lack_reasons = resource.get("lack_reasons") or []
            if lack_reasons:
                joined = "、".join(str(item) for item in lack_reasons if item)
                if joined:
                    objectives.append(f"需补充：{joined}")
            route_summary = self._build_route_summary(route_lookup.get(resource_id))
            line: RescuePlanLine = {
                "lineId": f"{task_id}-L{index + 1}",
                "title": f"{resource.get('rescuer_type', '救援力量')}救援线",
                "primaryResourceId": resource_id,
                "etaMinutes": eta_minutes,
                "route": route_summary,
                "objectives": objectives,
            }
            lines.append(line)
        return lines

    def _route_by_resource(self, routes: Sequence[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
        lookup: Dict[str, Mapping[str, Any]] = {}
        for route in routes:
            resource_id = route.get("resource_id")
            if isinstance(resource_id, str):
                lookup[resource_id] = route
        return lookup

    def _build_route_summary(self, route: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        if not route:
            return {}
        summary: Dict[str, Any] = {
            "routeId": route.get("route_id"),
            "distanceKm": self._safe_float(route.get("distance_meters"), divisor=1000.0),
            "durationMinutes": self._safe_float(route.get("duration_seconds"), divisor=60.0),
            "etaMinutes": self._safe_float(route.get("eta_minutes")),
            "cacheHit": bool(route.get("cache_hit")),
        }
        return {key: value for key, value in summary.items() if value is not None or isinstance(value, bool)}

    def _build_team_resource_entries(
        self,
        *,
        matched_resources: Sequence[Mapping[str, Any]],
        unmatched_resources: Sequence[Mapping[str, Any]],
    ) -> Tuple[List[RescuePlanResourceEntry], List[RescuePlanEvidenceEntry]]:
        entries: List[RescuePlanResourceEntry] = []
        evidence: List[RescuePlanEvidenceEntry] = []
        for resource in matched_resources:
            entry = self._team_resource_entry(resource, available=True)
            entries.append(entry)
            evidence.append(self._team_evidence_entry(resource))
        for resource in unmatched_resources:
            entry = self._team_resource_entry(resource, available=False)
            entries.append(entry)
            evidence.append(self._team_evidence_entry(resource))
        return entries, evidence

    def _team_resource_entry(self, resource: Mapping[str, Any], *, available: bool) -> RescuePlanResourceEntry:
        resource_id = str(resource.get("resource_id"))
        entry: RescuePlanResourceEntry = {
            "resourceId": resource_id,
            "resourceType": "team",
            "name": str(resource.get("name", resource_id)),
            "capabilityMatch": resource.get("capability_match"),
            "etaMinutes": self._safe_float(resource.get("eta_minutes")),
            "distanceKm": self._safe_float(resource.get("distance_km")),
            "recommendedQuantity": None,
            "reasoning": None,
            "confidenceLevel": None,
            "lackReasons": [str(item) for item in resource.get("lack_reasons") or []],
            "evidenceIds": [f"team:{resource_id}"],
            "attributes": {
                "rescuerType": resource.get("rescuer_type"),
                "available": available,
            },
        }
        return entry

    def _team_evidence_entry(self, resource: Mapping[str, Any]) -> RescuePlanEvidenceEntry:
        resource_id = str(resource.get("resource_id"))
        eta = self._safe_float(resource.get("eta_minutes"))
        distance = self._safe_float(resource.get("distance_km"))
        pieces: List[str] = []
        capability = resource.get("capability_match")
        if capability:
            pieces.append(f"能力匹配：{capability}")
        if eta is not None:
            pieces.append(f"预计抵达 {eta:.1f} 分钟")
        if distance is not None:
            pieces.append(f"距离 {distance:.1f} 公里")
        lack = resource.get("lack_reasons") or []
        if lack:
            lack_joined = "、".join(str(item) for item in lack if item)
            if lack_joined:
                pieces.append(f"待补充：{lack_joined}")
        summary = "；".join(pieces) if pieces else "资源评估信息缺失"
        return RescuePlanEvidenceEntry(
            evidenceId=f"team:{resource_id}",
            category="recommendation",
            source="resource_matcher",
            summary=summary,
            confidence=None,
            relatedResourceId=resource_id,
        )

    def _build_equipment_entries(
        self,
        equipment_recommendations: Sequence[Mapping[str, Any]],
    ) -> Tuple[List[RescuePlanResourceEntry], List[RescuePlanEvidenceEntry]]:
        resources: List[RescuePlanResourceEntry] = []
        evidence: List[RescuePlanEvidenceEntry] = []
        for recommendation in equipment_recommendations:
            equipment_name = str(recommendation.get("equipment_name") or recommendation.get("display_name") or uuid.uuid4())
            evidence_ids: List[str] = []
            kg_evidence = recommendation.get("kg_evidence")
            if isinstance(kg_evidence, Mapping):
                kg_id = f"kg:{equipment_name}"
                evidence_ids.append(kg_id)
                evidence.append(self._build_kg_evidence_entry(kg_id, equipment_name, kg_evidence))
            rag_evidence = recommendation.get("rag_evidence") or []
            if isinstance(rag_evidence, Iterable):
                for index, item in enumerate(rag_evidence):
                    if not isinstance(item, Mapping):
                        continue
                    rag_id = f"rag:{equipment_name}:{index}"
                    evidence_ids.append(rag_id)
                    evidence.append(self._build_rag_evidence_entry(rag_id, equipment_name, item))
            resource_entry: RescuePlanResourceEntry = {
                "resourceId": equipment_name,
                "resourceType": "equipment",
                "name": str(recommendation.get("display_name", equipment_name)),
                "capabilityMatch": None,
                "etaMinutes": None,
                "distanceKm": None,
                "recommendedQuantity": int(recommendation.get("recommended_quantity", 0)),
                "reasoning": recommendation.get("reasoning"),
                "confidenceLevel": recommendation.get("confidence_level"),
                "lackReasons": [],
                "evidenceIds": evidence_ids,
                "attributes": {"source": "equipment_recommendation"},
            }
            resources.append(resource_entry)
        return resources, evidence

    def _build_kg_evidence_entry(
        self,
        evidence_id: str,
        equipment_name: str,
        data: Mapping[str, Any],
    ) -> RescuePlanEvidenceEntry:
        standard_quantity = data.get("standard_quantity")
        urgency = data.get("urgency")
        summary_parts: List[str] = []
        if standard_quantity is not None:
            summary_parts.append(f"标准配置 {standard_quantity}")
        if urgency is not None:
            summary_parts.append(f"紧急程度 {urgency}")
        summary = "，".join(summary_parts) if summary_parts else "来源于知识图谱标准配置"
        return RescuePlanEvidenceEntry(
            evidenceId=evidence_id,
            category="kg",
            source="knowledge_graph",
            summary=summary,
            confidence=None,
            relatedResourceId=equipment_name,
        )

    def _build_rag_evidence_entry(
        self,
        evidence_id: str,
        equipment_name: str,
        data: Mapping[str, Any],
    ) -> RescuePlanEvidenceEntry:
        source = data.get("case_source")
        snippet = data.get("context_snippet")
        confidence = self._safe_float(data.get("confidence"))
        summary_parts: List[str] = []
        if source:
            summary_parts.append(str(source))
        if snippet:
            summary_parts.append(str(snippet))
        summary = "：".join(summary_parts) if summary_parts else "案例参考"
        return RescuePlanEvidenceEntry(
            evidenceId=evidence_id,
            category="rag",
            source="rag_case",
            summary=summary,
            confidence=confidence,
            relatedResourceId=equipment_name,
        )

    def _build_plan_risk_entries(self, risk_zones: Sequence[Mapping[str, Any]]) -> List[RescuePlanRiskEntry]:
        entries: List[RescuePlanRiskEntry] = []
        for zone in risk_zones:
            zone_id_raw = zone.get("zoneId") or zone.get("zone_id")
            zone_id = str(zone_id_raw) if zone_id_raw is not None else str(uuid.uuid4())
            geometry = zone.get("geometry") if isinstance(zone.get("geometry"), Mapping) else {}
            entry: RescuePlanRiskEntry = {
                "zoneId": zone_id,
                "zoneName": str(zone.get("zoneName") or zone_id),
                "hazardType": str(zone.get("hazardType") or "未知风险"),
                "severity": str(zone.get("severity")) if zone.get("severity") is not None else None,
                "description": str(zone.get("description")) if zone.get("description") is not None else None,
                "validFrom": zone.get("validFrom"),
                "validUntil": zone.get("validUntil"),
                "geometry": dict(geometry),
            }
            entries.append(entry)
        return entries

    def _build_route_warnings(
        self,
        *,
        matched_resources: Sequence[Mapping[str, Any]],
        routes: Sequence[Mapping[str, Any]],
        risk_zones: Sequence[Mapping[str, Any]],
        resolved_location: Mapping[str, Any],
    ) -> List[RescuePlanRouteWarning]:
        if not risk_zones:
            return []
        target_lng = self._safe_float(resolved_location.get("lng"))
        target_lat = self._safe_float(resolved_location.get("lat"))
        if target_lng is None or target_lat is None:
            return []
        resource_ids = [
            str(resource.get("resource_id"))
            for resource in matched_resources
            if isinstance(resource.get("resource_id"), str)
        ]
        if not resource_ids:
            return []
        warnings: List[RescuePlanRouteWarning] = []
        for zone in risk_zones:
            geometry = zone.get("geometry") if isinstance(zone.get("geometry"), Mapping) else None
            centroid = self._zone_centroid(geometry)
            if centroid is None:
                continue
            distance = self._geo_distance_km(target_lng, target_lat, centroid[0], centroid[1])
            if distance is None or distance > 2.5:
                continue
            severity = zone.get("severity")
            hazard = zone.get("hazardType") or "未知风险"
            zone_name = zone.get("zoneName") or "危险区域"
            message = f"{zone_name} 存在 {hazard} 风险"
            if severity is not None:
                message += f"（等级 {severity}）"
            message += "，请确认路线清障或调整调度。"
            warnings.append(
                {
                    "zoneId": str(zone.get("zoneId") or zone_name),
                    "hazardType": str(hazard),
                    "severity": str(severity) if severity is not None else None,
                    "message": message,
                    "distanceKm": distance,
                    "resourceIds": resource_ids,
                }
            )
        return warnings

    def _zone_centroid(self, geometry: Mapping[str, Any] | None) -> Tuple[float, float] | None:
        if geometry is None:
            return None
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates")
        if geom_type == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            lng = self._safe_float(coords[0])
            lat = self._safe_float(coords[1])
            if lng is not None and lat is not None:
                return (lng, lat)
            return None
        points = self._flatten_coordinates(coords)
        if not points:
            return None
        total_lng = sum(point[0] for point in points)
        total_lat = sum(point[1] for point in points)
        count = len(points)
        return (total_lng / count, total_lat / count)

    @staticmethod
    def _flatten_coordinates(value: Any) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and all(isinstance(item, (int, float)) for item in value):
                points.append((float(value[0]), float(value[1])))
            else:
                for item in value:
                    points.extend(RescueTaskGenerationHandler._flatten_coordinates(item))
        return points

    @staticmethod
    def _geo_distance_km(lng1: float, lat1: float, lng2: float, lat2: float) -> Optional[float]:
        try:
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lng2 - lng1)
            a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return 6371.0 * c
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _deduplicate_evidence(evidence: Iterable[RescuePlanEvidenceEntry]) -> List[RescuePlanEvidenceEntry]:
        unique: Dict[str, RescuePlanEvidenceEntry] = {}
        for item in evidence:
            unique[item["evidenceId"]] = item
        return list(unique.values())

    def _compose_ui_actions(
        self,
        *,
        incident_id: str,
        task_id: str,
        resolved: Mapping[str, Any],
        entity: Optional[IncidentEntityDetail],
        plan_payload: Mapping[str, Any],
        risk_summary: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        actions: List[Any] = []
        metadata = {"incident_id": incident_id, "task_id": task_id}
        lng = resolved.get("lng")
        lat = resolved.get("lat")
        if isinstance(lng, (int, float)) and isinstance(lat, (int, float)):
            actions.append(camera_fly_to(float(lng), float(lat), metadata=metadata))
        if entity is not None:
            actions.append(focus_entity(entity.entity.entity_id, metadata=metadata))
        actions.append(open_panel(panel="rescue_plan", params={"plan": plan_payload}, metadata=metadata))
        actions.append(
            show_toast(
                "已生成救援方案，等待指挥员确认。",
                level="info",
                metadata=metadata,
            )
        )
        risk_count = int(risk_summary.get("count", 0) or 0)
        if risk_count > 0:
            hazard_types = risk_summary.get("hazardTypes") or []
            hazard_text = "、".join(str(item) for item in hazard_types) if hazard_types else "风险类型待确认"
            actions.append(
                show_toast(
                    f"附近存在{risk_count}处危险区域：{hazard_text}。",
                    level="warning",
                    metadata=metadata,
                    duration_ms=8000,
                )
            )
        route_warnings = plan_payload.get("routeWarnings") or []
        for warning in route_warnings:
            message = warning.get("message")
            if not message:
                continue
            actions.append(
                show_risk_warning(
                    str(message),
                    related_resources=warning.get("resourceIds"),
                    risk_zones=[warning["zoneId"]] if warning.get("zoneId") else None,
                    metadata=metadata,
                )
            )
        return serialize_actions(actions)

    async def handle(self, slots: RescueTaskGenerationSlots, state: dict[str, object]) -> dict[str, object]:
        # legacy_graph = await self._ensure_graph(notify=True)
        task_id = str(uuid.uuid4())
        conversation_context: Dict[str, Any] = dict(cast(Dict[str, Any], state.get("conversation_context") or {}))
        metadata: Dict[str, Any] = dict(cast(Dict[str, Any], state.get("metadata") or {}))
        existing_event_type = conversation_context.get("event_type")
        if existing_event_type and not slots.event_type:
            slots.event_type = str(existing_event_type)

        incident_id: Optional[str] = cast(Optional[str], conversation_context.get("incident_id"))
        if not incident_id:
            incident_id = RESCUE_DEMO_INCIDENT_ID
            conversation_context["incident_id"] = incident_id
            logger.info(
                "rescue_task_using_default_incident",
                thread_id=state.get("thread_id"),
                incident_id=incident_id,
                task_id=task_id,
            )

        tactical_state: RescueTacticalState = {
            "task_id": task_id,
            "user_id": str(state.get("user_id")),
            "thread_id": str(state.get("thread_id")),
            "slots": slots,
            "simulation_mode": False,
            "auto_persist": self._draft_service is None,
            "conversation_context": conversation_context,
        }

        coordinates = getattr(slots, "coordinates", None)
        has_coordinates = isinstance(coordinates, dict) and "lat" in coordinates and "lng" in coordinates
        logger.info(
            "rescue_task_slots_prepared",
            task_id=task_id,
            thread_id=state.get("thread_id"),
            mission_type=getattr(slots, "mission_type", None),
            location_name=getattr(slots, "location_name", None),
            has_coordinates=has_coordinates,
            summary_length=len(getattr(slots, "situation_summary", "") or ""),
        )

        if self._simple_graph is not None:
            simple_slots = asdict(slots)
            simple_state = {
                "thread_id": str(state.get("thread_id")),
                "user_id": str(state.get("user_id")),
                "slots": simple_slots,
            }
            try:
                logger.info(
                    "simple_rescue_graph_invoke_start",
                    task_id=task_id,
                    thread_id=state.get("thread_id"),
                )
                simple_result = await self._simple_graph.ainvoke(
                    simple_state,
                    config={"configurable": {"thread_id": str(state.get("thread_id"))}},
                )
                logger.info(
                    "simple_rescue_graph_invoke_complete",
                    task_id=task_id,
                    thread_id=state.get("thread_id"),
                    status=simple_result.get("status"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "simple_rescue_graph_invoke_failed",
                    task_id=task_id,
                    thread_id=state.get("thread_id"),
                    error=str(exc),
                )
                fallback_text = "简化救援流程暂时不可用，请人工调度或稍后重试。"
                return {
                    "response_text": fallback_text,
                    "rescue_task": None,
                    "conversation_context": conversation_context,
                    "simple_rescue": {
                        "status": "error",
                        "equipment": None,
                        "missing_fields": None,
                    },
                }

            response_text = str(simple_result.get("response_text") or "救援信息已记录，请继续补充现场情况。")
            return {
                "response_text": response_text,
                "rescue_task": None,
                "conversation_context": conversation_context,
                "simple_rescue": {
                    "status": simple_result.get("status", "success"),
                    "equipment": simple_result.get("equipment"),
                    "missing_fields": simple_result.get("missing_fields"),
                },
            }

        logger.warning(
            "simple_rescue_graph_missing",
            task_id=task_id,
            thread_id=state.get("thread_id"),
        )
        if not self._legacy_fallback_enabled:
            return {
                "response_text": "简化救援流程未准备就绪，请联系系统管理员。",
                "rescue_task": None,
                "conversation_context": conversation_context,
                "simple_rescue": {
                    "status": "error",
                    "equipment": None,
                    "missing_fields": None,
                },
            }

        graph = await self._ensure_graph(notify=True)
        result = await graph.invoke(
            tactical_state,
            config={"durability": "sync"},
        )
        if result.get("status") == "error":
            error_text = result.get("error", "任务生成失败。")
            logger.error(
                "rescue_task_failed",
                task_id=task_id,
                error=error_text,
                thread_id=state.get("thread_id"),
            )
            updated_context = result.get("conversation_context") or conversation_context
            slots_after = result.get("slots") or slots
            if isinstance(slots_after, RescueTaskGenerationSlots) and slots_after.event_type:
                updated_context["event_type"] = slots_after.event_type
            return {
                "response_text": error_text,
                "rescue_task": None,
                "conversation_context": updated_context,
            }

        summary = cast(AnalysisSummary, result.get("analysis_summary") or AnalysisSummary())
        payload = result.get("ws_payload")
        resolved_location = result.get("resolved_location") or {}
        updated_context = result.get("conversation_context") or conversation_context
        slots_after = result.get("slots") or slots
        if isinstance(slots_after, RescueTaskGenerationSlots) and slots_after.event_type:
            updated_context["event_type"] = slots_after.event_type

        logger.info(
            "rescue_task_completed",
            task_id=task_id,
            thread_id=state.get("thread_id"),
            matched=summary.get("matched_count", 0),
            unmatched=summary.get("unmatched_count", 0),
            kg_count=summary.get("kg_count", 0),
            rag_count=summary.get("rag_count", 0),
            cache_hits=summary.get("cache_hits", 0),
        )

        simulation_mode = bool(tactical_state.get("simulation_mode"))
        entity_detail: Optional[IncidentEntityDetail] = None
        if not simulation_mode:
            entity_detail = await self._create_rescue_entity(
                incident_id=incident_id,
                resolved_location=resolved_location,
                slots=slots,
                recommendation=result.get("recommendation") or {},
                metadata=metadata,
                user_id=str(state.get("user_id")),
            )
            if entity_detail is not None:
                logger.info(
                    "local_rescue_entity_created",
                    incident_id=incident_id,
                    entity_id=entity_detail.entity.entity_id,
                    thread_id=state.get("thread_id"),
                    entry_source=metadata.get("source"),
                )

        risk_zones_payload: List[Dict[str, Any]]
        risk_summary: Dict[str, Any]
        if not simulation_mode:
            risk_zones_payload, risk_summary = await self._prepare_risk_context(incident_id=incident_id)
        else:
            risk_zones_payload = []
            risk_summary = {"count": 0, "hazardTypes": [], "source": "simulation"}

        persisted_task_entry = result.get("persisted_task") or {}
        final_task_id = persisted_task_entry.get("id") or task_id

        active_slots = slots_after if isinstance(slots_after, RescueTaskGenerationSlots) else slots

        plan_payload = self._build_plan_payload(
            task_id=final_task_id,
            incident_id=incident_id,
            slots=active_slots,
            resolved_location=resolved_location,
            entity=entity_detail,
            recommendation=result.get("recommendation") or {},
            handler_result=result,
            risk_zones=risk_zones_payload,
            risk_summary=risk_summary,
        )

        ui_actions: List[Dict[str, Any]] = []
        if not simulation_mode:
            ui_actions = self._compose_ui_actions(
                incident_id=incident_id,
                task_id=task_id,
                resolved=resolved_location,
                entity=entity_detail,
                plan_payload=plan_payload,
                risk_summary=risk_summary,
            )
            if plan_payload["routeWarnings"]:
                logger.warning(
                    "route_risk_detected",
                    incident_id=incident_id,
                    task_id=task_id,
                    warning_count=len(plan_payload["routeWarnings"]),
                )
            if ui_actions:
                logger.info(
                    "rescue_ui_actions_emitted",
                    incident_id=incident_id,
                    task_id=task_id,
                    count=len(ui_actions),
                )

        entity_payload: Optional[Dict[str, Any]] = None
        if entity_detail is not None:
            entity_payload = {
                "entity_id": entity_detail.entity.entity_id,
                "layer_code": entity_detail.entity.layer_code,
                "display_name": entity_detail.entity.display_name,
                "geometry": entity_detail.entity.geometry_geojson,
                "properties": entity_detail.entity.properties,
                "relation": {
                    "type": entity_detail.link.relation_type,
                    "description": entity_detail.link.notes,
                },
            }

        routes_serialized = self._serialize_routes(result.get("routes"))

        rescue_task_payload: Dict[str, Any] = {
            "task_id": final_task_id,
            "resolved_location": result.get("resolved_location"),
            "matched_resources": result.get("matched_resources"),
            "unmatched_resources": result.get("unmatched_resources"),
            "routes": routes_serialized,
            "recommendation": result.get("recommendation"),
            "kg_requirements": result.get("kg_requirements"),
            "rag_cases": result.get("rag_cases"),
            "rag_equipments": result.get("rag_equipments"),
            "recommendations": result.get("recommendations"),
            "analysis_summary": summary,
            "ws_payload": payload,
            "incident_response": result.get("incident_response"),
            "persisted_task": persisted_task_entry,
            "persisted_routes": result.get("persisted_routes"),
            "entity": entity_payload,
            "plan": plan_payload,
            "risk_summary": risk_summary,
            "risk_zones": risk_zones_payload,
            "route_warnings": plan_payload["routeWarnings"],
        }

        if self._draft_service is not None and not simulation_mode:
            actor = str(state.get("user_id") or "system")
            draft_record = await self._draft_service.save_draft(
                incident_id=incident_id,
                entity=entity_detail,
                plan=rescue_task_payload,
                risk_summary=risk_summary,
                ui_actions=ui_actions,
                created_by=actor,
            )
            rescue_task_payload["draft_id"] = draft_record.draft_id

        return {
            "response_text": result.get("response_text", "已生成救援建议。"),
            "conversation_context": updated_context,
            "rescue_task": rescue_task_payload,
            "ui_actions": ui_actions,
        }

    @staticmethod
    def _serialize_routes(routes: Any) -> List[Dict[str, Any]]:
        if not isinstance(routes, Sequence):
            return []
        serialized: List[Dict[str, Any]] = []
        for route in routes:
            if hasattr(route, "__dataclass_fields__"):
                serialized.append(asdict(route))
            elif isinstance(route, Mapping):
                serialized.append(dict(route))
        return serialized


@dataclass
class RescueSimulationHandler(IntentHandler[RescueTaskGenerationSlots]):
    pool: AsyncConnectionPool
    kg_service: KGService
    rag_pipeline: RagPipeline
    amap_client: AmapClient
    llm_client: Any
    llm_model: str
    orchestrator_client: OrchestratorClient | None
    rag_timeout: float
    postgres_dsn: str

    def __post_init__(self) -> None:
        self._graph: Optional[RescueTacticalGraph] = None
        self._graph_lock = asyncio.Lock()

    async def _ensure_graph(self) -> RescueTacticalGraph:
        if self._graph is not None:
            return self._graph
        async with self._graph_lock:
            if self._graph is None:
                self._graph = await build_rescue_tactical_graph(
                    pool=self.pool,
                    kg_service=self.kg_service,
                    rag_pipeline=self.rag_pipeline,
                    amap_client=self.amap_client,
                    llm_client=self.llm_client,
                    llm_model=self.llm_model,
                    orchestrator=self.orchestrator_client,
                    rag_timeout=self.rag_timeout,
                    notify=False,
                    postgres_dsn=self.postgres_dsn,
                )
        return self._graph

    async def aclose(self) -> None:
        if self._graph is not None:
            await self._graph.close()
            self._graph = None

    async def handle(self, slots: RescueTaskGenerationSlots, state: dict[str, object]) -> dict[str, object]:
        graph = await self._ensure_graph()
        task_id = str(uuid.uuid4())
        conversation_context: Dict[str, Any] = dict(cast(Dict[str, Any], state.get("conversation_context") or {}))
        incident_id: Optional[str] = cast(Optional[str], conversation_context.get("incident_id"))
        if not incident_id:
            incident_id = RESCUE_DEMO_INCIDENT_ID
            conversation_context["incident_id"] = incident_id

        tactical_state: RescueTacticalState = {
            "task_id": task_id,
            "user_id": str(state.get("user_id")),
            "thread_id": str(state.get("thread_id")),
            "slots": slots,
            "simulation_mode": True,
            "conversation_context": conversation_context,
        }
        result = await graph.invoke(
            tactical_state,
            config={"durability": "sync"},  # 长流程（救援任务生成），同步保存checkpoint确保高可靠性
        )
        response_text = result.get("response_text", "已生成模拟救援方案。")
        summary = cast(AnalysisSummary, result.get("analysis_summary") or AnalysisSummary())
        return {
            "response_text": response_text,
            "conversation_context": result.get("conversation_context") or conversation_context,
            "simulation": {
                "recommendation": result.get("recommendation"),
                "matched_resources": result.get("matched_resources"),
                "unmatched_resources": result.get("unmatched_resources"),
                "routes": result.get("routes"),
                "analysis_summary": summary,
            },
        }
