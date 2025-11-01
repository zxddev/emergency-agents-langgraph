# Design: 战术侦察子图技术设计

## Architecture Overview

### LangGraph StateGraph 结构

```
                    ┌──────────────────────┐
                    │  ScoutTacticalState  │
                    │  ────────────────── │
                    │  incident_id: str    │
                    │  user_id: str        │
                    │  thread_id: str      │
                    │  slots: Slots        │
                    │  devices: List[...]  │
                    │  waypoints: List[...]│
                    │  intel_reqs: List[...]│
                    │  risk_warnings: [...] │
                    │  scout_task_id: str  │
                    │  ui_actions: List[...]│
                    └──────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │      device_selection              │
        │  ──────────────────────────────── │
        │  - 查询资产管理系统                  │
        │  - 筛选可用设备(无人机/机器人)        │
        │  - 匹配传感器能力                    │
        │  - 计算距离优先级                    │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │    recon_route_planning            │
        │  ──────────────────────────────── │
        │  - 提取目标坐标                      │
        │  - 生成巡航航点(圆形/网格模式)        │
        │  - 调用高德API获取路径(可选)          │
        │  - 设置飞行高度和速度                 │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │  sensor_payload_assignment         │
        │  ──────────────────────────────── │
        │  - 读取目标类型                      │
        │  - 分配传感器任务                    │
        │    * 坍塌→相机+红外                  │
        │    * 危化→气体+相机                  │
        │    * 洪水→相机+测距                  │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │  intel_requirement_builder         │
        │  ──────────────────────────────── │
        │  - 汇总情报需求                      │
        │  - 标记可采集项/缺失项                │
        │  - 生成优先级排序                    │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │       risk_overlay                 │
        │  ──────────────────────────────── │
        │  - 检测航点风险                      │
        │  - 标注危险区域                      │
        │  - 生成规避建议                      │
        │    * 绕行/提升高度/加速通过           │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │       persist_task (@task)         │
        │  ──────────────────────────────── │
        │  - 保存 ScoutTask 到数据库           │
        │  - 记录审计日志                      │
        │  - 返回 task_id                     │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │      prepare_response              │
        │  ──────────────────────────────── │
        │  - 生成侦察计划摘要                   │
        │  - 构建 UI Actions                  │
        │    * fly_to                         │
        │    * open_scout_panel               │
        │    * preview_route                  │
        └────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────┐
        │       ws_notify (@task)            │
        │  ──────────────────────────────── │
        │  - 推送到 Java 后台                  │
        │  - WebSocket 广播前端                │
        │  - 通知模拟器/设备通道                │
        └────────────────────────────────────┘
                             │
                             ▼
                         END (返回)
```

## State Definition

### 强类型定义（使用 Required/NotRequired）

```python
from typing import TypedDict, List, Dict, Any
from typing_extensions import Required, NotRequired

class ScoutTacticalState(TypedDict):
    # 必填字段（来自调用方）
    incident_id: Required[str]
    user_id: Required[str]
    thread_id: Required[str]
    slots: Required["ScoutTaskGenerationSlots"]

    # 可选字段（节点填充）
    devices: NotRequired[List[Dict[str, Any]]]
    waypoints: NotRequired[List[Dict[str, Any]]]
    sensor_payloads: NotRequired[List[Dict[str, Any]]]
    intel_requirements: NotRequired[List[str]]
    coverage_gaps: NotRequired[List[str]]
    risk_warnings: NotRequired[List[Dict[str, Any]]]
    scout_task_id: NotRequired[str]
    response_text: NotRequired[str]
    ui_actions: NotRequired[List[Dict[str, Any]]]
```

**设计理由**:
- 使用 `Required`/`NotRequired` 显式标记字段必填性，符合官方最佳实践
- 比 `total=False` 更清晰，mypy 可准确检查类型错误
- 参考 `rescue_tactical_app.py` 的成功模式

## Key Design Decisions

### 1. 设备选择策略

**问题**: 如何从资产表中筛选最合适的侦察设备？

