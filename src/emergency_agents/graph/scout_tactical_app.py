from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, NotRequired, Optional, Required, Sequence, Tuple, TypedDict

import structlog
from langgraph.graph import task

from emergency_agents.control.models import DeviceType
from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.external.amap_client import AmapClient, Coordinate, RoutePlan
from emergency_agents.external.device_directory import DeviceDirectory, DeviceEntry
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from emergency_agents.risk.repository import RiskDataRepository

logger = structlog.get_logger(__name__)


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


class SelectedDevice(TypedDict):
    """选中的设备信息 - 设备选择节点的输出"""
    device_id: Required[str]  # 设备ID (必填)
    name: Required[str]  # 设备名称 (必填)
    device_type: Required[str]  # 设备类型 (必填,如'uav','robotdog')
    vendor: NotRequired[Optional[str]]  # 厂商 (可选)
    capabilities: NotRequired[List[str]]  # 能力列表 (可选,如['flight','camera','infrared'])


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


class ScoutTacticalState(TypedDict):
    """侦察战术图状态 - 使用Required/NotRequired明确标注字段必选性

    这是LangGraph状态定义,必须严格遵循强类型约束:
    - Required[T]: 明确必填字段
    - NotRequired[T]: 明确可选字段
    - 绝对禁止使用total=False (会使所有字段变为可选)
    """
    incident_id: Required[str]  # 事件ID (必填)
    user_id: Required[str]  # 用户ID (必填)
    thread_id: Required[str]  # 线程ID (必填)
    slots: NotRequired[ScoutTaskGenerationSlots]  # 意图槽位 (可选,用于细化需求)
    selected_devices: NotRequired[List[SelectedDevice]]  # 已选设备列表 (可选,device_selection节点输出)
    recon_route: NotRequired[ReconRoute]  # 侦察路线 (可选,recon_route_planning节点输出)
    sensor_assignments: NotRequired[List[SensorAssignment]]  # 传感器分配列表 (可选,sensor_payload_assignment节点输出)


