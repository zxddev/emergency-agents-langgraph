from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, NotRequired, Optional, Required, Sequence, Tuple, TypedDict, Awaitable, Literal, Iterable

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.func import task
from langgraph.graph import StateGraph
from psycopg_pool import AsyncConnectionPool

from emergency_agents.control.models import DeviceType
from emergency_agents.db.dao import RescueTaskRepository, serialize_dataclass
from emergency_agents.db.models import (
    RiskZoneRecord,
    TaskCreateInput,
    TaskRoutePlanCreateInput,
)
from emergency_agents.external.amap_client import AmapClient, Coordinate, RoutePlan
from emergency_agents.external.device_directory import DeviceDirectory, DeviceEntry
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from emergency_agents.risk.repository import RiskDataRepository

logger = structlog.get_logger(__name__)

_SENSOR_DISPLAY_LABELS: Dict[str, str] = {
    "camera": "高清相机",
    "gas_detector": "气体检测",
    "thermal_imaging": "热成像",
    "sonar": "声呐",
    "depth_camera": "深度成像",
}

_SENSOR_KEYWORDS: Dict[str, Iterable[str]] = {
    "gas_detector": ("gas", "气", "有毒", "检测"),
    "thermal_imaging": ("thermal", "infrared", "热成像", "红外"),
    "sonar": ("sonar", "声呐"),
    "depth_camera": ("depth", "lidar", "激光", "深度"),
    "camera": ("camera", "visible", "video", "摄像", "光学"),
}


def _normalize_sensor_name(value: str) -> Optional[str]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    for token, keywords in _SENSOR_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return token
    return None