**决策**: 多维度评分排序
```python
async def device_selection(state: ScoutTacticalState) -> Dict[str, Any]:
    slots = state["slots"]
    target_location = slots.coordinates  # (lat, lon)
    target_type = slots.target_type  # "坍塌"/"危化"/"洪水"

    # 1. 查询所有在线设备
    devices = await asset_client.query_devices(
        status="online",
        types=["uav", "robot"]
    )

    # 2. 能力匹配（必须支持目标类型所需传感器）
    required_sensors = SENSOR_REQUIREMENTS[target_type]
    capable_devices = [
        d for d in devices
        if all(sensor in d.capabilities for sensor in required_sensors)
    ]

    # 3. 评分排序
    for device in capable_devices:
        score = 0
        # 距离近 (+100分)
        distance = haversine(device.location, target_location)
        score += max(0, 100 - distance * 10)  # 每公里扣10分

        # 电量足 (+50分)
        score += device.battery_level / 2

        # 空闲优先 (+30分)
        if device.status == "idle":
            score += 30

        device.score = score

    # 4. 返回前N个最优设备
    selected = sorted(capable_devices, key=lambda d: d.score, reverse=True)[:3]
    return {"devices": [d.to_dict() for d in selected]}
```

**备选方案**: 简单的距离优先策略（已拒绝，缺乏灵活性）

### 2. 航线规划算法

**问题**: 如何为目标区域生成合理的巡航航点？

**决策**: Phase 1 使用圆形/网格航点，Phase 2 接入高德路径规划

#### Phase 1: 简单几何算法
```python
def generate_waypoints_circle(center: Tuple[float, float], radius: float, num_points: int = 8) -> List[Dict]:
    """
    生成圆形巡航航点
    center: (lat, lon) 目标中心坐标
    radius: 巡航半径（米）
    num_points: 航点数量
    """
    waypoints = []
    for i in range(num_points):
        angle = (360 / num_points) * i
        point = destination_point(center, radius, angle)  # 地理计算
        waypoints.append({
            "lat": point[0],
            "lon": point[1],
            "alt": 80,  # 固定高度80米
            "speed": 5,  # 5m/s
            "action": "patrol"
        })
    return waypoints

def generate_waypoints_grid(bbox: Dict, spacing: float = 50) -> List[Dict]:
    """
    生成网格扫描航点
    bbox: {"min_lat": ..., "max_lat": ..., "min_lon": ..., "max_lon": ...}
    spacing: 航点间距（米）
    """
    waypoints = []
    lat_step = meters_to_degrees_lat(spacing)
    lon_step = meters_to_degrees_lon(spacing, bbox["min_lat"])

    lat = bbox["min_lat"]
    direction = 1  # 1=向东, -1=向西（蛇形扫描）

    while lat <= bbox["max_lat"]:
        lon_range = (bbox["min_lon"], bbox["max_lon"]) if direction == 1 else (bbox["max_lon"], bbox["min_lon"])
        lon = lon_range[0]
        while (direction == 1 and lon <= lon_range[1]) or (direction == -1 and lon >= lon_range[1]):
            waypoints.append({"lat": lat, "lon": lon, "alt": 80, "speed": 5})
            lon += lon_step * direction
        lat += lat_step
        direction *= -1  # 反向
    return waypoints
```

#### Phase 2: 高德路径规划集成（待实现）
```python
@task
async def amap_route_planning_task(start: Tuple, end: Tuple, amap_client: AmapClient) -> List[Dict]:
    """
    调用高德路径规划API
    幂等性保证：相同起终点返回相同路径
    """
    path = await amap_client.driving_route(origin=start, destination=end)
    waypoints = [
        {"lat": p["lat"], "lon": p["lon"], "alt": 80}
        for p in path["steps"]
    ]
    logger.info("amap_route_planned", waypoint_count=len(waypoints))
    return waypoints
```

**设计理由**:
- Phase 1 快速交付，满足演示需求
- Phase 2 接入真实路径规划，支持复杂场景（城市道路、河道）

### 3. 传感器任务分配

**问题**: 如何根据灾害类型分配传感器任务？

