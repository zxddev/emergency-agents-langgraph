from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field, PositiveInt, field_validator


class GeoPoint(BaseModel):
    """地理坐标点位。"""

    lon: float = Field(..., ge=-180.0, le=180.0)
    lat: float = Field(..., ge=-90.0, le=90.0)


class MissionPhase(str, Enum):
    """任务阶段枚举。"""

    RECONNAISSANCE = "reconnaissance"
    RESCUE = "rescue"
    ALERT = "alert"
    LOGISTICS = "logistics"


class SeverityBand(BaseModel):
    """严重程度分级。"""

    threshold: float = Field(..., ge=0.0, le=100.0)
    description: Optional[str] = None


class EquipmentNeed(BaseModel):
    """推荐装备定义。"""

    name: str
    quantity: PositiveInt = Field(..., description="建议数量")
    priority: Literal["critical", "recommended", "optional"] = "recommended"


class TaskTemplate(BaseModel):
    """任务模板定义。"""

    task_id: str
    task_type: str
    required_capabilities: List[str]
    recommended_equipment: List[EquipmentNeed] = Field(default_factory=list)
    duration_minutes: PositiveInt
    dependencies: List[str] = Field(default_factory=list)
    parallel_allowed: bool = False
    description: Optional[str] = None
    safety_notes: Optional[str] = None
    phase: Optional[MissionPhase] = None

    @field_validator("required_capabilities", mode="before")
    @classmethod
    def _normalize_capability(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip().lower() for item in value]
        return [str(value).strip().lower()]


class MissionTemplate(BaseModel):
    """阶段任务清单。"""

    phase: MissionPhase
    tasks: List[TaskTemplate]


class RiskRule(BaseModel):
    """风险规则定义。"""

    rule_id: str
    condition: str
    action: str
    priority: Literal["critical", "high", "medium", "low"] = "medium"


class ReferenceCase(BaseModel):
    """历史案例索引。"""

    case_id: str
    title: str
    summary: str
    date: Optional[str] = None
    location: Optional[str] = None
    lessons_learned: Optional[str] = None
    rag_doc_id: Optional[str] = None


class HazardPack(BaseModel):
    """灾种知识包。"""

    hazard_type: str
    version: str
    severity_levels: Dict[str, SeverityBand] = Field(default_factory=dict)
    mission_templates: List[MissionTemplate]
    risk_rules: List[RiskRule] = Field(default_factory=list)
    reference_cases: List[ReferenceCase] = Field(default_factory=list)

    def severity_label(self, score: float) -> str:
        """根据分值选择严重等级。"""
        if not self.severity_levels:
            return "unknown"
        sorted_levels = sorted(
            self.severity_levels.items(),
            key=lambda item: item[1].threshold,
        )
        chosen = "unknown"
        for label, band in sorted_levels:
            chosen = label
            if score <= band.threshold:
                return label
        return chosen


class PlannedTask(BaseModel):
    """规划后的单个任务。"""

    task_id: str
    phase: MissionPhase
    task_type: str
    required_capabilities: List[str]
    recommended_equipment: List[EquipmentNeed]
    duration_minutes: PositiveInt
    dependencies: List[str]
    parallel_allowed: bool
    description: Optional[str] = None
    safety_notes: Optional[str] = None
    severity_label: Optional[str] = None


class PlannedMission(BaseModel):
    """规划输出结构。"""

    hazard_type: str
    severity_label: str
    tasks: List[PlannedTask]
    risk_rules: List[RiskRule] = Field(default_factory=list)
    reference_cases: List[ReferenceCase] = Field(default_factory=list)


class ResourceCandidate(BaseModel):
    """可调度资源信息。"""

    resource_id: str
    name: Optional[str] = None
    kind: Literal["rescue_team", "uav", "robotic_dog", "usv", "other"] = "rescue_team"
    capabilities: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    speed_kmh: Optional[float] = Field(None, ge=0.0)
    location: Optional[GeoPoint] = None
    availability: bool = True

    @field_validator("capabilities", mode="before")
    @classmethod
    def _normalize_caps(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip().lower() for item in value]
        return [str(value).strip().lower()]

    @field_validator("equipment", mode="before")
    @classmethod
    def _normalize_equipment(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip().lower() for item in value]
        return [str(value).strip().lower()]


class ResourceMatch(BaseModel):
    """资源匹配详情。"""

    task_id: str
    resource_id: str
    match_score: float = Field(..., ge=0.0)
    capability_coverage: float = Field(..., ge=0.0, le=1.0)
    distance_km: Optional[float] = Field(None, ge=0.0)
    lacking_capabilities: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ResourcePlanningResult(BaseModel):
    """资源匹配输出。"""

    matches: List[ResourceMatch]
    unmatched_tasks: List[str] = Field(default_factory=list)
    unused_resources: List[str] = Field(default_factory=list)


class RescueTaskPlanRequest(BaseModel):
    """下发给 Java 的任务规划请求结构。"""

    incident_id: str
    hazard_type: str
    severity_label: str
    tasks: List[PlannedTask]
    resource_matches: List[ResourceMatch]
    risk_rules: List[RiskRule] = Field(default_factory=list)
    reference_cases: List[ReferenceCase] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_plan(
        cls,
        incident_id: str,
        mission: PlannedMission,
        resource_matches: Sequence[ResourceMatch],
        metadata: Optional[Dict[str, str]] = None,
    ) -> "RescueTaskPlanRequest":
        return cls(
            incident_id=incident_id,
            hazard_type=mission.hazard_type,
            severity_label=mission.severity_label,
            tasks=mission.tasks,
            resource_matches=list(resource_matches),
            risk_rules=mission.risk_rules,
            reference_cases=mission.reference_cases,
            metadata=metadata or {},
        )