def _normalize_sensor_list(values: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for item in values:
        token = _normalize_sensor_name(item)
        if token:
            normalized.append(token)
    if not normalized:
        normalized.append("camera")
    seen: set[str] = set()
    unique: List[str] = []
    for item in normalized:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _sensor_display(tokens: Iterable[str]) -> str:
    friendly: List[str] = []
    for token in tokens:
        label = _SENSOR_DISPLAY_LABELS.get(token, token.replace("_", " "))
        friendly.append(label)
    return "、".join(friendly)


def _evaluate_device_selection(
    *,
    device_directory: DeviceDirectory,
    required_sensors: Sequence[str],
    prefer_device_type: Optional[DeviceType],
) -> DeviceSelectionOutcome:
    normalized_required = _normalize_sensor_list(required_sensors)

    all_devices = list(device_directory.list_entries())
    logger.info(
        "device_selection_started",
        total_devices=len(all_devices),
        required_sensors=list(required_sensors),
        normalized_required=normalized_required,
        prefer_type=prefer_device_type.value if prefer_device_type else None,
    )

    if prefer_device_type:
        candidates = [
            dev for dev in all_devices if dev.device_type == prefer_device_type
        ]
    else:
        candidates = all_devices

    if not candidates:
        logger.warning(
            "device_selection_no_candidates",
            required_sensors=normalized_required,
        )
        return {
            "status": "none",
            "missingSensors": list(normalized_required),
            "coverageSensors": [],
            "devices": [],
            "usableDevices": [],
        }

    selected: List[SelectedDevice] = []
    usable_devices: List[SelectedDevice] = []
    coverage_tokens: set[str] = set()

    for dev in candidates:
        selected_dev: SelectedDevice = {
            "device_id": dev.device_id,
            "name": dev.name,
            "device_type": dev.device_type.value if dev.device_type else "unknown",
        }
        if dev.vendor:
            selected_dev["vendor"] = dev.vendor

        capabilities: List[str] = []
        if dev.device_type == DeviceType.UAV:
            capabilities.extend(["flight", "camera", "gps"])
        elif dev.device_type == DeviceType.ROBOTDOG:
            capabilities.extend(["ground_movement", "camera", "thermal_imaging"])
        elif dev.device_type == DeviceType.UGV:
            capabilities.extend(["ground_movement", "camera", "depth_camera"])
        elif dev.device_type == DeviceType.USV:
            capabilities.extend(["water_surface", "sonar", "camera"])
        if capabilities:
            selected_dev["capabilities"] = capabilities

        matched = [token for token in normalized_required if token in capabilities]
        missing = [token for token in normalized_required if token not in matched]
        if matched:
            coverage_tokens.update(matched)
            usable_devices.append(
                {
                    **selected_dev,
                    "matchedSensors": matched,
                    "missingSensors": missing,
                }
            )
        selected_dev["matchedSensors"] = matched
        selected_dev["missingSensors"] = missing
        selected.append(selected_dev)

    if not usable_devices:
        logger.warning(
            "device_selection_without_capability",
            required_sensors=normalized_required,
            candidate_ids=[dev["device_id"] for dev in selected],
        )
        return {
            "status": "none",
            "missingSensors": list(normalized_required),
            "coverageSensors": [],
            "devices": selected,
            "usableDevices": [],
        }

    missing_overall = [token for token in normalized_required if token not in coverage_tokens]
    status: Literal["full", "partial"]
    if missing_overall:
        status = "partial"
    else:
        status = "full"

    outcome: DeviceSelectionOutcome = {
        "status": status,
        "missingSensors": missing_overall,
        "coverageSensors": sorted(coverage_tokens),
        "devices": selected,
        "usableDevices": usable_devices,
    }
    logger.info(
        "device_selection_completed",
        status=status,
        coverage=list(coverage_tokens),
        missing=missing_overall,
        usable_ids=[dev["device_id"] for dev in usable_devices],
    )
    return outcome


class ScoutPlanOverview(TypedDict):
    """侦察计划概览 - 使用Required/NotRequired明确标注字段必选性"""
    incidentId: Required[str]  # 事件ID (必填)
    generatedAt: Required[str]  # 生成时间 (必填)
    riskSummary: Required[Dict[str, Any]]  # 风险汇总 (必填)
    targetType: NotRequired[Optional[str]]  # 目标类型 (可选)
    objective: NotRequired[Optional[str]]  # 侦察目标 (可选)


class ScoutPlanTarget(TypedDict):
    """侦察目标点 - 使用Required/NotRequired明确标注字段必选性"""
    targetId: Required[str]  # 目标ID (必填)
    hazardType: Required[str]  # 灾害类型 (必填)
    severity: Required[int]  # 严重等级 (必填)
    location: Required[Dict[str, float]]  # 位置坐标 (必填)
    priority: Required[str]  # 优先级 (必填)
    notes: NotRequired[Optional[str]]  # 备注信息 (可选)


class ScoutPlan(TypedDict):
    """完整侦察计划 - 使用Required/NotRequired明确标注字段必选性"""
    overview: Required[ScoutPlanOverview]  # 计划概览 (必填)
    targets: Required[List[ScoutPlanTarget]]  # 侦察目标列表 (必填)
    intelRequirements: Required[List[Dict[str, Any]]]  # 情报需求 (必填)
    recommendedSensors: Required[List[str]]  # 推荐传感器 (必填)
    riskHints: Required[List[str]]  # 风险提示 (必填)
    executionAdvice: NotRequired[Dict[str, Any]]  # 执行建议 (可选)


class SelectedDevice(TypedDict):
    """选中的设备信息 - 设备选择节点的输出"""
    device_id: Required[str]  # 设备ID (必填)
    name: Required[str]  # 设备名称 (必填)
    device_type: Required[str]  # 设备类型 (必填,如'uav','robotdog')
    vendor: NotRequired[Optional[str]]  # 厂商 (可选)
    capabilities: NotRequired[List[str]]  # 能力列表 (可选,如['flight','camera','infrared'])
    matchedSensors: NotRequired[List[str]]  # 已覆盖传感器 (可选)
    missingSensors: NotRequired[List[str]]  # 仍缺传感器 (可选)


class DeviceSelectionOutcome(TypedDict):
    """设备筛选结果摘要。"""

    status: Required[Literal["full", "partial", "none"]]  # 覆盖状态
    missingSensors: Required[List[str]]  # 整体仍缺的传感器
    coverageSensors: Required[List[str]]  # 已覆盖的传感器
    devices: Required[List[SelectedDevice]]  # 全量候选设备
    usableDevices: Required[List[SelectedDevice]]  # 可实际执行的设备(具备至少一个传感器)


class ReconWaypoint(TypedDict):
    """侦察航点 - 路线规划节点的输出"""
    sequence: Required[int]  # 序号 (必填,从1开始)
    location: Required[Coordinate]  # 坐标 (必填,经纬度)
    target_id: NotRequired[str]  # 关联的目标ID (可选,对应风险点ID)
    action: NotRequired[str]  # 该点的动作 (可选,如'observe','photograph','sample')
    duration_sec: NotRequired[int]  # 停留时长(秒) (可选)


class ReconRoute(TypedDict):
    """完整侦察路线 - 路线规划节点的输出"""
    waypoints: Required[List[ReconWaypoint]]  # 航点列表 (必填)
    total_distance_m: Required[int]  # 总里程(米) (必填)
    total_duration_sec: Required[int]  # 总时长(秒) (必填)
    route_plan: NotRequired[RoutePlan]  # 高德路线详情 (可选,用于调试)


class SensorAssignment(TypedDict):
    """传感器分配 - 传感器载荷分配节点的输出"""
    device_id: Required[str]  # 设备ID (必填)
    waypoint_sequence: Required[int]  # 关联的航点序号 (必填)
    sensors: Required[List[str]]  # 分配的传感器列表 (必填,如['camera','thermal_imaging'])
    task_description: Required[str]  # 任务描述 (必填,如'拍摄可见光照片并记录温度')
    priority: NotRequired[int]  # 优先级 (可选,1-5,5最高)


class WaypointRisk(TypedDict):
    """航点风险评估 - risk_overlay节点的输出"""
    waypoint_sequence: Required[int]  # 航点序号 (必填)
    risk_level: Required[int]  # 风险等级 (必填,0-5)
    hazard_types: Required[List[str]]  # 危险类型列表 (必填,如['landslide','aftershock'])


class ScoutTacticalState(TypedDict):
    """侦察战术图状态 - 使用Required/NotRequired明确标注字段必选性

    这是LangGraph状态定义,必须严格遵循强类型约束:
    - Required[T]: 明确必填字段
    - NotRequired[T]: 明确可选字段
    - 绝对禁止使用total=False (会使所有字段变为可选)

    参考: rescue_tactical_app.py:106-156 的最佳实践
    """
    # 核心标识字段 (必填)
    incident_id: Required[str]  # 事件ID
    user_id: Required[str]  # 用户ID
    thread_id: Required[str]  # 线程ID

    # 输入槽位 (可选)
    slots: NotRequired[ScoutTaskGenerationSlots]  # 意图槽位,用于细化需求

    # 流程状态 (可选)
    status: NotRequired[str]  # 执行状态 (ok/error)
    error: NotRequired[str]  # 错误信息

    # 节点输出 (可选,各节点逐步填充)
    scout_plan: NotRequired[ScoutPlan]  # 侦察计划 (build_intel_requirements输出)
    selected_devices: NotRequired[List[SelectedDevice]]  # 已选设备 (device_selection输出)
    device_selection_result: NotRequired[DeviceSelectionOutcome]  # 设备筛选结果
    recon_route: NotRequired[ReconRoute]  # 侦察路线 (route_planning输出)
    sensor_assignments: NotRequired[List[SensorAssignment]]  # 传感器分配 (sensor_assignment输出)
    waypoint_risks: NotRequired[List[WaypointRisk]]  # 航点风险 (risk_overlay输出)

    # 持久化结果 (可选)
    persisted_task: NotRequired[Dict[str, Any]]  # 已保存的任务记录 (persist_task输出)
    persisted_routes: NotRequired[List[Dict[str, Any]]]  # 已保存的路线记录 (persist_task输出)

    # 输出数据 (可选)
    ui_actions: NotRequired[List[Dict[str, Any]]]  # 前端UI动作 (prepare_response输出)
    response_text: NotRequired[str]  # 响应文本 (prepare_response输出)
    ws_payload: NotRequired[Dict[str, Any]]  # WebSocket推送内容 (ws_notify输出)


class ScoutTacticalGraph:
    """侦察战术图 - 基于StateGraph的节点化流程

    这是重构后的ScoutTacticalGraph类,遵循LangGraph最佳实践:
    1. 所有依赖Required,不允许Optional(符合"不做降级"原则)
    2. 使用StateGraph节点化流程,而非单一invoke()方法
    3. 通过闭包捕获依赖,传递给节点函数
    4. 支持durability="sync"持久化长流程状态
    5. 支持人工审批中断点(未来扩展)

    参考: rescue_tactical_app.py:303-921 的最佳实践实现
    """

    def __init__(
        self,
        *,
        risk_repository: RiskDataRepository,
        device_directory: DeviceDirectory,  # Required,不再是Optional
        amap_client: AmapClient,  # Required,不再是Optional
        orchestrator_client: OrchestratorClient,  # 新增: 后台通知客户端
        task_repository: RescueTaskRepository,  # 新增: 任务数据仓库
        postgres_dsn: str,  # 新增: PostgreSQL连接字符串
        checkpoint_schema: str = "scout_tactical_checkpoint",  # 检查点表名
    ) -> None:
        """初始化侦察战术图

        Args:
            risk_repository: 风险数据仓库(必需)
            device_directory: 设备目录(必需,不再可选)
            amap_client: 高德地图客户端(必需,不再可选)
            orchestrator_client: Orchestrator客户端(必需,用于WebSocket通知)
            task_repository: 任务数据仓库(必需,用于持久化任务)
            postgres_dsn: PostgreSQL连接字符串(必需,用于检查点)
            checkpoint_schema: 检查点表名(可选,默认scout_tactical_checkpoint)

        注意: 所有依赖都是Required,启动时就会验证完整性,
              不会在运行时降级处理(符合"不做fallback"原则)
        """
        # 存储所有依赖为实例变量
        self._risk_repository = risk_repository
        self._device_directory = device_directory
        self._amap_client = amap_client
        self._orchestrator_client = orchestrator_client
        self._task_repository = task_repository
        self._postgres_dsn = postgres_dsn
        self._checkpoint_schema = checkpoint_schema

        # 构建StateGraph(将在Phase 4实现)
        self._graph = self._build_graph()

        # 检查点和编译后的图(将在build()类方法中初始化)
        self._checkpointer: Optional[AsyncPostgresSaver] = None
        self._compiled: Optional[Any] = None
        self._checkpoint_close: Optional[Callable[[], Awaitable[None]]] = None

    def _build_graph(self) -> StateGraph:
        """构建StateGraph - 8个节点的侦察战术流程

        节点流程:
        build_intel_requirements → device_selection → route_planning
        → sensor_assignment → risk_overlay → persist_task
        → prepare_response → ws_notify → END

        每个节点使用闭包捕获self._xxx依赖,调用对应的@task函数

        参考: rescue_tactical_app.py:397-905 的节点构建模式
        """
        graph = StateGraph(ScoutTacticalState)

        # ========== 节点1: build_intel_requirements ==========
        async def build_intel_requirements(state: ScoutTacticalState) -> Dict[str, Any]:
            """生成情报需求 - 基于风险点生成侦察计划

            输入: state["slots"], state["incident_id"]
            输出: state["scout_plan"]
            """
            # 幂等性检查
            if "scout_plan" in state and state.get("scout_plan"):
                logger.info("build_intel_requirements_skip_existing")
                return {}  # 已有计划,跳过

            slots = state.get("slots")
            incident_id = state.get("incident_id", "")

            # 查询活跃风险区域
            zones = await self._risk_repository.list_active_zones()

            # 调用辅助方法生成计划(复用现有逻辑)
            plan = self._build_plan(incident_id, slots, zones)

            logger.info(
                "build_intel_requirements_completed",
                incident_id=incident_id,
                target_count=len(plan.get("targets", [])),
            )
            return {"scout_plan": plan}

        # ========== 节点2: device_selection ==========
        async def device_selection(state: ScoutTacticalState) -> Dict[str, Any]:
            """设备选择 - 根据传感器需求筛选设备

            输入: state["scout_plan"]
            输出: state["selected_devices"]
            """
            # 幂等性检查
            if "selected_devices" in state and state.get("selected_devices"):
                logger.info("device_selection_skip_existing")
                return {}

            plan = state.get("scout_plan")
            if not plan:
                logger.warning("device_selection_no_plan")
                return {"selected_devices": []}

            required_sensors = plan.get("recommendedSensors", [])

            # 调用@task函数(闭包捕获self._device_directory)
            selection = await select_devices_for_recon_task(
                device_directory=self._device_directory,
                required_sensors=required_sensors,
                prefer_device_type=DeviceType.UAV,
            )

            usable = selection["usableDevices"]
            if not usable:
                logger.warning(
                    "device_selection_no_usable_device",
                    missing=selection["missingSensors"],
                )

            logger.info(
                "device_selection_completed",
                selected_count=len(usable),
                status=selection["status"],
            )
            return {
                "selected_devices": usable,
                "device_selection_result": selection,
            }

        # ========== 节点3: route_planning ==========
        async def route_planning(state: ScoutTacticalState) -> Dict[str, Any]:
            """路线规划 - 生成多目标巡逻路线

            输入: state["scout_plan"], state["selected_devices"]
            输出: state["recon_route"]
            """
            # 幂等性检查
            if "recon_route" in state and state.get("recon_route"):
                logger.info("route_planning_skip_existing")
                return {}

            plan = state.get("scout_plan")
            devices = state.get("selected_devices", [])

            if not plan or not devices:
                logger.warning("route_planning_missing_input", has_plan=bool(plan), has_devices=bool(devices))
                return {"recon_route": {"waypoints": [], "total_distance_m": 0, "total_duration_sec": 0}}

            # 构建目标列表: [(target_id, coordinate), ...]
            targets: List[Tuple[str, Coordinate]] = []
            for target in plan.get("targets", []):
                target_id = target.get("targetId", "")
                location = target.get("location", {})
                lng = location.get("lng")
                lat = location.get("lat")
                if isinstance(lng, (int, float)) and isinstance(lat, (int, float)):
                    coord: Coordinate = {"lng": float(lng), "lat": float(lat)}
                    targets.append((target_id, coord))

            if not targets:
                logger.warning("route_planning_no_targets")
                return {"recon_route": {"waypoints": [], "total_distance_m": 0, "total_duration_sec": 0}}

            # 假设起点为第一个目标附近
            origin: Coordinate = targets[0][1]

            # 调用@task函数(闭包捕获self._amap_client)
            recon_route = await plan_recon_route_task(
                origin=origin,
                targets=targets,
                amap_client=self._amap_client,
            )

            logger.info(
                "route_planning_completed",
                waypoint_count=len(recon_route["waypoints"]),
            )
            return {"recon_route": recon_route}

        # ========== 节点4: sensor_assignment ==========
        async def sensor_assignment(state: ScoutTacticalState) -> Dict[str, Any]:
            """传感器载荷分配 - 为设备和航点分配传感器任务

            输入: state["selected_devices"], state["recon_route"], state["scout_plan"]
            输出: state["sensor_assignments"]
            """
            # 幂等性检查
            if "sensor_assignments" in state and state.get("sensor_assignments"):
                logger.info("sensor_assignment_skip_existing")
                return {}

            devices = state.get("selected_devices", [])
            route = state.get("recon_route")
            plan = state.get("scout_plan")

            if not devices or not route or not plan:
                logger.warning("sensor_assignment_missing_input")
                return {"sensor_assignments": []}

            waypoints = route.get("waypoints", [])
            required_sensors = plan.get("recommendedSensors", [])

            # 调用@task函数
            sensor_assignments = await assign_sensor_payloads_task(
                devices=devices,
                waypoints=waypoints,
                required_sensors=required_sensors,
            )

            logger.info(
                "sensor_assignment_completed",
                assignment_count=len(sensor_assignments),
            )
            return {"sensor_assignments": sensor_assignments}

        # ========== 节点5: risk_overlay ==========
        async def risk_overlay(state: ScoutTacticalState) -> Dict[str, Any]:
            """风险叠加 - 为每个航点叠加风险数据

            输入: state["recon_route"]
            输出: state["waypoint_risks"]
            """
            # 幂等性检查
            if "waypoint_risks" in state and state.get("waypoint_risks"):
                logger.info("risk_overlay_skip_existing")
                return {}

            route = state.get("recon_route")
            if not route:
                logger.warning("risk_overlay_no_route")
                return {"waypoint_risks": []}

            waypoints = route.get("waypoints", [])
            if not waypoints:
                return {"waypoint_risks": []}

            # 调用@task函数(闭包捕获self._risk_repository)
            waypoint_risks = await risk_overlay_task(
                waypoints=waypoints,
                risk_repository=self._risk_repository,
            )

            logger.info(
                "risk_overlay_completed",
                waypoint_count=len(waypoint_risks),
            )
            return {"waypoint_risks": waypoint_risks}

        # ========== 节点6: persist_task ==========
        async def persist_task_node(state: ScoutTacticalState) -> Dict[str, Any]:
            """持久化任务 - 保存侦察任务到数据库

            输入: state["scout_plan"], state["incident_id"], state["user_id"]
            输出: state["persisted_task"]
            """
            # 幂等性检查
            if "persisted_task" in state and state.get("persisted_task"):
                logger.info("persist_task_skip_existing")
                return {}

            plan = state.get("scout_plan")
            if not plan:
                logger.warning("persist_task_no_plan")
                return {}

            # 构建任务数据
            task_id = f"scout_{state['incident_id']}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            scout_task_data = {
                "task_id": task_id,
                "description": f"侦察任务 - {len(plan.get('targets', []))}个目标点",
                "incident_id": state["incident_id"],
                "user_id": state["user_id"],
                "scout_plan": plan,
            }

            # 调用@task函数(闭包捕获self._task_repository)
            persisted = await persist_scout_task(
                scout_task=scout_task_data,
                task_repository=self._task_repository,
            )

            logger.info(
                "persist_task_completed",
                task_id=task_id,
                record_id=persisted.get("task_record_id"),
            )
            return {"persisted_task": persisted}

        # ========== 节点7: prepare_response ==========
        async def prepare_response(state: ScoutTacticalState) -> Dict[str, Any]:
            """准备响应 - 生成UI动作和响应文本

            输入: state所有数据
            输出: state["ui_actions"], state["response_text"]
            """
            plan = state.get("scout_plan")
            selection = state.get("device_selection_result")
            advice: Optional[Dict[str, Any]] = None
            if plan and selection:
                advice = self._build_execution_advice(selection)
                plan["executionAdvice"] = advice

            # 生成UI动作
            ui_result = await prepare_ui_actions_task(state)
            ui_actions = ui_result.get("ui_actions", [])

            if plan:
                response_text = self._compose_response(plan, advice)
            else:
                response_text = "侦察计划生成失败"

            logger.info(
                "prepare_response_completed",
                ui_action_count=len(ui_actions),
            )
            return {
                "ui_actions": ui_actions,
                "response_text": response_text,
            }

        # ========== 节点8: ws_notify ==========
        async def ws_notify(state: ScoutTacticalState) -> Dict[str, Any]:
            """WebSocket通知 - 推送侦察场景到后台

            输入: state所有数据
            输出: state["ws_payload"]
            """
            # 构建推送载荷
            plan = state.get("scout_plan")
            devices = state.get("selected_devices", [])
            route = state.get("recon_route")

            if not plan:
                logger.warning("ws_notify_no_plan")
                return {}

            payload = {
                "taskId": state.get("persisted_task", {}).get("task_record_id", ""),
                "scenario": "scout",
                "incidentId": state["incident_id"],
                "targetCount": len(plan.get("targets", [])),
                "deviceCount": len(devices),
                "waypointCount": len(route.get("waypoints", [])) if route else 0,
            }

            # 调用@task函数(闭包捕获self._orchestrator_client)
            notify_result = await notify_backend_task(
                payload=payload,
                orchestrator=self._orchestrator_client,
            )

            logger.info(
                "ws_notify_completed",
                success=notify_result.get("success", False),
            )
            return {"ws_payload": notify_result}

        # ========== 添加节点到图 ==========
        graph.add_node("build_intel_requirements", build_intel_requirements)
        graph.add_node("device_selection", device_selection)
        graph.add_node("route_planning", route_planning)
        graph.add_node("sensor_assignment", sensor_assignment)
        graph.add_node("risk_overlay", risk_overlay)
        graph.add_node("persist_task", persist_task_node)
        graph.add_node("prepare_response", prepare_response)
        graph.add_node("ws_notify", ws_notify)

        # ========== 设置流程边 ==========
        graph.set_entry_point("build_intel_requirements")
        graph.add_edge("build_intel_requirements", "device_selection")
        graph.add_edge("device_selection", "route_planning")
        graph.add_edge("route_planning", "sensor_assignment")
        graph.add_edge("sensor_assignment", "risk_overlay")
        graph.add_edge("risk_overlay", "persist_task")
        graph.add_edge("persist_task", "prepare_response")
        graph.add_edge("prepare_response", "ws_notify")
        graph.add_edge("ws_notify", "__end__")

        logger.info("scout_tactical_graph_built", node_count=8)
        return graph

    @classmethod
    async def build(
        cls,
        *,
        risk_repository: RiskDataRepository,
        device_directory: DeviceDirectory,
        amap_client: AmapClient,
        orchestrator_client: OrchestratorClient,
        task_repository: RescueTaskRepository,
        postgres_dsn: str,
        checkpoint_schema: str = "scout_tactical_checkpoint",
    ) -> "ScoutTacticalGraph":
        """异步构建侦察战术图,绑定PostgreSQL checkpointer

        这是推荐的构建方式,确保:
        1. 所有依赖在启动时验证完整性(Required,不允许None)
        2. 异步创建PostgreSQL检查点连接池
        3. 编译StateGraph并绑定checkpointer
        4. 返回ready-to-use的图实例

        Args:
            risk_repository: 风险数据仓库(必需)
            device_directory: 设备目录(必需)
            amap_client: 高德地图客户端(必需)
            orchestrator_client: Orchestrator客户端(必需)
            task_repository: 任务数据仓库(必需)
            postgres_dsn: PostgreSQL连接字符串(必需)
            checkpoint_schema: 检查点表名(可选)

        Returns:
            ScoutTacticalGraph: 已初始化并编译的图实例

        Example:
            graph = await ScoutTacticalGraph.build(
                risk_repository=risk_repo,
                device_directory=device_dir,
                amap_client=amap,
                orchestrator_client=orchestrator,
                task_repository=task_repo,
                postgres_dsn="postgresql://user:pass@host:port/db",
            )
            result = await graph.invoke(state)
        """
        logger.info(
            "scout_tactical_graph_init",
            checkpoint_schema=checkpoint_schema,
        )

        # 创建实例
        instance = cls(
            risk_repository=risk_repository,
            device_directory=device_directory,
            amap_client=amap_client,
            orchestrator_client=orchestrator_client,
            task_repository=task_repository,
            postgres_dsn=postgres_dsn,
            checkpoint_schema=checkpoint_schema,
        )

        # 创建PostgreSQL checkpointer
        checkpointer, close_cb = await create_async_postgres_checkpointer(
            dsn=postgres_dsn,
            schema=checkpoint_schema,
            min_size=1,  # 最小连接数
            max_size=1,  # 最大连接数
        )
        instance._checkpointer = checkpointer
        instance._checkpoint_close = close_cb

        # 编译图并绑定checkpointer
        instance._compiled = instance._graph.compile(checkpointer=checkpointer)

        logger.info(
            "scout_tactical_graph_ready",
            checkpoint_schema=checkpoint_schema,
        )
        return instance

    async def invoke(
        self,
        state: ScoutTacticalState,
        config: Optional[Dict[str, Any]] = None,
    ) -> ScoutTacticalState:
        """执行侦察战术图 - 使用StateGraph编排8个节点

        这是重构后的invoke()方法,基于LangGraph StateGraph模式:
        1. 使用编译后的图(self._compiled)执行节点流程
        2. 配置durability="sync"确保每步同步持久化
        3. 支持人工审批中断点(未来扩展)

        节点流程:
        build_intel_requirements → device_selection → route_planning
        → sensor_assignment → risk_overlay → persist_task
        → prepare_response → ws_notify → END

        Args:
            state: 侦察战术状态(必须包含incident_id, user_id, thread_id)
            config: 可选配置(如durability级别,会与默认配置合并)

        Returns:
            ScoutTacticalState: 执行完成后的状态(包含所有节点输出)

        Raises:
            RuntimeError: 如果图未初始化(未调用build()方法)

        Example:
            graph = await ScoutTacticalGraph.build(...)
            state = {
                "incident_id": "INC-001",
                "user_id": "user123",
                "thread_id": "scout-INC-001",
                "slots": {...},
            }
            result = await graph.invoke(state)
            print(result["response_text"])

        参考: rescue_tactical_app.py:907-921 的invoke()实现
        """
        # 检查图是否已编译(必须先调用build())
        if self._compiled is None:
            raise RuntimeError(
                "ScoutTacticalGraph 尚未初始化完成。"
                "请使用 ScoutTacticalGraph.build() 方法创建实例。"
            )

        # 构建配置: 合并用户配置与默认配置
        if config is None:
            config = {}

        # 确保有configurable字段
        if "configurable" not in config:
            config["configurable"] = {}

        # 设置thread_id(如果未提供)
        if "thread_id" not in config["configurable"]:
            config["configurable"]["thread_id"] = state.get("thread_id", "")

        # 设置durability="sync"(长流程,每步完成后同步保存checkpoint)
        # 参考: docs/新业务逻辑md/langgraph资料/references/concept-durable-execution.md:88-90
        if "durability" not in config:
            config["durability"] = "sync"

        slots_obj = state.get("slots")
        target_type = getattr(slots_obj, "target_type", None) if slots_obj else None
        objective_summary = getattr(slots_obj, "objective_summary", None) if slots_obj else None
        coordinates = getattr(slots_obj, "coordinates", None) if slots_obj else None
        has_coordinates = isinstance(coordinates, dict) and {"lng", "lat"} <= coordinates.keys()
        logger.info(
            "scout_tactical_invoke_entry",
            thread_id=config["configurable"].get("thread_id"),
            incident_id=state.get("incident_id"),
            target_type=target_type,
            has_coordinates=has_coordinates,
            summary_length=len(objective_summary) if isinstance(objective_summary, str) else 0,
        )

        logger.info(
            "scout_tactical_invoke_start",
            thread_id=config["configurable"]["thread_id"],
            incident_id=state.get("incident_id"),
        )

        # 执行编译后的图
        result = await self._compiled.ainvoke(state, config=config)

        logger.info(
            "scout_tactical_invoke_complete",
            thread_id=config["configurable"]["thread_id"],
            status=result.get("status", "unknown"),
        )

        return result

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

    def _compose_response(self, plan: ScoutPlan, advice: Optional[Dict[str, Any]] = None) -> str:
        target_count = len(plan.get("targets", []))
        high = plan["overview"].get("riskSummary", {}).get("highSeverity", 0)
        base_text = f"已整理 {target_count} 个侦察目标，其中 {high} 个高风险点。已列出优先检查清单。"
        if not advice:
            return base_text

        status = advice.get("status")
        missing = advice.get("missingSensors", [])
        if status == "none":
            if missing:
                return f"当前无可执行侦察设备，需要尽快补充：{_sensor_display(missing)}。"
            return "当前无可执行侦察设备，请检查设备状态。"
        if status == "partial" and missing:
            return f"已生成基础侦察方案，但仍缺少：{_sensor_display(missing)}。请指挥员确认最小化执行并安排补充。"
        return base_text

    def _build_execution_advice(self, selection: DeviceSelectionOutcome) -> Dict[str, Any]:
        status = selection["status"]
        missing = selection["missingSensors"]
        coverage = selection["coverageSensors"]
        usable_ids = [device["device_id"] for device in selection["usableDevices"]]
        advice: Dict[str, Any] = {
            "status": status,
            "missingSensors": missing,
            "missingDisplay": _sensor_display(missing) if missing else "",
            "coverageSensors": coverage,
            "usableDevices": usable_ids,
        }
        if status != "full" and missing:
            advice["recommendations"] = [
                f"补充具备 { _sensor_display(missing) } 能力的侦察设备"
            ]
        return advice

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