**决策**: 预定义规则映射表
```python
SENSOR_REQUIREMENTS = {
    "坍塌建筑": ["camera", "infrared"],
    "危化品泄漏": ["gas_detector", "camera"],
    "洪水区域": ["camera", "lidar"],
    "火灾现场": ["infrared", "camera"],
    "人员被困": ["camera", "infrared", "audio"]
}

async def sensor_payload_assignment(state: ScoutTacticalState) -> Dict[str, Any]:
    slots = state["slots"]
    devices = state["devices"]
    target_type = slots.target_type

    required_sensors = SENSOR_REQUIREMENTS.get(target_type, ["camera"])

    payloads = []
    for device in devices:
        # 匹配设备能力和需求
        assigned_sensors = [
            sensor for sensor in required_sensors
            if sensor in device["capabilities"]
        ]
        payloads.append({
            "device_id": device["id"],
            "sensors": assigned_sensors,
            "tasks": [
                {"sensor": s, "mode": "continuous", "interval": 1}
                for s in assigned_sensors
            ]
        })

    logger.info("sensors_assigned", payload_count=len(payloads))
    return {"sensor_payloads": payloads}
```

**备选方案**: LLM动态推理（已拒绝，延迟高且不稳定）

### 4. 风险叠加检测

**问题**: 如何检测航点是否经过高风险区域？

**决策**: 地理围栏碰撞检测
```python
async def risk_overlay(state: ScoutTacticalState) -> Dict[str, Any]:
    waypoints = state["waypoints"]
    zones = await risk_repository.list_active_zones()

    warnings = []
    for i, wp in enumerate(waypoints):
        for zone in zones:
            if point_in_polygon((wp["lat"], wp["lon"]), zone.boundary):
                warnings.append({
                    "waypoint_index": i,
                    "risk_type": zone.disaster_type,
                    "risk_level": zone.risk_level,
                    "action": _suggest_avoidance(zone.risk_level)
                })

    logger.warning("risk_detected", warning_count=len(warnings))
    return {"risk_warnings": warnings}

def _suggest_avoidance(risk_level: int) -> str:
    if risk_level >= 80:
        return "avoid"  # 绕行
    elif risk_level >= 50:
        return "elevation_increase"  # 提升高度
    else:
        return "speed_increase"  # 加速通过
```

**设计理由**:
- 简单高效，满足实时性要求
- 可扩展支持3D围栏（海拔限制）

### 5. UI Actions 协议

**问题**: 前端需要哪些动作指令？

**决策**: 三类标准动作
```python
def _generate_ui_actions(state: ScoutTacticalState) -> List[Dict[str, Any]]:
    waypoints = state["waypoints"]
    task_id = state["scout_task_id"]

    # 目标中心坐标
    first_waypoint = waypoints[0]

    return [
        # 1. 地图飞行到目标区域
        {
            "type": "fly_to",
            "params": {
                "lat": first_waypoint["lat"],
                "lon": first_waypoint["lon"],
                "zoom": 15,
                "pitch": 45,
                "duration": 2000  # 2秒动画
            }
        },
        # 2. 打开侦察任务面板
        {
            "type": "open_scout_panel",
            "params": {
                "task_id": task_id,
                "panel_position": "right"
            }
        },
        # 3. 预览航线
        {
            "type": "preview_route",
            "params": {
                "waypoints": waypoints,
                "color": "#FF6B00",  # 橙色航线
                "animation": "flow"  # 流动动画
            }
        }
    ]
```

**设计理由**:
- 与救援子图的 UI Actions 协议保持一致
- 前端可逐步实现，不阻塞后端开发

## Data Models

### ScoutTask 表结构

```sql
CREATE TABLE scout_task (
    id VARCHAR(64) PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    targets JSONB NOT NULL,  -- [{"lat": ..., "lon": ..., "type": "坍塌"}]
    devices JSONB NOT NULL,  -- [{"id": "UAV-001", "score": 85}]
    waypoints JSONB NOT NULL,  -- [{"lat": ..., "lon": ..., "alt": 80}]
    intel_requirements JSONB,  -- ["建筑结构状态", "人员数量"]
    risk_warnings JSONB,  -- [{"waypoint_index": 3, "action": "avoid"}]
    status VARCHAR(32) DEFAULT 'pending',  -- pending/executing/completed/failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_incident (incident_id),
    INDEX idx_user (user_id),
    INDEX idx_status (status)
);
```

### ScoutScenarioPayload (Java 集成)

