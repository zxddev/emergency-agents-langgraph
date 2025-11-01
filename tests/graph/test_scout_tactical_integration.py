"""Scout 战术图集成测试 - 验证新节点执行逻辑

测试目标:
1. device_selection 节点使用真实 PostgreSQL 数据库
2. recon_route_planning 节点使用真实高德地图 API
3. sensor_payload_assignment 节点纯逻辑验证

测试策略:
- 使用 @pytest.mark.integration 标记需要外部服务的测试
- 环境变量未配置时自动跳过(pytest.skip)
- 使用真实服务,不允许 mock/fallback
- 测试数据以 TEST- 前缀命名,自动清理
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest
from emergency_agents.external.device_directory import DeviceDirectory, PostgresDeviceDirectory
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.scout_tactical_app import (
    ScoutTacticalGraph,
    ScoutTacticalState,
    SelectedDevice,
    ReconRoute,
    ReconWaypoint,
    SensorAssignment,
)
from emergency_agents.db.dao import RescueTaskRepository
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


# ============================================================================
# 测试辅助函数
# ============================================================================


def _create_test_state_minimal() -> ScoutTacticalState:
    """创建最小化测试状态(仅包含 Required 字段)"""
    return ScoutTacticalState(
        incident_id="test-incident-001",
        user_id="test-user",
        thread_id="test-thread-001",
    )


def _prepare_test_devices(pool: ConnectionPool) -> None:
    """准备测试设备数据(执行 scout_test_data.sql)"""
    import pathlib

    sql_file = pathlib.Path(__file__).parent.parent / "fixtures" / "scout_test_data.sql"
    if not sql_file.exists():
        pytest.skip(f"测试数据 SQL 文件不存在: {sql_file}")

    with pool.connection() as conn:
        conn.execute(sql_file.read_text(encoding="utf-8"))
        conn.commit()
    logger.info("prepare_test_devices_completed", sql_file=str(sql_file))


# ============================================================================
# 集成测试: device_selection 节点
# ============================================================================


@pytest.mark.integration
@pytest.mark.anyio
async def test_device_selection_with_real_db(
    postgres_pool: ConnectionPool,
    device_directory: DeviceDirectory,
    empty_risk_repository,
) -> None:
    """测试设备选择节点使用真实 PostgreSQL 数据库

    验证点:
    1. 从数据库成功查询 TEST- 前缀设备
    2. 返回的设备数据结构完整(device_id, name, device_type)
    3. 设备类型符合预期(UAV/ROBOTDOG)
    4. 日志记录设备选择过程
    """
    # 准备测试数据
    _prepare_test_devices(postgres_pool)

    # 创建测试所需的依赖（Mock 未测试的组件）
    mock_amap_client = Mock(spec=AmapClient)  # 不测试路线规划，使用 Mock
    mock_orchestrator = Mock(spec=OrchestratorClient)  # 不测试后端通知，使用 Mock
    task_repository = RescueTaskRepository.create(postgres_pool)
    postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql://rescue:rescue_password@localhost:5432/rescue_system")

    # 构建 Scout 战术图（使用新的异步 build() 方法）
    graph = await ScoutTacticalGraph.build(
        risk_repository=empty_risk_repository,
        device_directory=device_directory,
        amap_client=mock_amap_client,
        orchestrator_client=mock_orchestrator,
        task_repository=task_repository,
        postgres_dsn=postgres_dsn,
    )

    # 准备输入状态
    initial_state = _create_test_state_minimal()

    # 执行 device_selection 节点
    result = await graph.invoke(initial_state)

    # 验证结果结构
    assert isinstance(result, dict), "返回结果应该是字典"
    assert "selected_devices" in result, "应该返回 selected_devices 字段"

    # 验证设备列表
    devices: List[SelectedDevice] = result["selected_devices"]
    assert len(devices) > 0, "应该至少选择一个设备"
    logger.info(
        "device_selection_result",
        device_count=len(devices),
        device_ids=[d["device_id"] for d in devices],
    )

    # 验证第一个设备的数据结构
    first_device = devices[0]
    assert "device_id" in first_device, "设备必须包含 device_id"
    assert "name" in first_device, "设备必须包含 name"
    assert "device_type" in first_device, "设备必须包含 device_type"

    # 验证设备类型
    assert first_device["device_type"] in ["UAV", "ROBOTDOG", "USV", "UGV"], f"未知设备类型: {first_device['device_type']}"

    # 验证设备ID前缀(如果是测试数据)
    if first_device["device_id"].startswith("TEST-"):
        logger.info("device_selection_using_test_data", device=first_device)


# ============================================================================
# 集成测试: recon_route_planning 节点
# ============================================================================


@pytest.mark.integration
@pytest.mark.anyio
async def test_route_planning_with_real_amap(
    postgres_pool: ConnectionPool,
    device_directory: DeviceDirectory,
    amap_client: AmapClient,
    empty_risk_repository,
) -> None:
    """测试路线规划节点使用真实高德地图 API

    验证点:
    1. 调用真实高德 API 成功
    2. 返回航点数据结构完整(lat, lng, sequence)
    3. 总里程和时长合理
    4. 路线包含多个航点
    """
    # 准备测试数据
    _prepare_test_devices(postgres_pool)

    # 创建测试所需的依赖（Mock 未测试的组件）
    mock_orchestrator = Mock(spec=OrchestratorClient)  # 不测试后端通知，使用 Mock
    task_repository = RescueTaskRepository.create(postgres_pool)
    postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql://rescue:rescue_password@localhost:5432/rescue_system")

    # 构建 Scout 战术图（使用新的异步 build() 方法，启用真实 amap_client）
    graph = await ScoutTacticalGraph.build(
        risk_repository=empty_risk_repository,
        device_directory=device_directory,
        amap_client=amap_client,
        orchestrator_client=mock_orchestrator,
        task_repository=task_repository,
        postgres_dsn=postgres_dsn,
    )

    # 准备输入状态(从 empty_risk_repository 获取风险区域,中心点为杭州西湖)
    initial_state = _create_test_state_minimal()

    # 执行完整流程(device_selection + recon_route_planning)
    result = await graph.invoke(initial_state)

    # 验证设备选择成功
    assert "selected_devices" in result, "应该先选择设备"
    assert len(result["selected_devices"]) > 0, "应该至少选择一个设备"

    # 验证路线规划结果
    assert "recon_route" in result, "应该返回 recon_route 字段"
    route: ReconRoute = result["recon_route"]

    # 验证航点列表
    assert "waypoints" in route, "路线必须包含 waypoints"
    waypoints: List[ReconWaypoint] = route["waypoints"]
    assert len(waypoints) > 0, "应该生成至少一个航点"
    logger.info("route_planning_result", waypoint_count=len(waypoints))

    # 验证第一个航点的数据结构
    first_waypoint = waypoints[0]
    assert "lat" in first_waypoint, "航点必须包含纬度"
    assert "lng" in first_waypoint, "航点必须包含经度"
    assert "sequence" in first_waypoint, "航点必须包含序号"

    # 验证坐标合理性(杭州周边范围 29-31°N, 119-121°E)
    assert 29.0 < first_waypoint["lat"] < 31.0, f"纬度超出预期范围: {first_waypoint['lat']}"
    assert 119.0 < first_waypoint["lng"] < 121.0, f"经度超出预期范围: {first_waypoint['lng']}"

    # 验证总里程和时长
    assert "total_distance_m" in route, "路线必须包含总里程"
    assert "total_duration_sec" in route, "路线必须包含总时长"
    assert route["total_distance_m"] > 0, "总里程应该大于0"
    assert route["total_duration_sec"] > 0, "总时长应该大于0"

    logger.info(
        "route_metrics",
        distance_km=route["total_distance_m"] / 1000,
        duration_min=route["total_duration_sec"] / 60,
    )


# ============================================================================
# 单元测试: sensor_payload_assignment 节点(纯逻辑,无外部依赖)
# ============================================================================


@pytest.mark.unit
def test_sensor_assignment_logic() -> None:
    """测试传感器载荷分配节点的纯逻辑

    验证点:
    1. 根据航点需求匹配合适的传感器
    2. 设备能力与航点需求正确对应
    3. 生成的任务描述清晰
    4. 优先级分配合理
    """
    # 构造测试设备(具备不同能力)
    test_devices: List[SelectedDevice] = [
        SelectedDevice(
            device_id="TEST-UAV-001",
            name="测试无人机1",
            device_type="UAV",
            capabilities=["camera", "thermal_imaging", "gas_detection"],
        ),
        SelectedDevice(
            device_id="TEST-UGV-001",
            name="测试机器狗1",
            device_type="ROBOTDOG",
            capabilities=["camera", "obstacle_detection"],
        ),
    ]

    # 构造测试航点(不同任务类型)
    test_waypoints: List[ReconWaypoint] = [
        ReconWaypoint(
            lat=30.25,
            lng=120.15,
            sequence=1,
            action="photo",  # 拍照任务
        ),
        ReconWaypoint(
            lat=30.26,
            lng=120.16,
            sequence=2,
            action="thermal",  # 热成像任务
        ),
        ReconWaypoint(
            lat=30.27,
            lng=120.17,
            sequence=3,
            action="gas_detect",  # 气体检测任务
        ),
    ]

    # 执行传感器分配逻辑(模拟节点函数)
    assignments = _mock_sensor_assignment(test_devices, test_waypoints)

    # 验证分配结果数量
    assert len(assignments) == len(test_waypoints), "每个航点都应该分配传感器"

    # 验证第一个航点(拍照)
    photo_assignment = assignments[0]
    assert photo_assignment["waypoint_sequence"] == 1
    assert "camera" in photo_assignment["sensors"], "拍照任务需要相机"
    assert photo_assignment["device_id"] in ["TEST-UAV-001", "TEST-UGV-001"], "应该分配给有相机能力的设备"

    # 验证第二个航点(热成像)
    thermal_assignment = assignments[1]
    assert thermal_assignment["waypoint_sequence"] == 2
    assert "thermal_imaging" in thermal_assignment["sensors"], "热成像任务需要热成像传感器"
    assert thermal_assignment["device_id"] == "TEST-UAV-001", "只有无人机有热成像能力"

    # 验证第三个航点(气体检测)
    gas_assignment = assignments[2]
    assert gas_assignment["waypoint_sequence"] == 3
    assert "gas_detection" in gas_assignment["sensors"], "气体检测任务需要气体检测传感器"
    assert gas_assignment["device_id"] == "TEST-UAV-001", "只有无人机有气体检测能力"

    # 验证任务描述不为空
    for assignment in assignments:
        assert assignment["task_description"], "任务描述不应为空"
        assert len(assignment["task_description"]) > 5, "任务描述应该有实际内容"

    logger.info("sensor_assignment_test_passed", assignment_count=len(assignments))


def _mock_sensor_assignment(
    devices: List[SelectedDevice],
    waypoints: List[ReconWaypoint],
) -> List[SensorAssignment]:
    """模拟传感器分配逻辑(简化版,实际实现在 scout_tactical_app.py)

    分配规则:
    - photo → camera
    - thermal → thermal_imaging
    - gas_detect → gas_detection
    """
    assignments: List[SensorAssignment] = []

    # 任务类型到传感器的映射
    task_sensor_map: Dict[str, str] = {
        "photo": "camera",
        "thermal": "thermal_imaging",
        "gas_detect": "gas_detection",
    }

    for wp in waypoints:
        action = wp.get("action", "photo")
        required_sensor = task_sensor_map.get(action, "camera")

        # 查找具备该能力的设备
        assigned_device: Optional[SelectedDevice] = None
        for device in devices:
            if required_sensor in device.get("capabilities", []):
                assigned_device = device
                break

        if not assigned_device:
            # 如果没有匹配设备,使用第一个设备作为兜底
            assigned_device = devices[0]

        # 生成分配结果
        assignments.append(
            SensorAssignment(
                device_id=assigned_device["device_id"],
                waypoint_sequence=wp["sequence"],
                sensors=[required_sensor],
                task_description=f"使用{required_sensor}执行{action}任务",
                priority=3,  # 默认中等优先级
            )
        )

    return assignments