# ============================================================================
# LangGraph Task Functions - 使用@task包装确保幂等性
# ============================================================================


@task
def select_devices_for_recon_task(
    device_directory: DeviceDirectory,
    required_sensors: List[str],
    prefer_device_type: Optional[DeviceType] = None,
) -> DeviceSelectionOutcome:
    """设备选择任务 - 查询设备目录并按传感器需求筛选。"""

    return _evaluate_device_selection(
        device_directory=device_directory,
        required_sensors=required_sensors,
        prefer_device_type=prefer_device_type,
    )


@task
async def plan_recon_route_task(
    origin: Coordinate,
    targets: List[Tuple[str, Coordinate]],  # [(target_id, coordinate), ...]
    amap_client: AmapClient,
) -> ReconRoute:
    """侦察路线规划任务 - 生成多目标巡逻航点

    这是一个带@task装饰器的幂等函数,用于:
    1. 基于起点和多个目标点生成巡逻路线
    2. 调用高德地图API计算路径
    3. 生成带序号的航点列表

    Args:
        origin: 起点坐标(如指挥部位置)
        targets: 目标列表,每个元素为(目标ID, 坐标)元组
        amap_client: 高德地图客户端

    Returns:
        ReconRoute: 完整侦察路线(包含航点、里程、时长)

    幂等性保证: @task装饰器确保相同输入返回相同结果

    实现策略: 简化版 - 按顺序访问所有目标点,返回时原路返回
    未来优化: 使用TSP算法优化访问顺序
    """
    logger.info(
        "recon_route_planning_started",
        origin=origin,
        target_count=len(targets),
    )

    if not targets:
        # 无目标,返回空路线
        logger.warning("recon_route_planning_no_targets", origin=origin)
        return {
            "waypoints": [],
            "total_distance_m": 0,
            "total_duration_sec": 0,
        }

    # 构建航点序列: 起点 → 目标1 → 目标2 → ... → 起点
    waypoints: List[ReconWaypoint] = []
    total_distance = 0
    total_duration = 0

    # 添加起点(序号0)
    waypoints.append({
        "sequence": 0,
        "location": origin,
        "action": "depart",
    })

    # 逐个访问目标点
    for idx, (target_id, target_coord) in enumerate(targets, start=1):
        # 计算从上一点到当前目标的路径
        prev_coord = waypoints[-1]["location"]
        try:
            route_plan = await amap_client.direction(
                origin=prev_coord,
                destination=target_coord,
                mode="driving",  # 使用驾车模式(适用于UAV/UGV)
            )
            segment_distance = route_plan.get("distance_meters", 0)
            segment_duration = route_plan.get("duration_seconds", 0)
        except Exception as exc:
            # 路径规划失败,使用直线距离估算
            logger.warning(
                "recon_route_segment_failed",
                from_coord=prev_coord,
                to_coord=target_coord,
                error=str(exc),
            )
            # 简化估算: 假设平均速度15m/s (54km/h)
            import math
            dx = (target_coord["lng"] - prev_coord["lng"]) * 111320  # 经度转米
            dy = (target_coord["lat"] - prev_coord["lat"]) * 110540  # 纬度转米
            segment_distance = int(math.sqrt(dx**2 + dy**2))
            segment_duration = segment_distance // 15

        total_distance += segment_distance
        total_duration += segment_duration

        # 添加目标航点
        waypoint: ReconWaypoint = {
            "sequence": idx,
            "location": target_coord,
            "target_id": target_id,
            "action": "observe",  # 默认动作:观察
            "duration_sec": 120,  # 默认停留2分钟
        }
        waypoints.append(waypoint)
        total_duration += 120  # 累加停留时间

    # 返程:从最后一个目标回到起点
    last_target_coord = waypoints[-1]["location"]
    try:
        return_route = await amap_client.direction(
            origin=last_target_coord,
            destination=origin,
            mode="driving",
        )
        return_distance = return_route.get("distance_meters", 0)
        return_duration = return_route.get("duration_seconds", 0)
    except Exception as exc:
        logger.warning(
            "recon_route_return_failed",
            from_coord=last_target_coord,
            to_coord=origin,
            error=str(exc),
        )
        import math
        dx = (origin["lng"] - last_target_coord["lng"]) * 111320
        dy = (origin["lat"] - last_target_coord["lat"]) * 110540
        return_distance = int(math.sqrt(dx**2 + dy**2))
        return_duration = return_distance // 15

    total_distance += return_distance
    total_duration += return_duration

    # 添加返回起点的航点
    waypoints.append({
        "sequence": len(waypoints),
        "location": origin,
        "action": "return",
    })

    result: ReconRoute = {
        "waypoints": waypoints,
        "total_distance_m": total_distance,
        "total_duration_sec": total_duration,
    }

    logger.info(
        "recon_route_planning_completed",
        waypoint_count=len(waypoints),
        total_distance_m=total_distance,
        total_duration_sec=total_duration,
    )
    return result


