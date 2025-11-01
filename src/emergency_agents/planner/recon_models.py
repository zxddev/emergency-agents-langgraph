"""侦察方案强类型模型定义。"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, PositiveInt


class IntentPriority(str, Enum):
    """指挥意图优先级。"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GeoPoint(BaseModel):
    """地理坐标点位。"""

    lon: float = Field(..., ge=-180.0, le=180.0, description="经度值")
    lat: float = Field(..., ge=-90.0, le=90.0, description="纬度值")


class ReconIntent(BaseModel):
    """指挥员下达的侦察意图结构。"""

    event_id: str = Field(..., description="关联事件ID")
    raw_text: str = Field(..., description="原始指令文本")
    priority: IntentPriority = Field(IntentPriority.HIGH, description="任务优先级")
    target_area: Optional[List[GeoPoint]] = Field(None, description="目标区域多边形坐标")
    target_spots: List[GeoPoint] = Field(default_factory=list, description="重点关注点位列表")
    deadline_minutes: Optional[PositiveInt] = Field(None, description="完成时限")
    risk_keywords: List[str] = Field(default_factory=list, description="风险关键词")
    notes: Optional[str] = Field(None, description="指挥员补充说明")


class ReconDevice(BaseModel):
    """可用侦察装备信息。"""

    device_id: str = Field(..., description="设备编号")
    name: Optional[str] = Field(None, description="设备名称")
    category: Literal["uav", "robot_dog", "usv", "sensor", "other"] = Field("uav", description="设备类型")
    environment: Literal["air", "land", "sea", "mixed", "other"] = Field("air", description="使用环境")
    capabilities: List[str] = Field(default_factory=list, description="能力标签")
    endurance_minutes: Optional[PositiveInt] = Field(None, description="续航时间")
    payloads: List[str] = Field(default_factory=list, description="挂载传感器")
    location: Optional[GeoPoint] = Field(None, description="当前位置")
    available: bool = Field(True, description="可调度状态")


class ReconAgent(BaseModel):
    """执行侦察任务的人员或队伍。"""

    unit_id: str = Field(..., description="队伍或人员ID")
    name: Optional[str] = Field(None, description="队伍名称")
    kind: Literal["rescue_team", "uav_team", "robot_dog_team", "other"] = Field("rescue_team", description="类别")
    capabilities: List[str] = Field(default_factory=list, description="能力标签")
    contact: Optional[str] = Field(None, description="联系方式")
    location: Optional[GeoPoint] = Field(None, description="当前位置")
    available: bool = Field(True, description="可用状态")


class HazardSnapshot(BaseModel):
    """事件灾情快照。"""

    hazard_type: str = Field(..., description="灾害类型")
    severity: Literal["low", "medium", "high", "critical"] = Field("medium", description="严重程度")
    description: Optional[str] = Field(None, description="概述")
    affected_population: Optional[PositiveInt] = Field(None, description="影响人口估计")
    notes: Optional[str] = Field(None, description="补充信息")


class ReconContext(BaseModel):
    """侦察上下文数据。"""

    event_id: str = Field(..., description="事件ID")
    hazard: HazardSnapshot = Field(..., description="灾情快照")
    available_devices: List[ReconDevice] = Field(default_factory=list, description="可用装备列表")
    available_agents: List[ReconAgent] = Field(default_factory=list, description="可用队伍列表")
    existing_tasks: List[str] = Field(default_factory=list, description="当前已有任务ID")
    blocked_routes: List[str] = Field(default_factory=list, description="受阻道路")
    weather: Optional[str] = Field(None, description="气象摘要")


class ReconConstraint(BaseModel):
    """侦察约束。"""

    name: str = Field(..., min_length=1, description="约束名称")
    detail: Optional[str] = Field(None, description="约束细节")
    severity: Literal["info", "warning", "critical"] = Field("warning", description="约束等级")


