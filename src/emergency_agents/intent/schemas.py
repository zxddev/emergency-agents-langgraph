# Copyright 2025 msq
"""意图槽位JSON Schema定义。

使用dataclass定义各意图的槽位结构，自动生成JSON Schema用于验证。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class BaseSlots:
    """所有槽位 dataclass 的基类。"""


@dataclass
class ReconMinimalSlots(BaseSlots):
    """侦察最小化槽位。"""
    lng: float
    lat: float
    alt_m: int = 80
    steps: int = 20


@dataclass
class DeviceControlRobotdogSlots(BaseSlots):
    """机器人狗控制槽位。

    注意：action改为可选，以处理LLM提取不完整的情况。
    """
    action: Optional[str] = None
    device_id: Optional[str] = None
    distance_m: Optional[float] = None
    angle_deg: Optional[float] = None
    speed: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


@dataclass
class TrappedReportSlots(BaseSlots):
    """被困报告槽位。

    注意：count改为可选，以处理LLM提取不完整的情况。
    """
    count: Optional[int] = None
    location_text: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    time_reported: Optional[str] = None
    description: Optional[str] = None


@dataclass
class HazardReportSlots(BaseSlots):
    """灾情报告槽位。

    注意：event_type改为可选，以处理LLM提取不完整的情况。
    """
    event_type: Optional[str] = None
    location_text: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    severity: Optional[str] = None
    time_reported: Optional[str] = None
    description: Optional[str] = None
    parent_event_id: Optional[str] = None


@dataclass
class RouteSafePointQuerySlots(BaseSlots):
    """路线与安全点查询槽位。"""
    lat: float
    lng: float
    policy: str = "best"


@dataclass
class DeviceStatusQuerySlots(BaseSlots):
    """设备状态查询槽位。

    注意：所有字段均可选，以处理LLM提取不完整的情况。
    使用device_name而非device_id，支持用户自然语言输入设备名称。
    """
    device_type: Optional[str] = None
    metric: Optional[str] = None
    device_name: Optional[str] = None


@dataclass
class GeoAnnotateSlots(BaseSlots):
    """地图标注槽位。

    注意：label和geometry_type改为可选，以处理LLM提取不完整的情况。
    """
    label: Optional[str] = None
    geometry_type: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    coordinates: Optional[List[List[float]]] = None
    confidence: Optional[float] = None
    description: Optional[str] = None


@dataclass
class AnnotationSignSlots(BaseSlots):
    """标注签收槽位。"""
    annotation_id: str
    decision: str


@dataclass
class PlanTaskApprovalSlots(BaseSlots):
    """方案/任务审批槽位。"""
    target_type: str
    target_id: str
    decision: str
    reason: Optional[str] = None


@dataclass
class RfaRequestSlots(BaseSlots):
    """资源/增援请求槽位。"""
    unit_type: str
    count: int
    priority: str = "NORMAL"
    equipment: Optional[List[str]] = None
    window: Optional[str] = None


@dataclass
class EventUpdateSlots(BaseSlots):
    """事件更新槽位。

    注意：event_type和title原本是必填字段，但为了处理LLM误判或不完整输入，
    现改为可选字段。Handler应检查这些字段是否存在。
    """
    event_type: Optional[str] = None
    title: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    parent_event_id: Optional[str] = None


@dataclass
class VideoAnalyzeSlots(BaseSlots):
    """视频/报告分析槽位（报告驱动）。"""
    report_text: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    discovered_type: Optional[str] = None


@dataclass
class RescueTaskGenerationSlots(BaseSlots):
    """救援任务生成槽位。"""
    mission_type: Optional[str] = None
    location_name: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None
    situation_summary: Optional[str] = None
    disaster_type: Optional[str] = None
    impact_scope: Optional[int] = None
    simulation_only: bool = False
    task_id: Optional[str] = None
    event_type: Optional[str] = None


@dataclass
class ScoutTaskGenerationSlots(BaseSlots):
    """侦察任务生成槽位。"""
    target_type: Optional[str] = None
    location_name: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None
    priority: Optional[str] = None
    objective_summary: Optional[str] = None
    incident_stage: Optional[str] = None


@dataclass
class EvidenceBookmarkPlaybackSlots(BaseSlots):
    """证据书签/回放槽位。"""
    target_type: str
    target_id: str
    action: str
    duration_sec: Optional[int] = None
    uri: Optional[str] = None


@dataclass
class ConversationControlSlots(BaseSlots):
    """对话管控槽位。"""
    command: str


@dataclass
class GeneralChatSlots(BaseSlots):
    """通用对话槽位。

    用于处理闲聊、问候、测试等非业务对话场景。
    """
    pass  # 对话不需要特定槽位


@dataclass
class TaskProgressQuerySlots(BaseSlots):
    """任务进度查询槽位。"""
    task_id: Optional[str] = None
    task_code: Optional[str] = None
    need_route: bool = False


@dataclass
class LocationPositioningSlots(BaseSlots):
    """定位能力槽位。"""
    target_type: str
    event_id: Optional[str] = None
    event_code: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    poi_name: Optional[str] = None


@dataclass
class DeviceControlSlots(BaseSlots):
    """设备控制槽位（基础控制）。"""
    action: str
    device_type: str
    device_id: str
    action_params: Optional[Dict[str, Any]] = None


@dataclass
class VideoAnalysisSlots(BaseSlots):
    """视频流分析槽位

    用于视频流截取和GLM-4V视觉分析，支持无人机、机器狗等设备的实时画面分析。

    Attributes:
        device_name: 设备名称（用户输入的原始设备名称，如"无人机A"、"机器狗01"）
        device_type: 设备类型（uav/robotdog/camera）
        analysis_goal: 分析目标（damage_assessment/person_detection/fire_detection等）
        analysis_params: 额外的分析参数（可选）

    Note:
        Handler内部会根据device_name查询device表获取device_id，
        然后再根据device_id查询视频流地址。

    Example:
        用户说："查看无人机A的画面"
        LLM提取设备名称：
        slots = VideoAnalysisSlots(
            device_name="无人机A",  # 直接保存用户说的设备名称
            device_type="uav",
            analysis_goal="damage_assessment"
        )
    """

    device_name: str  # 用户输入的设备名称（如"无人机A"）
    device_type: str
    analysis_goal: str
    analysis_params: Optional[Dict[str, Any]] = None

@dataclass
class SystemDataQuerySlots(BaseSlots):
    """系统数据查询槽位（统一查询接口）
    
    支持查询各种系统内部数据：
    - 设备状态（carried_devices, device_by_name）
    - 车辆位置（vehicle_location）
    - 任务进度/数量/状态/指派（task_progress, task_by_code, task_count, task_status_by_name, task_assignees）
    - 事件位置（event_location, team_location）
    - POI信息（poi_location）
    
    Attributes:
        query_type: 查询类型（必填），决定调用哪个DAO方法
        query_params: 查询参数（可选），根据query_type决定具体内容
        
    Example:
        # 查询所有携带设备
        slots = SystemDataQuerySlots(
            query_type="carried_devices"
        )
        
        # 查询指定设备
        slots = SystemDataQuerySlots(
            query_type="device_by_name",
            query_params={"device_name": "无人机A"}
        )
        
        # 查询任务进度
        slots = SystemDataQuerySlots(
            query_type="task_progress",
            query_params={"task_id": "TASK-001"}
        )
    """
    query_type: str  # 查询类型（carried_devices/device_by_name/task_progress等）
    query_params: Optional[Dict[str, Any]] = None  # 查询参数


# ===== UI 控制最小槽位 =====

# ===== 通用澄清交互结构 =====
from typing import TypedDict
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class ClarifyOption(TypedDict):
    """澄清选项（强类型）。"""
    label: str
    device_id: str


class ClarifyRequest(TypedDict):
    """澄清请求（用于 interrupt 与前端 UI）。"""
    type: str  # 固定为 "clarify"
    slot: str  # 例如 "device_name"
    options: List[ClarifyOption]
    reason: NotRequired[str]
    default_index: NotRequired[int]

@dataclass
class UICameraFlytoSlots(BaseSlots):
    """UI 镜头飞行槽位。"""
    lng: float
    lat: float
    zoom: Optional[float] = None


@dataclass
class UIToggleLayerSlots(BaseSlots):
    """UI 图层显隐槽位。"""
    layer_name: Optional[str] = None
    layerCode: Optional[str] = None
    on: bool = True


def _dataclass_to_jsonschema(dc_class) -> Dict[str, Any]:
    """将dataclass转为JSON Schema。
    
    Args:
        dc_class: dataclass类型。
    
    Returns:
        JSON Schema字典。
    """
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }
    
    for f in dc_class.__dataclass_fields__.values():
        field_type = f.type
        field_type_str = str(field_type)
        
        # 处理特定的Dict字段
        if "Dict" in field_type_str and f.name == "coordinates":
            schema["properties"][f.name] = {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lng": {"type": "number"},
                },
                "required": ["lat", "lng"],
                "additionalProperties": False,
            }
        # 处理通用的Dict[str, Any]字段（如query_params）
        elif "Dict[str, typing.Any]" in field_type_str or "Dict[str, Any]" in field_type_str:
            schema["properties"][f.name] = {
                "type": "object",
                "additionalProperties": True  # 允许任意属性
            }
        elif "List[List[float]]" in field_type_str:
            schema["properties"][f.name] = {"type": "array", "items": {"type": "array", "items": {"type": "number"}}}
        elif "List[str]" in field_type_str:
            schema["properties"][f.name] = {"type": "array", "items": {"type": "string"}}
        elif "int" in field_type_str:
            schema["properties"][f.name] = {"type": "integer"}
        elif "float" in field_type_str:
            schema["properties"][f.name] = {"type": "number"}
        elif "bool" in field_type_str:
            schema["properties"][f.name] = {"type": "boolean"}
        elif "str" in field_type_str:
            schema["properties"][f.name] = {"type": "string"}
        else:
            # 对于其他未知类型，设置为object
            schema["properties"][f.name] = {"type": "object"}
        
        from dataclasses import MISSING
        # 只有非Optional字段才是required
        if f.default is MISSING and f.default_factory is MISSING and "Optional" not in field_type_str:
            schema["required"].append(f.name)
    
    return schema


INTENT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "recon_minimal": _dataclass_to_jsonschema(ReconMinimalSlots),
    "device_control_robotdog": _dataclass_to_jsonschema(DeviceControlRobotdogSlots),
    "trapped_report": _dataclass_to_jsonschema(TrappedReportSlots),
    "hazard_report": _dataclass_to_jsonschema(HazardReportSlots),
    "route_safe_point_query": _dataclass_to_jsonschema(RouteSafePointQuerySlots),
    "device_status_query": _dataclass_to_jsonschema(DeviceStatusQuerySlots),
    "geo_annotate": _dataclass_to_jsonschema(GeoAnnotateSlots),
    "annotation_sign": _dataclass_to_jsonschema(AnnotationSignSlots),
    "plan_task_approval": _dataclass_to_jsonschema(PlanTaskApprovalSlots),
    "rfa_request": _dataclass_to_jsonschema(RfaRequestSlots),
    "event_update": _dataclass_to_jsonschema(EventUpdateSlots),
    "video_analyze": _dataclass_to_jsonschema(VideoAnalyzeSlots),
    "rescue_task_generate": _dataclass_to_jsonschema(RescueTaskGenerationSlots),
    "rescue_simulation": _dataclass_to_jsonschema(RescueTaskGenerationSlots),
    "rescue-task-generate": _dataclass_to_jsonschema(RescueTaskGenerationSlots),
    "rescue-simulation": _dataclass_to_jsonschema(RescueTaskGenerationSlots),
    "scout_task_simple": _dataclass_to_jsonschema(ScoutTaskGenerationSlots),
    "scout-task-simple": _dataclass_to_jsonschema(ScoutTaskGenerationSlots),
    "evidence_bookmark_playback": _dataclass_to_jsonschema(EvidenceBookmarkPlaybackSlots),
    "conversation_control": _dataclass_to_jsonschema(ConversationControlSlots),
    "task-progress-query": _dataclass_to_jsonschema(TaskProgressQuerySlots),
    "location-positioning": _dataclass_to_jsonschema(LocationPositioningSlots),
    "device-control": _dataclass_to_jsonschema(DeviceControlSlots),
    "video-analysis": _dataclass_to_jsonschema(VideoAnalysisSlots),
    # UI 控制
    "ui_camera_flyto": _dataclass_to_jsonschema(UICameraFlytoSlots),
    "ui_toggle_layer": _dataclass_to_jsonschema(UIToggleLayerSlots),
    # 统一数据查询
    "system-data-query": _dataclass_to_jsonschema(SystemDataQuerySlots),
    # 通用对话
    "general-chat": _dataclass_to_jsonschema(GeneralChatSlots),
}


HIGH_RISK_INTENTS = {
    "device_control_robotdog",
    "plan_task_approval",
    "rescue_task_generate",
}


INTENT_SLOT_TYPES: Dict[str, type[BaseSlots]] = {
    "task-progress-query": TaskProgressQuerySlots,
    "location-positioning": LocationPositioningSlots,
    "device-control": DeviceControlSlots,
    "video-analysis": VideoAnalysisSlots,
    "recon_minimal": ReconMinimalSlots,
    "device_control_robotdog": DeviceControlRobotdogSlots,
    "trapped_report": TrappedReportSlots,
    "hazard_report": HazardReportSlots,
    "route_safe_point_query": RouteSafePointQuerySlots,
    "device_status_query": DeviceStatusQuerySlots,
    "device-status-query": DeviceStatusQuerySlots,  # 添加连字符版本
    "geo_annotate": GeoAnnotateSlots,
    "annotation_sign": AnnotationSignSlots,
    "plan_task_approval": PlanTaskApprovalSlots,
    "rfa_request": RfaRequestSlots,
    "event_update": EventUpdateSlots,
    "video_analyze": VideoAnalyzeSlots,
    "rescue_task_generate": RescueTaskGenerationSlots,
    "rescue_simulation": RescueTaskGenerationSlots,
    "rescue-task-generate": RescueTaskGenerationSlots,
    "rescue-simulation": RescueTaskGenerationSlots,
    "scout_task_simple": ScoutTaskGenerationSlots,
    "scout-task-simple": ScoutTaskGenerationSlots,
    "evidence_bookmark_playback": EvidenceBookmarkPlaybackSlots,
    "conversation_control": ConversationControlSlots,
    # UI 控制
    "ui_camera_flyto": UICameraFlytoSlots,
    "ui_toggle_layer": UIToggleLayerSlots,
    # 统一数据查询
    "system-data-query": SystemDataQuerySlots,
    # 通用对话
    "general-chat": GeneralChatSlots,
}