@task
def assign_sensor_payloads_task(
    devices: List[SelectedDevice],
    waypoints: List[ReconWaypoint],
    required_sensors: List[str],  # 从ScoutPlan.recommendedSensors获取
) -> List[SensorAssignment]:
    """传感器载荷分配任务 - 为设备和航点分配传感器任务

    这是一个带@task装饰器的幂等函数,用于:
    1. 根据航点的action字段确定所需传感器
    2. 将设备的能力与航点需求匹配
    3. 生成设备-航点-传感器的分配关系

    Args:
        devices: 已选设备列表(包含能力信息)
        waypoints: 航点列表(包含action和target_id)
        required_sensors: 整体推荐的传感器列表

    Returns:
        List[SensorAssignment]: 传感器分配列表

    幂等性保证: @task装饰器确保相同输入返回相同结果

    分配策略:
    - observe: 相机(可见光/热成像)
    - photograph: 高清相机
    - sample: 气体检测器/采样器
    """
    logger.info(
        "sensor_assignment_started",
        device_count=len(devices),
        waypoint_count=len(waypoints),
        required_sensors=required_sensors,
    )

    assignments: List[SensorAssignment] = []

    # 为每个有action的航点分配传感器
    for waypoint in waypoints:
        action = waypoint.get("action")
        sequence = waypoint["sequence"]

        # 跳过起点/终点航点(无实际任务)
        if action in ("depart", "return"):
            continue

        # 根据action确定所需传感器
        needed_sensors: List[str] = []
        task_desc = ""

        if action == "observe":
            needed_sensors = ["camera"]
            task_desc = f"航点{sequence}: 观察并记录现场情况"
            # 如果有热成像能力,优先使用
            if "thermal_imaging" in " ".join(required_sensors):
                needed_sensors.append("thermal_imaging")
                task_desc += ",使用热成像检测温度异常"

        elif action == "photograph":
            needed_sensors = ["camera", "gps"]
            task_desc = f"航点{sequence}: 高清拍照并记录坐标"

        elif action == "sample":
            needed_sensors = ["gas_detector"]
            task_desc = f"航点{sequence}: 气体采样和检测"
            if "气" in str(waypoint.get("target_id", "")):
                needed_sensors.append("camera")
                task_desc += ",拍摄采样现场"

        else:
            # 未知action,使用默认相机
            needed_sensors = ["camera"]
            task_desc = f"航点{sequence}: 默认观察任务"

        # 为该航点选择合适的设备
        # 简化实现:选择第一个具有所需能力的设备
        assigned_device = None
        for device in devices:
            device_capabilities = device.get("capabilities", [])
            # 检查设备是否具备所有needed_sensors
            if all(sensor in device_capabilities for sensor in needed_sensors):
                assigned_device = device
                break

        # 如果没有完全匹配的设备,选择第一个有相机的设备
        if not assigned_device:
            for device in devices:
                device_capabilities = device.get("capabilities", [])
                if "camera" in device_capabilities:
                    assigned_device = device
                    logger.warning(
                        "sensor_assignment_partial_match",
                        waypoint_seq=sequence,
                        needed=needed_sensors,
                        device_cap=device_capabilities,
                    )
                    break

        # 如果仍然没有设备,跳过该航点
        if not assigned_device:
            logger.warning(
                "sensor_assignment_no_device",
                waypoint_seq=sequence,
                needed_sensors=needed_sensors,
            )
            continue

        # 创建分配记录
        assignment: SensorAssignment = {
            "device_id": assigned_device["device_id"],
            "waypoint_sequence": sequence,
            "sensors": needed_sensors,
            "task_description": task_desc,
        }

        # 根据航点关联的风险等级设置优先级
        target_id = waypoint.get("target_id")
        if target_id and "HIGH" in str(target_id).upper():
            assignment["priority"] = 5
        elif action == "sample":
            assignment["priority"] = 4
        else:
            assignment["priority"] = 3

        assignments.append(assignment)

    logger.info(
        "sensor_assignment_completed",
        assignment_count=len(assignments),
        device_ids=list(set(a["device_id"] for a in assignments)),
    )
    return assignments


