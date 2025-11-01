"""侦察任务规划流水线。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Set, Tuple, Literal, runtime_checkable

from emergency_agents.planner.recon_models import (
    GeoPoint,
    HazardSnapshot,
    ReconAgent,
    ReconAssetPlan,
    ReconConstraint,
    ReconContext,
    ReconDevice,
    ReconIntent,
    ReconJustification,
    ReconPlan,
    ReconPlanMeta,
    ReconSector,
    ReconTask,
    TaskPlanPayload,
)
from emergency_agents.planner.recon_llm import (
    LLMPlanBlueprint,
    LLMTaskBlueprint,
    ReconLLMEngine,
)


KEYWORD_CATALOG = {
    "chemical": "chemical_hazard",
    "leak": "chemical_hazard",
    "危化": "chemical_hazard",
    "泄漏": "chemical_hazard",
    "slide": "landslide_risk",
    "mudslide": "landslide_risk",
    "滑坡": "landslide_risk",
    "flood": "flood_risk",
    "洪水": "flood_risk",
    "bridge": "infrastructure_damage",
    "桥": "infrastructure_damage",
    "fire": "fire_risk",
    "火灾": "fire_risk",
}

TARGET_COORD_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")


@runtime_checkable
class ReconDataGateway(Protocol):
    """侦察数据访问网关，封装权威数据源。"""

    def fetch_hazard_snapshot(self, event_id: str) -> HazardSnapshot:
        """获取事件灾情快照。"""

    def fetch_available_devices(self, event_id: str) -> List[ReconDevice]:
        """查询可调度装备列表。"""

    def fetch_available_agents(self, event_id: str) -> List[ReconAgent]:
        """查询可用侦察队伍。"""

    def fetch_blocked_routes(self, event_id: str) -> List[str]:
        """查询受阻道路编号。"""

    def fetch_existing_recon_tasks(self, event_id: str) -> List[str]:
        """查询已存在的侦察任务编号。"""


@dataclass(slots=True)
class ReconPipelineConfig:
    """侦察规划参数。"""

    default_deadline_minutes: int = 90
    min_sector_points: int = 3


class ReconPipeline:
    """侦察任务规划器。"""

    def __init__(
        self,
        gateway: ReconDataGateway,
        llm_engine: ReconLLMEngine,
        config: ReconPipelineConfig | None = None,
    ) -> None:
        if not isinstance(gateway, ReconDataGateway):
            raise TypeError("gateway 必须实现 ReconDataGateway 协议")
        if not isinstance(llm_engine, ReconLLMEngine):
            raise TypeError("llm_engine 必须实现 ReconLLMEngine 协议")
        self._gateway = gateway
        self._llm = llm_engine
        self._config = config or ReconPipelineConfig()

    def build_plan(self, command_text: str, event_id: str) -> ReconPlan:
        """从原始指令生成侦察方案。"""

        intent = self._parse_intent(command_text=command_text, event_id=event_id)
        context = self._assemble_context(intent=intent)
        blueprint = self._llm.generate_plan(intent=intent, context=context)
        return self._build_plan_from_blueprint(intent=intent, context=context, blueprint=blueprint)

    def build_task_payload(self, scheme_id: str, task: ReconTask) -> TaskPlanPayload:
        """生成写入 tasks.plan_step 的结构。"""

        return TaskPlanPayload(
            scheme_id=scheme_id,
            task_id=task.task_id,
            objective=task.objective,
            target_points=task.target_points,
            required_capabilities=task.required_capabilities,
            recommended_devices=task.recommended_devices,
            duration_minutes=task.duration_minutes,
            safety_notes=task.safety_notes,
            dependencies=task.dependencies,
            assigned_unit=task.assigned_unit,
        )

    def _parse_intent(self, *, command_text: str, event_id: str) -> ReconIntent:
        """解析指令生成意图。"""

        lowered = command_text.lower()
        keywords = [key for key in KEYWORD_CATALOG if key in lowered]
        target_spots: List[GeoPoint] = []
        seen_points: Set[Tuple[float, float]] = set()

        for match in TARGET_COORD_PATTERN.finditer(command_text):
            lon_str, lat_str = match.groups()
            try:
                lon = float(lon_str)
                lat = float(lat_str)
            except ValueError:
                continue
            point = (lon, lat)
            if point in seen_points:
                continue
            target_spots.append(GeoPoint(lon=lon, lat=lat))
            seen_points.add(point)

        # 保留原有分词逻辑，兼容带空格的场景
        for token in command_text.replace("；", " ").replace("、", " ").split():
            if "," not in token:
                continue
            parts = token.split(",")
            if len(parts) != 2:
                continue
            try:
                lon = float(parts[0])
                lat = float(parts[1])
            except ValueError:
                continue
            point = (lon, lat)
            if point in seen_points:
                continue
            target_spots.append(GeoPoint(lon=lon, lat=lat))
            seen_points.add(point)

        return ReconIntent(
            event_id=event_id,
            raw_text=command_text,
            risk_keywords=keywords,
            target_spots=target_spots,
            deadline_minutes=self._config.default_deadline_minutes,
        )

    def _assemble_context(self, *, intent: ReconIntent) -> ReconContext:
        """汇总上下文数据。"""

        hazard = self._gateway.fetch_hazard_snapshot(intent.event_id)
        devices = self._gateway.fetch_available_devices(intent.event_id)
        agents = self._gateway.fetch_available_agents(intent.event_id)
        blocked_routes = self._gateway.fetch_blocked_routes(intent.event_id)
        existing_tasks = self._gateway.fetch_existing_recon_tasks(intent.event_id)

        if not devices:
            raise ValueError("无可用侦察装备，无法编制侦察方案")

        return ReconContext(
            event_id=intent.event_id,
            hazard=hazard,
            available_devices=devices,
            available_agents=agents,
            existing_tasks=existing_tasks,
            blocked_routes=blocked_routes,
        )

    def _build_plan_from_blueprint(
        self,
        *,
        intent: ReconIntent,
        context: ReconContext,
        blueprint: LLMPlanBlueprint,
    ) -> ReconPlan:
        """将 LLM 蓝图转换为完整侦察方案。"""

        devices_map: Dict[str, ReconDevice] = {device.device_id: device for device in context.available_devices}
        if not devices_map:
            raise ValueError("无可用侦察装备，无法编制侦察方案")
        if not blueprint.tasks:
            raise ValueError("LLM 未提供任何侦察任务")

        used_devices: Set[str] = set()
        existing_ids: Set[str] = set(context.existing_tasks)
        tasks: List[ReconTask] = []
        center = self._target_center(intent=intent, context=context)

        phase_map: Dict[str, Literal["recon", "alert", "rescue", "logistics"]] = {
            "recon": "recon",
            "alert": "alert",
            "rescue": "rescue",
            "logistics": "logistics",
        }
        priority_map: Dict[str, Literal["critical", "high", "medium", "low"]] = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }

        for index, task_blueprint in enumerate(blueprint.tasks, start=1):
            device_id = task_blueprint.recommended_device
            device = devices_map.get(device_id)
            if device is None:
                raise ValueError(f"LLM 返回不存在的设备 {device_id}")
            if not device.available:
                raise ValueError(f"设备 {device_id} 当前不可用，无法派遣")
            if device_id in used_devices:
                raise ValueError(f"设备 {device_id} 已被其它任务占用，请调整任务规划")
            task_id = f"recon-{device_id}"
            if task_id in existing_ids:
                raise ValueError(f"任务 {task_id} 已存在，禁止重复生成")

            mission_phase_key = task_blueprint.mission_phase.lower()
            mission_phase = phase_map.get(mission_phase_key)
            if mission_phase is None:
                raise ValueError(f"任务阶段 {task_blueprint.mission_phase} 不受支持")

            priority_key = task_blueprint.priority.lower()
            priority = priority_map.get(priority_key)
            if priority is None:
                raise ValueError(f"任务优先级 {task_blueprint.priority} 不受支持")

            duration = task_blueprint.duration_minutes
            if duration is not None and duration <= 0:
                raise ValueError(f"任务 {task_id} 的持续时间必须为正数")
            if duration is not None and device.endurance_minutes is not None and duration > device.endurance_minutes:
                raise ValueError(f"任务 {task_id} 的持续时间超出设备续航")
            if duration is None:
                duration = device.endurance_minutes

            required_capabilities = (
                task_blueprint.required_capabilities if task_blueprint.required_capabilities else device.capabilities
            )
            if not required_capabilities:
                raise ValueError(f"设备 {device_id} 缺少能力配置，无法生成任务")

            target_points = task_blueprint.target_points[:]
            if not target_points:
                if intent.target_spots:
                    target_points = intent.target_spots[:1]
                elif center is not None:
                    target_points = [center]
                else:
                    raise ValueError(f"任务 {task_id} 缺少侦察坐标")
            else:
                target_points = target_points[:3]

            safety_notes = task_blueprint.safety_notes
            if safety_notes is None and device.category == "uav":
                safety_notes = "注意风向与禁飞区"

            tasks.append(
                ReconTask(
                    task_id=task_id,
                    title=task_blueprint.title,
                    mission_phase=mission_phase,
                    objective=task_blueprint.objective,
                    priority=priority,
                    target_points=target_points,
                    required_capabilities=required_capabilities,
                    recommended_devices=[device_id],
                    assigned_unit=None,
                    duration_minutes=duration,
                    safety_notes=safety_notes,
                    dependencies=task_blueprint.dependencies,
                )
            )
            used_devices.add(device_id)

        objectives = self._merge_objectives(
            intent=intent,
            context=context,
            llm_objectives=blueprint.objectives,
        )
        sectors = self._build_sectors(intent=intent, context=context)
        if sectors:
            sectors[0].tasks = [task.task_id for task in tasks]
        constraints = self._build_constraints(intent=intent, context=context)
        justification = self._build_justification_from_llm(
            context=context,
            blueprint=blueprint,
            constraints=constraints,
        )
        meta = self._build_meta(intent=intent, context=context)
        assets = self._build_assets(tasks=tasks, context=context)

        return ReconPlan(
            objectives=objectives,
            sectors=sectors,
            tasks=tasks,
            assets=assets,
            constraints=constraints,
            justification=justification,
            meta=meta,
        )

    def _merge_objectives(
        self,
        *,
        intent: ReconIntent,
        context: ReconContext,
        llm_objectives: List[str],
    ) -> List[str]:
        """合并 LLM 与规则目标，保持去重。"""

        merged: List[str] = []
        for item in llm_objectives[:3]:
            normalized = item.strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        for item in self._derive_objectives(intent=intent, context=context):
            if item not in merged:
                merged.append(item)
        return merged

    def _build_justification_from_llm(
        self,
        *,
        context: ReconContext,
        blueprint: LLMPlanBlueprint,
        constraints: List[ReconConstraint],
    ) -> ReconJustification:
        """根据 LLM 输出构造解释结构。"""

        risk_warnings: List[str] = [
            warn for warn in blueprint.justification.risk_warnings if warn
        ]
        for constraint in constraints:
            if constraint.detail and constraint.detail not in risk_warnings:
                risk_warnings.append(constraint.detail)
        reasoning_chain = (
            blueprint.justification.reasoning_chain
            if blueprint.justification.reasoning_chain
            else ["分析灾情快照", "整合装备能力", "调用 LLM 生成侦察任务"]
        )
        return ReconJustification(
            summary=blueprint.justification.summary,
            evidence=[f"event://{context.event_id}"],
            reasoning_chain=reasoning_chain,
            risk_warnings=risk_warnings,
        )

    def _target_center(self, *, intent: ReconIntent, context: ReconContext) -> Optional[GeoPoint]:
        """确定距离计算使用的基准坐标。"""

        if intent.target_spots:
            return intent.target_spots[0]
        if context.available_devices:
            for device in context.available_devices:
                if device.location is not None:
                    return device.location
        return None

    @staticmethod
    def _device_distance(device: ReconDevice, center: GeoPoint) -> float:
        """计算设备与目标中心的粗略距离（公里）。"""

        if device.location is None:
            return float("inf")
        lon1, lat1 = math.radians(device.location.lon), math.radians(device.location.lat)
        lon2, lat2 = math.radians(center.lon), math.radians(center.lat)
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return 6371.0 * c

    def _derive_objectives(self, *, intent: ReconIntent, context: ReconContext) -> List[str]:
        """生成方案目标。"""

        objectives: List[str] = []
        if intent.risk_keywords:
            for keyword in intent.risk_keywords:
                mapped = KEYWORD_CATALOG.get(keyword)
                if mapped == "chemical_hazard":
                    objectives.append("确认危化泄漏范围")
                elif mapped == "landslide_risk":
                    objectives.append("排查滑坡风险点")
                elif mapped == "flood_risk":
                    objectives.append("评估洪水漫延范围")
        if not objectives:
            objectives.append("获取灾情精准态势")
        if context.hazard.severity in {"high", "critical"}:
            objectives.append("持续监测高风险区域")
        return objectives

    def _build_sectors(self, *, intent: ReconIntent, context: ReconContext) -> List[ReconSector]:
        """构建侦察扇区。"""

        sector_points = intent.target_spots[:]
        if not sector_points:
            for device in context.available_devices:
                if device.location:
                    sector_points.append(device.location)
                if len(sector_points) >= self._config.min_sector_points:
                    break
        if len(sector_points) < self._config.min_sector_points:
            sector_points = [GeoPoint(lon=103.0, lat=30.0), GeoPoint(lon=103.01, lat=30.0), GeoPoint(lon=103.0, lat=30.01)]

        return [
            ReconSector(
                sector_id=f"sector-{context.event_id}",
                name="重点侦察区",
                area=sector_points,
                priority="critical" if context.hazard.severity in {"high", "critical"} else "high",
                tasks=[],
            )
        ]


    def _build_assets(self, *, tasks: List[ReconTask], context: ReconContext) -> List[ReconAssetPlan]:
        """生成资产调度计划。"""

        assets: List[ReconAssetPlan] = []
        devices_map = {device.device_id: device for device in context.available_devices}
        for task in tasks:
            device_id = task.recommended_devices[0]
            device = devices_map.get(device_id)
            if device is None:
                continue
            asset_type = device.category if device.category in {"uav", "robot_dog", "usv", "sensor", "team"} else "team"
            assets.append(
                ReconAssetPlan(
                    asset_id=device_id,
                    asset_type=asset_type,
                    usage=task.objective,
                    duration_minutes=task.duration_minutes,
                )
            )
        return assets

    def _build_constraints(self, *, intent: ReconIntent, context: ReconContext) -> List[ReconConstraint]:
        """生成执行约束。"""

        constraints: List[ReconConstraint] = []
        for route in context.blocked_routes:
            constraints.append(
                ReconConstraint(
                    name="blocked_route",
                    detail=f"道路 {route} 已封闭",
                    severity="warning",
                )
            )
        if context.hazard.severity in {"high", "critical"}:
            constraints.append(
                ReconConstraint(
                    name="high_severity",
                    detail="高风险区域需保持安全距离",
                    severity="critical",
                )
            )
        if not intent.target_spots:
            constraints.append(
                ReconConstraint(
                    name="limited_target",
                    detail="缺少精确坐标，仅根据装备位置规划",
                    severity="info",
                )
            )
        return constraints

    def _build_meta(self, *, intent: ReconIntent, context: ReconContext) -> ReconPlanMeta:
        """生成元信息。"""

        missing_fields: List[str] = []
        if not intent.target_spots:
            missing_fields.append("target_spots")
        return ReconPlanMeta(
            generated_by="ai",
            schema_version="v1",
            data_sources=["operational.events", "operational.devices", "operational.tasks"],
            missing_fields=missing_fields,
            warnings=[],
        )