class ReconTask(BaseModel):
    """单个侦察任务。"""

    task_id: str = Field(..., min_length=1, description="任务ID")
    title: str = Field(..., min_length=1, description="任务标题")
    mission_phase: Literal["recon", "alert", "rescue", "logistics"] = Field("recon", description="任务阶段")
    objective: str = Field(..., min_length=1, description="任务目标")
    priority: Literal["critical", "high", "medium", "low"] = Field("high", description="优先级")
    target_area: Optional[List[GeoPoint]] = Field(None, description="任务覆盖区域")
    target_points: List[GeoPoint] = Field(default_factory=list, description="重点坐标")
    required_capabilities: List[str] = Field(default_factory=list, description="能力要求")
    recommended_devices: List[str] = Field(default_factory=list, description="建议装备ID")
    assigned_unit: Optional[str] = Field(None, description="指定执行单位")
    duration_minutes: Optional[PositiveInt] = Field(None, description="预计用时")
    safety_notes: Optional[str] = Field(None, description="安全提示")
    dependencies: List[str] = Field(default_factory=list, description="前置任务")


class ReconAssetPlan(BaseModel):
    """执行任务的资产配置。"""

    asset_id: str = Field(..., min_length=1, description="资产ID")
    asset_type: Literal["uav", "robot_dog", "usv", "sensor", "team"] = Field("uav", description="资产类型")
    usage: str = Field(..., min_length=1, description="使用方式")
    duration_minutes: Optional[PositiveInt] = Field(None, description="使用时长")
    remarks: Optional[str] = Field(None, description="备注")


class ReconSector(BaseModel):
    """侦察作战扇区。"""

    sector_id: str = Field(..., min_length=1, description="扇区ID")
    name: str = Field(..., min_length=1, description="扇区名称")
    area: List[GeoPoint] = Field(default_factory=list, description="扇区多边形")
    priority: Literal["critical", "high", "medium", "low"] = Field("medium", description="扇区优先级")
    tasks: List[str] = Field(default_factory=list, description="扇区关联任务ID")


class ReconJustification(BaseModel):
    """AI 推理解释。"""

    summary: str = Field(..., description="总述")
    evidence: List[str] = Field(default_factory=list, description="证据ID列表")
    reasoning_chain: List[str] = Field(default_factory=list, description="推理链条")
    risk_warnings: List[str] = Field(default_factory=list, description="风险提示")


class ReconPlanMeta(BaseModel):
    """方案元信息。"""

    generated_by: Literal["ai", "manual"] = Field("ai", description="生成方式")
    schema_version: str = Field("v1", description="方案结构版本")
    data_sources: List[str] = Field(default_factory=list, description="数据来源")
    missing_fields: List[str] = Field(default_factory=list, description="缺失字段提示")
    warnings: List[str] = Field(default_factory=list, description="警告信息")


class ReconPlan(BaseModel):
    """完整侦察方案。"""

    objectives: List[str] = Field(default_factory=list, description="方案目标列表")
    sectors: List[ReconSector] = Field(default_factory=list, description="作战扇区")
    tasks: List[ReconTask] = Field(default_factory=list, description="侦察任务集合")
    assets: List[ReconAssetPlan] = Field(default_factory=list, description="资产调度计划")
    constraints: List[ReconConstraint] = Field(default_factory=list, description="执行约束")
    justification: ReconJustification = Field(..., description="AI 推理解释")
    meta: ReconPlanMeta = Field(default_factory=ReconPlanMeta, description="元信息")


class TaskPlanPayload(BaseModel):
    """写入 `operational.tasks.plan_step` 的结构。"""

    scheme_id: str = Field(..., min_length=1, description="所属方案ID")
    task_id: str = Field(..., min_length=1, description="任务ID")
    objective: str = Field(..., min_length=1, description="任务目标")
    target_points: List[GeoPoint] = Field(default_factory=list, description="目标坐标")
    required_capabilities: List[str] = Field(default_factory=list, description="能力要求")
    recommended_devices: List[str] = Field(default_factory=list, description="建议装备")
    duration_minutes: Optional[PositiveInt] = Field(None, description="预计用时")
    safety_notes: Optional[str] = Field(None, description="安全提示")
    dependencies: List[str] = Field(default_factory=list, description="依赖任务")
    assigned_unit: Optional[str] = Field(None, description="执行单位")