@task
async def risk_overlay_task(
    waypoints: List[ReconWaypoint],
    risk_repository: RiskDataRepository,
) -> List[WaypointRisk]:
    """风险叠加任务 - 为每个航点叠加风险数据

    这是一个带@task装饰器的幂等函数,用于:
    1. 遍历所有航点坐标
    2. 查询该坐标附近的风险区域
    3. 评估航点的综合风险等级

    Args:
        waypoints: 航点列表(包含坐标信息)
        risk_repository: 风险数据仓库

    Returns:
        List[WaypointRisk]: 航点风险评估列表(航点序号、风险等级、危险类型)

    幂等性保证: @task装饰器确保相同输入返回相同结果,
                查询风险数据库是确定性操作
    """
    logger.info(
        "risk_overlay_started",
        waypoint_count=len(waypoints),
    )

    risks: List[WaypointRisk] = []

    for waypoint in waypoints:
        sequence = waypoint["sequence"]
        coord = waypoint["location"]

        # 查询该坐标附近500米内的风险区域
        try:
            nearby_zones = await risk_repository.find_zones_near(
                lng=coord["lng"],
                lat=coord["lat"],
                radius_meters=500,
            )
        except Exception as exc:
            logger.warning(
                "risk_overlay_query_failed",
                waypoint_seq=sequence,
                coord=coord,
                error=str(exc),
            )
            nearby_zones = []

        # 计算综合风险等级: 取最高严重等级
        if nearby_zones:
            max_severity = max(zone.severity for zone in nearby_zones)
            hazard_types = [zone.hazard_type for zone in nearby_zones]
        else:
            max_severity = 0
            hazard_types = []

        risk: WaypointRisk = {
            "waypoint_sequence": sequence,
            "risk_level": max_severity,
            "hazard_types": hazard_types,
        }
        risks.append(risk)

        logger.debug(
            "risk_overlay_waypoint_evaluated",
            waypoint_seq=sequence,
            risk_level=max_severity,
            hazard_count=len(hazard_types),
        )

    logger.info(
        "risk_overlay_completed",
        total_waypoints=len(waypoints),
        high_risk_count=sum(1 for r in risks if r["risk_level"] >= 4),
    )
    return risks