@dataclass(slots=True)
class ScoutTacticalGraph:
    risk_repository: RiskDataRepository
    device_directory: Optional[DeviceDirectory] = None  # 设备目录(可选,用于设备选择)
    amap_client: Optional[AmapClient] = None  # 高德地图客户端(可选,用于路线规划)

    async def invoke(
        self,
        state: ScoutTacticalState,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """侦察战术图主入口 - 串联执行所有节点

        执行流程:
        1. 生成侦察计划(基于风险点)
        2. [可选] 设备选择(如果提供device_directory)
        3. [可选] 路线规划(如果提供amap_client和已选设备)
        4. [可选] 传感器分配(如果有设备和航点)

        Args:
            state: 侦察战术状态
            config: 配置(如durability级别)

        Returns:
            Dict包含: scout_plan, selected_devices, recon_route, sensor_assignments, response_text
        """
        slots = state.get("slots")
        incident_id = state.get("incident_id", "")

        # 步骤1: 生成基础侦察计划(基于风险点)
        zones = await self.risk_repository.list_active_zones()
        plan = self._build_plan(incident_id, slots, zones)
        logger.info(
            "scout_plan_generated",
            incident_id=incident_id,
            target_count=len(plan.get("targets", [])),
            risk_count=plan["overview"].get("riskSummary", {}).get("total", 0),
        )

        result: Dict[str, Any] = {
            "status": "ok",
            "scout_plan": plan,
        }

        # 步骤2: 设备选择(如果配置了设备目录)
        if self.device_directory:
            required_sensors = plan.get("recommendedSensors", [])
            prefer_type = DeviceType.UAV  # 默认优先使用无人机
            selected_devices = select_devices_for_recon_task(
                device_directory=self.device_directory,
                required_sensors=required_sensors,
                prefer_device_type=prefer_type,
            )
            result["selected_devices"] = selected_devices
            logger.info(
                "scout_devices_selected",
                selected_count=len(selected_devices),
                device_ids=[d["device_id"] for d in selected_devices],
            )

            # 步骤3: 路线规划(如果有设备且配置了amap_client)
            if selected_devices and self.amap_client:
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

                # 假设起点为第一个目标附近(简化实现,未来可从incident坐标获取)
                origin: Coordinate = targets[0][1] if targets else {"lng": 120.0, "lat": 30.0}

                recon_route = await plan_recon_route_task(
                    origin=origin,
                    targets=targets,
                    amap_client=self.amap_client,
                )
                result["recon_route"] = recon_route
                logger.info(
                    "scout_route_planned",
                    waypoint_count=len(recon_route["waypoints"]),
                    total_distance_m=recon_route["total_distance_m"],
                )

                # 步骤4: 传感器分配(如果有设备和航点)
                waypoints = recon_route["waypoints"]
                if waypoints:
                    sensor_assignments = assign_sensor_payloads_task(
                        devices=selected_devices,
                        waypoints=waypoints,
                        required_sensors=required_sensors,
                    )
                    result["sensor_assignments"] = sensor_assignments
                    logger.info(
                        "scout_sensors_assigned",
                        assignment_count=len(sensor_assignments),
                    )

        # 生成响应文本
        response_text = self._compose_response(plan)
        result["response_text"] = response_text

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


# ============================================================================
# LangGraph Task Functions - 使用@task包装确保幂等性
# ============================================================================


@task
def select_devices_for_recon_task(
    device_directory: DeviceDirectory,
    required_sensors: List[str],
    prefer_device_type: Optional[DeviceType] = None,
) -> List[SelectedDevice]:
    """设备选择任务 - 查询设备目录并按传感器需求筛选

    这是一个带@task装饰器的幂等函数,用于:
    1. 从设备目录查询所有可用设备
    2. 按设备类型筛选(如只选UAV)
    3. 根据传感器需求匹配设备能力

    Args:
        device_directory: 设备目录查询服务
        required_sensors: 所需传感器列表(如['gas_detector','visible_light_camera'])
        prefer_device_type: 优先设备类型(如DeviceType.UAV,可选)

    Returns:
        List[SelectedDevice]: 选中的设备列表(包含设备ID、名称、类型、能力)

    幂等性保证: @task装饰器确保相同输入返回相同结果
    """
    # 从设备目录获取所有设备
    all_devices = list(device_directory.list_entries())
    logger.info(
        "device_selection_started",
        total_devices=len(all_devices),
        required_sensors=required_sensors,
        prefer_type=prefer_device_type.value if prefer_device_type else None,
    )

    # 按设备类型筛选
    candidates: List[DeviceEntry] = []
    if prefer_device_type:
        candidates = [
            dev for dev in all_devices
            if dev.device_type == prefer_device_type
        ]
        logger.info(
            "device_selection_filtered_by_type",
            prefer_type=prefer_device_type.value,
            filtered_count=len(candidates),
        )
    else:
        candidates = all_devices

    # 如果没有设备,返回空列表
    if not candidates:
        logger.warning("device_selection_no_candidates", required_sensors=required_sensors)
        return []

    # 简化实现:暂时返回所有候选设备
    # TODO: 未来可根据required_sensors精确匹配设备能力字段
    selected: List[SelectedDevice] = []
    for dev in candidates:
        selected_dev: SelectedDevice = {
            "device_id": dev.device_id,
            "name": dev.name,
            "device_type": dev.device_type.value if dev.device_type else "unknown",
        }
        if dev.vendor:
            selected_dev["vendor"] = dev.vendor

        # 根据设备类型推断能力(基于现有业务逻辑)
        capabilities: List[str] = []
        if dev.device_type == DeviceType.UAV:
            capabilities.extend(["flight", "camera", "gps"])
            if "gas" in " ".join(required_sensors).lower():
                capabilities.append("gas_detector")
        elif dev.device_type == DeviceType.ROBOTDOG:
            capabilities.extend(["ground_movement", "camera", "thermal_imaging"])
        elif dev.device_type == DeviceType.UGV:
            capabilities.extend(["ground_movement", "camera"])
        elif dev.device_type == DeviceType.USV:
            capabilities.extend(["water_surface", "sonar", "camera"])

        if capabilities:
            selected_dev["capabilities"] = capabilities

        selected.append(selected_dev)

    logger.info(
        "device_selection_completed",
        selected_count=len(selected),
        device_ids=[d["device_id"] for d in selected],
    )
    return selected


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


def build_scout_tactical_graph(
    *,
    risk_repository: RiskDataRepository,
    device_directory: Optional[DeviceDirectory] = None,
    amap_client: Optional[AmapClient] = None,
) -> ScoutTacticalGraph:
    """构建侦察战术图

    Args:
        risk_repository: 风险数据仓库(必需)
        device_directory: 设备目录(可选,提供则启用设备选择功能)
        amap_client: 高德地图客户端(可选,提供则启用路线规划功能)

    Returns:
        ScoutTacticalGraph实例
    """
    return ScoutTacticalGraph(
        risk_repository=risk_repository,
        device_directory=device_directory,
        amap_client=amap_client,
    )
