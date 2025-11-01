from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, MutableMapping, Optional, List

from typing_extensions import TypedDict


class QueryParams(TypedDict, total=False):
    """通用查询参数定义。"""

    event_id: str
    event_code: str
    team_id: str
    team_name: str
    poi_name: str
    task_id: str
    task_code: str
    device_id: str


@dataclass(slots=True)
class EventLocation:
    """事件定位信息。"""

    name: str
    lng: float
    lat: float


@dataclass(slots=True)
class EntityLocation:
    """实体或队伍的定位信息。"""

    name: str
    lng: float
    lat: float


@dataclass(slots=True)
class PoiLocation:
    """POI 点位信息。"""

    name: str
    lng: float
    lat: float


@dataclass(slots=True)
class DeviceSummary:
    """轻量级设备信息，用于控制或展示。"""

    id: str
    device_type: Optional[str]
    name: Optional[str]


@dataclass(slots=True)
class VideoDevice:
    """附带视频流地址的设备信息。"""

    id: str
    device_type: Optional[str]
    name: Optional[str]
    stream_url: Optional[str]


@dataclass(slots=True)
class TaskSummary:
    """任务概况。"""

    id: str
    code: Optional[str]
    description: Optional[str]
    status: str
    progress: Optional[int]
    updated_at: datetime


@dataclass(slots=True)
class TaskLogEntry:
    """任务最新日志条目。"""

    description: Optional[str]
    timestamp: Optional[datetime]
    recorder_name: Optional[str]


@dataclass(slots=True)
class TaskRoutePlan:
    """任务关联的路线规划。"""

    strategy: Optional[str]
    distance_meters: Optional[float]
    duration_seconds: Optional[int]


@dataclass(slots=True)
class IncidentRecord:
    """事件/事故基本信息。"""

    id: str
    parent_event_id: Optional[str]
    event_code: Optional[str]
    title: str
    type: str
    priority: int
    status: str
    description: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


@dataclass(slots=True)
class IncidentEntityLink:
    """事件与实体的关联记录。"""

    incident_id: str
    entity_id: str
    relation_type: Optional[str]
    notes: Optional[str]
    display_priority: Optional[int]
    linked_at: datetime


@dataclass(slots=True)
class EntityRecord:
    """GIS 实体信息。"""

    entity_id: str
    entity_type: str
    geometry_geojson: Mapping[str, Any]
    properties: Mapping[str, Any]
    layer_code: Optional[str]
    display_name: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class IncidentEntityDetail:
    """包含关联信息的事件实体。"""

    link: IncidentEntityLink
    entity: EntityRecord


@dataclass(slots=True)
class IncidentSnapshotRecord:
    """事件态势快照。"""

    snapshot_id: str
    incident_id: str
    snapshot_type: str
    payload: Mapping[str, Any]
    generated_at: datetime
    created_by: Optional[str]
    created_at: datetime


@dataclass(slots=True)
class IncidentSnapshotCreateInput:
    """新增事件快照的入参。"""

    incident_id: str
    snapshot_type: str
    payload: Mapping[str, Any]
    generated_at: datetime
    created_by: Optional[str]


@dataclass(slots=True)
class RiskZoneRecord:
    """危险区域记录。"""

    zone_id: str
    zone_name: str
    hazard_type: str
    severity: int
    description: Optional[str]
    geometry_geojson: Mapping[str, Any]
    properties: Mapping[str, Any]
    valid_from: datetime
    valid_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class IncidentEntityCreateInput:
    """创建事件实体及关联的入参。"""

    incident_id: str
    entity_type: str
    layer_code: str
    geometry_geojson: Mapping[str, Any]
    properties: Mapping[str, Any]
    relation_type: str = "primary"
    relation_description: Optional[str] = None
    display_priority: int = 100
    created_by: Optional[str] = None
    source: str = "system"
    is_visible_on_map: bool = True
    style_overrides: Mapping[str, Any] = field(default_factory=dict)
    image: Optional[str] = None


class RowMapping(TypedDict, total=False):
    """用于 DAO 内部的字典行类型。"""

    name: str
    lng: float
    lat: float
    id: str
    code: str
    description: str
    status: str
    progress: int
    updated_at: datetime
    recorder_name: str
    timestamp: datetime
    strategy: str
    distance_meters: float
    duration_seconds: int


class DAOResult(TypedDict, total=False):
    """DAO 调用统一返回结构。"""

    data: Any
    metadata: Mapping[str, Any]


@dataclass(slots=True)
class RescuerRecord:
    """救援力量记录。"""

    rescuer_id: str
    name: str
    rescuer_type: str
    status: Optional[str]
    availability: bool
    lng: Optional[float]
    lat: Optional[float]
    skills: List[str]
    equipment: Mapping[str, Any]


@dataclass(slots=True)
class TaskCreateInput:
    """创建任务所需参数。"""

    task_type: str
    status: str
    priority: int
    description: Optional[str]
    deadline: Optional[datetime]
    target_entity_id: Optional[str]
    event_id: Optional[str]
    created_by: str
    updated_by: str
    code: Optional[str]


@dataclass(slots=True)
class TaskRecord:
    """任务表返回结构。"""

    id: str
    task_type: str
    status: str
    priority: int
    description: Optional[str]
    deadline: Optional[datetime]
    progress: Optional[int]
    event_id: Optional[str]
    code: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class TaskRoutePlanCreateInput:
    """创建任务路线参数。"""

    task_id: str
    status: str
    strategy: Optional[str]
    origin_geojson: Optional[Mapping[str, Any]]
    destination_geojson: Optional[Mapping[str, Any]]
    polyline_geojson: Optional[Mapping[str, Any]]
    distance_meters: Optional[float]
    duration_seconds: Optional[int]
    estimated_arrival_time: Optional[datetime]
    avoid_polygons: Optional[Mapping[str, Any]]


@dataclass(slots=True)
class TaskRoutePlanRecord:
    """任务路线记录。"""

    id: str
    task_id: str
    status: str
    strategy: Optional[str]
    origin_geojson: Optional[Mapping[str, Any]]
    destination_geojson: Optional[Mapping[str, Any]]
    polyline_geojson: Optional[Mapping[str, Any]]
    distance_meters: Optional[float]
    duration_seconds: Optional[int]
    estimated_arrival_time: Optional[datetime]
    avoid_polygons: Optional[Mapping[str, Any]]
    created_at: datetime
    updated_at: datetime