@task
async def persist_scout_task(
    scout_task: Dict[str, Any],
    task_repository: RescueTaskRepository,
) -> Dict[str, Any]:
    """持久化侦察任务 - 保存任务到数据库

    这是一个带@task装饰器的幂等函数,用于:
    1. 将侦察任务数据保存到tasks表
    2. 使用task_id(code字段)作为唯一标识
    3. 如果任务已存在则跳过(幂等性保证)

    Args:
        scout_task: 侦察任务数据字典,包含:
            - task_id: 任务唯一标识
            - description: 任务描述
            - incident_id: 事件ID
            - user_id: 创建者ID
            - scout_plan: 侦察计划(存入plan_step jsonb字段)
        task_repository: 任务数据仓库

    Returns:
        Dict包含: task_record_id (数据库记录ID)

    幂等性保证: @task装饰器 + code字段唯一性约束
                重复调用不会创建重复记录
    """
    task_id = scout_task.get("task_id", "")
    logger.info(
        "persist_scout_task_started",
        task_id=task_id,
    )

    # 检查任务是否已存在(基于code字段)
    existing = await task_repository.find_by_code(task_id)
    if existing:
        logger.info(
            "persist_scout_task_already_exists",
            task_id=task_id,
            record_id=existing.id,
        )
        return {"task_record_id": existing.id}

    # 创建新任务记录
    task_input = TaskCreateInput(
        task_type="uav_recon",  # 使用现有的任务类型枚举
        status="pending",  # 初始状态为待执行
        priority=90,  # 侦察任务优先级较高
        description=scout_task.get("description", "侦察任务"),
        deadline=None,  # 侦察任务通常无固定截止时间
        target_entity_id=None,  # 可选,未来可关联具体实体
        event_id=scout_task.get("incident_id"),
        created_by=scout_task.get("user_id"),
        updated_by=scout_task.get("user_id"),
        code=task_id,  # 幂等性关键: 使用task_id作为唯一code
    )

    try:
        record = await task_repository.create_task(task_input)
        logger.info(
            "persist_scout_task_created",
            task_id=task_id,
            record_id=record.id,
        )
        return {"task_record_id": record.id}
    except Exception as exc:
        logger.error(
            "persist_scout_task_failed",
            task_id=task_id,
            error=str(exc),
        )
        raise


