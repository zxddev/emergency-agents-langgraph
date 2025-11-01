from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .models import (
    GeoPoint,
    PlannedTask,
    ResourceCandidate,
    ResourceMatch,
    ResourcePlanningResult,
)


def _haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    radius = 6371.0
    d_lat = math.radians(b.lat - a.lat)
    d_lon = math.radians(b.lon - a.lon)
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * (math.sin(d_lon / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(h))


def _capability_metrics(required: Sequence[str], candidate: ResourceCandidate) -> Tuple[float, List[str]]:
    if not required:
        return 1.0, []
    capability_set = {cap.lower() for cap in candidate.capabilities}
    matched = [cap for cap in required if cap in capability_set]
    coverage = len(matched) / len(required)
    lacking = [cap for cap in required if cap not in capability_set]
    return coverage, lacking


def _equipment_score(equipment_names: Sequence[str], candidate: ResourceCandidate) -> float:
    if not equipment_names:
        return 0.0
    if not candidate.equipment:
        return 0.0
    equipment_set = {item.lower() for item in candidate.equipment}
    hits = sum(1 for name in equipment_names if name.lower() in equipment_set)
    return hits / len(equipment_names)


class ResourceMatcher:
    """资源匹配器。"""

    def __init__(self, *, reuse_threshold: float = 0.85) -> None:
        self._reuse_threshold = reuse_threshold

    def match(
        self,
        tasks: Sequence[PlannedTask],
        candidates: Sequence[ResourceCandidate],
        *,
        incident_point: Optional[GeoPoint] = None,
    ) -> ResourcePlanningResult:
        available: Dict[str, ResourceCandidate] = {
            cand.resource_id: cand for cand in candidates if cand.availability
        }
        used_resources: Set[str] = set()
        matches: List[ResourceMatch] = []
        unmatched_tasks: List[str] = []

        for task in tasks:
            best_match: Optional[ResourceMatch] = None
            best_score: float = -1.0
            required_equipment = [item.name for item in task.recommended_equipment]
            for resource in available.values():
                coverage, lacking = _capability_metrics(task.required_capabilities, resource)
                if coverage <= 0.0 and lacking:
                    continue
                equipment_score = _equipment_score(required_equipment, resource)
                distance_km = None
                if incident_point and resource.location:
                    distance_km = _haversine_km(incident_point, resource.location)
                distance_score = 0.0
                if distance_km is not None and distance_km > 0.0:
                    distance_score = 1.0 / (1.0 + distance_km)
                score = (coverage * 0.6) + (equipment_score * 0.2) + (distance_score * 0.2)
                if resource.resource_id in used_resources and score < self._reuse_threshold:
                    continue
                if score > best_score:
                    best_score = score
                    best_match = ResourceMatch(
                        task_id=task.task_id,
                        resource_id=resource.resource_id,
                        match_score=round(score, 4),
                        capability_coverage=round(coverage, 4),
                        distance_km=None if distance_km is None else round(distance_km, 3),
                        lacking_capabilities=lacking,
                        notes=None if lacking else "能力完全覆盖",
                    )
            if best_match is None:
                unmatched_tasks.append(task.task_id)
                continue
            matches.append(best_match)
            used_resources.add(best_match.resource_id)

        unused = [resource_id for resource_id in available.keys() if resource_id not in used_resources]
        return ResourcePlanningResult(matches=matches, unmatched_tasks=unmatched_tasks, unused_resources=unused)
