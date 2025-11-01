from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, TypedDict

import structlog

from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from emergency_agents.risk.repository import RiskDataRepository

logger = structlog.get_logger(__name__)


class ScoutPlanOverview(TypedDict, total=False):
    incidentId: str
    targetType: Optional[str]
    objective: Optional[str]
    generatedAt: str
    riskSummary: Dict[str, Any]


class ScoutPlanTarget(TypedDict, total=False):
    targetId: str
    hazardType: str
    severity: int
    location: Dict[str, float]
    priority: str
    notes: Optional[str]


class ScoutPlan(TypedDict, total=False):
    overview: ScoutPlanOverview
    targets: List[ScoutPlanTarget]
    intelRequirements: List[Dict[str, Any]]
    recommendedSensors: List[str]
    riskHints: List[str]


class ScoutTacticalState(TypedDict, total=False):
    incident_id: str
    user_id: str
    thread_id: str
    slots: ScoutTaskGenerationSlots


@dataclass(slots=True)
class ScoutTacticalGraph:
    risk_repository: RiskDataRepository

    async def invoke(self, state: ScoutTacticalState) -> Dict[str, Any]:
        slots = state.get("slots")
        incident_id = state.get("incident_id", "")
        zones = await self.risk_repository.list_active_zones()
        plan = self._build_plan(incident_id, slots, zones)
        response_text = self._compose_response(plan)
        logger.info(
            "scout_plan_generated",
            incident_id=incident_id,
            target_count=len(plan.get("targets", [])),
            risk_count=plan["overview"].get("riskSummary", {}).get("total", 0),
        )
        return {
            "status": "ok",
            "scout_plan": plan,
            "response_text": response_text,
        }

    def _build_plan(
        self,
        incident_id: str,
        slots: Optional[ScoutTaskGenerationSlots],
        zones: Sequence[RiskZoneRecord],
    ) -> ScoutPlan:
        targets: List[ScoutPlanTarget] = []
        risk_hints: List[str] = []
        high_severity = 0
        for zone in zones:
            centroid = self._zone_centroid(zone.geometry_geojson)
            if centroid is None:
                continue
            priority = "HIGH" if zone.severity >= 4 else "MEDIUM"
            if priority == "HIGH":
                high_severity += 1
            targets.append(
                {
                    "targetId": zone.zone_id,
                    "hazardType": zone.hazard_type,
                    "severity": zone.severity,
                    "location": {"lng": centroid[0], "lat": centroid[1]},
                    "priority": priority,
                    "notes": zone.description,
                }
            )
            risk_hints.append(f"{zone.zone_name}：{zone.hazard_type} 等级 {zone.severity}")
        objective = slots.objective_summary if isinstance(slots, ScoutTaskGenerationSlots) else None
        overview: ScoutPlanOverview = {
            "incidentId": incident_id,
            "targetType": getattr(slots, "target_type", None) if slots else None,
            "objective": objective,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "riskSummary": {
                "total": len(zones),
                "highSeverity": high_severity,
            },
        }
        intel_requirements = self._build_intel_requirements(slots, zones)
        recommended_sensors = self._suggest_sensors(zones)
        return {
            "overview": overview,
            "targets": targets,
            "intelRequirements": intel_requirements,
            "recommendedSensors": recommended_sensors,
            "riskHints": risk_hints,
        }

    def _compose_response(self, plan: ScoutPlan) -> str:
        target_count = len(plan.get("targets", []))
        high = plan["overview"].get("riskSummary", {}).get("highSeverity", 0)
        return (
            f"已整理 {target_count} 个侦察目标，其中 {high} 个高风险点。已列出优先检查清单。"
        )

    def _build_intel_requirements(
        self,
        slots: Optional[ScoutTaskGenerationSlots],
        zones: Sequence[RiskZoneRecord],
    ) -> List[Dict[str, Any]]:
        requirements: List[Dict[str, Any]] = []
        if slots and slots.objective_summary:
            requirements.append({
                "type": "commander_objective",
                "description": slots.objective_summary,
            })
        for zone in zones:
            requirements.append(
                {
                    "type": "hazard_assessment",
                    "targetId": zone.zone_id,
                    "hazard": zone.hazard_type,
                    "details": zone.description,
                }
            )
        return requirements

    def _suggest_sensors(self, zones: Sequence[RiskZoneRecord]) -> List[str]:
        sensors: set[str] = set()
        for zone in zones:
            hazard = zone.hazard_type.lower()
            if "chemical" in hazard or "gas" in hazard:
                sensors.add("gas_detector")
            if "landslide" in hazard or "collapse" in hazard:
                sensors.add("depth_camera")
            if "flood" in hazard or "water" in hazard:
                sensors.add("sonar")
        if not sensors:
            sensors.add("visible_light_camera")
        return sorted(sensors)

    def _zone_centroid(self, geometry: Mapping[str, Any]) -> Optional[Tuple[float, float]]:
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates")
        if geom_type == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                return float(coords[0]), float(coords[1])
            except (TypeError, ValueError):
                return None
        points = self._flatten_coordinates(coords)
        if not points:
            return None
        avg_lng = sum(point[0] for point in points) / len(points)
        avg_lat = sum(point[1] for point in points) / len(points)
        return avg_lng, avg_lat

    def _flatten_coordinates(self, value: Any) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and all(isinstance(item, (int, float)) for item in value):
                points.append((float(value[0]), float(value[1])))
            else:
                for item in value:
                    points.extend(self._flatten_coordinates(item))
        return points


def build_scout_tactical_graph(*, risk_repository: RiskDataRepository) -> ScoutTacticalGraph:
    return ScoutTacticalGraph(risk_repository=risk_repository)