@task
def prepare_ui_actions_task(
    state: ScoutTacticalState,
) -> Dict[str, Any]:
    """准备UI动作 - 生成前端交互指令

    这是一个带@task装饰器的幂等函数,用于:
    1. 基于状态数据生成前端UI动作列表
    2. 包括路线预览、侦察面板打开等指令

    Args:
        state: 侦察战术状态(包含route、devices等数据)

    Returns:
        Dict包含: ui_actions (UI动作列表)

    幂等性保证: @task装饰器 + 纯计算函数(无副作用)
                相同输入总是返回相同输出
    """
    logger.info("prepare_ui_actions_started")

    route = state.get("recon_route")
    devices = state.get("selected_devices", [])
    plan = state.get("scout_plan")

    ui_actions: List[Dict[str, Any]] = []

    # 动作1: 预览侦察路线(如果有航点)
    if route and route.get("waypoints"):
        ui_actions.append({
            "action": "preview_route",
            "data": {
                "waypoints": route["waypoints"],
                "total_distance_m": route.get("total_distance_m", 0),
                "total_duration_sec": route.get("total_duration_sec", 0),
            },
        })

    # 动作2: 打开侦察控制面板(如果有设备)
    if devices:
        ui_actions.append({
            "action": "open_scout_panel",
            "data": {
                "devices": devices,
                "device_count": len(devices),
            },
        })

    # 动作3: 显示风险提示(如果有)
    if plan and plan.get("riskHints"):
        ui_actions.append({
            "action": "show_risk_hints",
            "data": {
                "hints": plan["riskHints"],
            },
        })
    if plan and plan.get("executionAdvice"):
        advice = plan["executionAdvice"]
        ui_actions.append({
            "action": "show_device_advice",
            "data": {
                "status": advice.get("status"),
                "missingSensors": advice.get("missingSensors", []),
                "recommendations": advice.get("recommendations", []),
            },
        })

    logger.info(
        "prepare_ui_actions_completed",
        action_count=len(ui_actions),
    )
    return {"ui_actions": ui_actions}