```python
@dataclass
class ScoutScenarioPayload:
    incident_id: str
    targets: List[Dict[str, Any]]
    devices: List[Dict[str, Any]]
    waypoints: List[Dict[str, Any]]
    intel_requirements: List[str]
    risk_warnings: List[Dict[str, Any]]
    ui_actions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incidentId": self.incident_id,
            "targets": self.targets,
            "devices": self.devices,
            "waypoints": self.waypoints,
            "intelRequirements": self.intel_requirements,
            "riskWarnings": self.risk_warnings,
            "uiActions": self.ui_actions
        }
```

## Error Handling

### 不使用 Fallback，直接暴露问题

```python
async def device_selection(state: ScoutTacticalState) -> Dict[str, Any]:
    try:
        devices = await asset_client.query_devices(...)
        if not devices:
            # 不使用 fallback，直接抛出异常
            raise DeviceNotAvailableError("无可用侦察设备")
        return {"devices": devices}
    except AssetClientError as e:
        # 不降级，记录错误并重新抛出
        logger.error("device_query_failed", error=str(e))
        raise  # 让上层处理
```

**设计理由**:
- 符合用户要求："不要兜底、降级、fallback、mock，直接暴露问题"
- 便于排查根因，不隐藏系统缺陷

## Monitoring and Logging

### Prometheus 指标

```python
from prometheus_client import Counter, Histogram

# 任务计数
scout_task_total = Counter(
    "scout_task_total",
    "侦察任务总数（按状态分类）",
    ["status"]  # pending/completed/failed
)

# 任务执行时长
scout_task_duration = Histogram(
    "scout_task_duration_seconds",
    "侦察任务执行时长（秒）",
    buckets=(1, 3, 5, 10, 30, 60)
)

# 设备选择次数
scout_device_selection_count = Counter(
    "scout_device_selection_total",
    "设备选择次数",
    ["device_type"]  # uav/robot
)

# 航点数量分布
scout_waypoint_count = Histogram(
    "scout_waypoint_count",
    "航点数量分布",
    buckets=(5, 10, 20, 50, 100)
)
```

### Structlog 日志规范

```python
# 关键节点日志
logger.info("scout_devices_selected",
    device_count=len(devices),
    device_types=[d["type"] for d in devices],
    avg_distance=avg_distance
)

logger.info("scout_route_generated",
    waypoint_count=len(waypoints),
    total_distance_km=total_distance / 1000,
    estimated_time_min=estimated_time / 60
)

logger.warning("scout_risk_detected",
    waypoint_index=wp_index,
    risk_type=zone.disaster_type,
    risk_level=zone.risk_level,
    avoidance_action=action
)

logger.info("scout_task_persisted",
    task_id=task_id,
    device_count=len(devices),
    waypoint_count=len(waypoints)
)
```

## Testing Strategy

### 单元测试（Mock外部依赖）

```python
@pytest.mark.unit
async def test_device_selection_with_mock():
    mock_asset_client = MagicMock()
    mock_asset_client.query_devices.return_value = [
        {"id": "UAV-001", "type": "uav", "capabilities": ["camera", "infrared"], "battery": 80}
    ]

    state = {
        "slots": ScoutTaskGenerationSlots(
            coordinates=(31.2, 121.5),
            target_type="坍塌建筑"
        )
    }

    result = await device_selection(state)
    assert len(result["devices"]) == 1
    assert result["devices"][0]["id"] == "UAV-001"
```

### 集成测试（真实数据库）

```python
@pytest.mark.integration
async def test_scout_workflow_end_to_end():
    # 使用测试数据库
    db_conn = get_test_db_connection()

    # 构建初始 state
    state = {
        "incident_id": "INC-001",
        "user_id": "user-123",
        "thread_id": "thread-456",
        "slots": ScoutTaskGenerationSlots(...)
    }

    # 执行完整子图
    graph = ScoutTacticalGraph(...)
    result = await graph.app.ainvoke(state, config={...})

    # 验证结果
    assert result["scout_task_id"] is not None
    assert len(result["devices"]) > 0
    assert len(result["waypoints"]) > 0

    # 验证数据库
    task = await scout_task_repo.get_scout_task(result["scout_task_id"])
    assert task.status == "pending"
```

---

**文档版本**: v1.0
**最后更新**: 2025-11-02
**负责人**: AI Assistant