@task
def notify_backend_task(
    payload: Dict[str, Any],
    orchestrator: OrchestratorClient,
) -> Dict[str, Any]:
    """后台通知任务 - 推送侦察场景到Java后台

    这是一个带@task装饰器的幂等函数,用于:
    1. 将侦察任务推送到Orchestrator服务
    2. 触发后台的WebSocket通知和业务流程

    Args:
        payload: 推送载荷(包含taskId、scenario等数据)
        orchestrator: Orchestrator客户端

    Returns:
        Dict包含: 推送响应(success/error)

    幂等性保证: @task装饰器 + Orchestrator端需支持幂等性
                (建议Orchestrator使用taskId去重)

    注意: 如果Orchestrator服务不支持幂等性,
          重复调用可能导致重复通知,需要业务层容忍
    """
    task_id = payload.get("taskId", "")
    logger.info(
        "notify_backend_started",
        task_id=task_id,
    )

    try:
        response = orchestrator.publish_scout_scenario(payload)
        logger.info(
            "notify_backend_succeeded",
            task_id=task_id,
            response=response,
        )
        return {"success": True, "response": response}
    except Exception as exc:
        logger.error(
            "notify_backend_failed",
            task_id=task_id,
            error=str(exc),
        )
        # 不抛出异常,返回失败状态(允许流程继续)
        return {"success": False, "error": str(exc)}


def build_scout_tactical_graph(
    *,
    risk_repository: RiskDataRepository,
    device_directory: Optional[DeviceDirectory] = None,
    amap_client: Optional[AmapClient] = None,
) -> ScoutTacticalGraph:
    """[已废弃] 旧的同步工厂函数 - 请迁移到 ScoutTacticalGraph.build()

    ⚠️ 此函数已废弃,无法与新的StateGraph架构配合使用。

    迁移指南:
    --------
    旧代码:
        graph = build_scout_tactical_graph(
            risk_repository=risk_repo,
            device_directory=device_dir,
            amap_client=amap,
        )

    新代码:
        graph = await ScoutTacticalGraph.build(
            risk_repository=risk_repo,
            device_directory=device_dir,  # 现在是Required,不再Optional
            amap_client=amap,  # 现在是Required,不再Optional
            orchestrator_client=orchestrator,  # 新增必需依赖
            task_repository=task_repo,  # 新增必需依赖
            postgres_dsn="postgresql://...",  # 新增必需依赖
        )

    关键变化:
    1. 必须使用async/await调用
    2. device_directory和amap_client不再Optional(遵循"不做降级"原则)
    3. 需要提供orchestrator_client、task_repository、postgres_dsn

    Raises:
        RuntimeError: 始终抛出,提示迁移到新接口
    """
    raise RuntimeError(
        "build_scout_tactical_graph() 已废弃！\n"
        "\n"
        "新架构使用 StateGraph + PostgreSQL checkpointer,必须异步初始化。\n"
        "\n"
        "请迁移到:\n"
        "  graph = await ScoutTacticalGraph.build(\n"
        "      risk_repository=...,\n"
        "      device_directory=...,  # Required\n"
        "      amap_client=...,  # Required\n"
        "      orchestrator_client=...,  # 新增\n"
        "      task_repository=...,  # 新增\n"
        "      postgres_dsn=...,  # 新增\n"
        "  )\n"
        "\n"
        "参考: docs/新业务逻辑md/new_0.1/Scout重构-StateGraph迁移方案.md"
    )
