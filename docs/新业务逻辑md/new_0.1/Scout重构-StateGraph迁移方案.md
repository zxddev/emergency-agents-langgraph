# Scout Tactical Graph 重构：StateGraph 迁移方案

**创建时间**: 2025-11-02
**重构目标**: 将 scout_tactical_app.py 从 @dataclass + invoke() 模式迁移到 StateGraph 模式
**参考基线**: rescue_tactical_app.py（已验证的最佳实践）

---

## 1. 问题分析

### 当前架构缺陷（对比 LangGraph最佳实践对比.md）

| 问题 | 当前实现 | 官方要求 | 影响 |
|------|---------|---------|------|
| 依赖注入 | Optional 依赖 | Required 依赖 | 降级处理，违反"不做fallback"原则 |
| @task 包装 | 仅 3 个函数有 @task | 所有副作用都需要 @task | 无法保证幂等性 |
| durability 配置 | 未配置 | 长流程需要 "sync" | 进程崩溃会丢失状态 |
| 图结构 | @dataclass 单一 invoke() | StateGraph 节点化 | 无法人工审批中断 |

### 代码依据

**文件**: `src/emergency_agents/graph/scout_tactical_app.py`
- **第100-101行**: `@dataclass(slots=True) class ScoutTacticalGraph`
- **第103-104行**: `device_directory: Optional[DeviceDirectory] = None`
  `amap_client: Optional[AmapClient] = None`
- **第145-146行**: `if self.device_directory:` - 降级逻辑
- **第161行**: `if selected_devices and self.amap_client:` - 降级逻辑

---

## 2. 重构策略

### 2.1 架构迁移路径

```
旧架构：
@dataclass + invoke() 方法包含所有逻辑
↓
新架构：
class + _build_graph() → StateGraph 节点化流程
```

### 2.2 节点拆分设计（8 个节点）

根据 OpenSpec `openspec/changes/enhance-scout-tactical-graph/tasks.md`：

| 节点名 | 职责 | @task 函数 | 依赖 |
|--------|------|------------|------|
| build_intel_requirements | 生成情报需求 | - | risk_repository |
| device_selection | 设备选择 | select_devices_for_recon_task | device_directory |
| route_planning | 路线规划 | plan_recon_route_task | amap_client |
| sensor_assignment | 传感器分配 | assign_sensor_payloads_task | - |
| risk_overlay | 风险叠加 | risk_overlay_task (新增) | risk_repository |
| persist_task | 持久化任务 | persist_scout_task (新增) | task_repository |
| prepare_response | 准备响应 | prepare_ui_actions_task (新增) | - |
| ws_notify | WebSocket通知 | notify_backend_task (新增) | orchestrator_client |

### 2.3 依赖注入重构

**修改前**（scout_tactical_app.py:103-104）:
```python
device_directory: Optional[DeviceDirectory] = None
amap_client: Optional[AmapClient] = None
```

**修改后**（参考 rescue_tactical_app.py:306-321）:
```python
def __init__(
    self,
    *,
    risk_repository: RiskDataRepository,
    device_directory: DeviceDirectory,  # Required
    amap_client: AmapClient,  # Required
    orchestrator_client: OrchestratorClient,  # 新增
    task_repository: RescueTaskRepository,  # 新增
    postgres_dsn: str,
    checkpoint_schema: str = "scout_tactical_checkpoint",
) -> None:
    self._risk_repository = risk_repository
    self._device_directory = device_directory
    self._amap_client = amap_client
    self._orchestrator_client = orchestrator_client
    self._task_repository = task_repository
    self._postgres_dsn = postgres_dsn
    self._checkpoint_schema = checkpoint_schema
    self._graph = self._build_graph()
    self._checkpointer: Optional[AsyncPostgresSaver] = None
    self._compiled: Optional[Any] = None
```

**理由**:
1. 所有依赖 Required，启动时就验证完整性
2. 通过闭包捕获依赖（self._xxx）到节点函数
3. 符合"不做降级"原则

---

## 3. StateGraph 构建模式

### 3.1 _build_graph() 方法结构

**参考**: rescue_tactical_app.py:397-905

```python
def _build_graph(self) -> StateGraph:
    graph = StateGraph(ScoutTacticalState)

    # 定义节点函数（闭包捕获 self._xxx）
    async def build_intel_requirements(state: ScoutTacticalState) -> Dict[str, Any]:
        zones = await self._risk_repository.list_active_zones()
        # 调用 _build_plan 逻辑...
        return {"scout_plan": plan}

    async def device_selection(state: ScoutTacticalState) -> Dict[str, Any]:
        plan = state.get("scout_plan")
        devices = select_devices_for_recon_task(
            device_directory=self._device_directory,  # 闭包访问
            required_sensors=plan["recommendedSensors"],
            prefer_device_type=DeviceType.UAV,
        )
        return {"selected_devices": devices}

    # ... 其他 6 个节点

    # 添加节点到图
    graph.add_node("build_intel_requirements", build_intel_requirements)
    graph.add_node("device_selection", device_selection)
    graph.add_node("route_planning", route_planning)
    graph.add_node("sensor_assignment", sensor_assignment)
    graph.add_node("risk_overlay", risk_overlay)
    graph.add_node("persist_task", persist_task)
    graph.add_node("prepare_response", prepare_response)
    graph.add_node("ws_notify", ws_notify)

    # 设置入口点
    graph.set_entry_point("build_intel_requirements")

    # 定义流程
    graph.add_edge("build_intel_requirements", "device_selection")
    graph.add_edge("device_selection", "route_planning")
    graph.add_edge("route_planning", "sensor_assignment")
    graph.add_edge("sensor_assignment", "risk_overlay")
    graph.add_edge("risk_overlay", "persist_task")
    graph.add_edge("persist_task", "prepare_response")
    graph.add_edge("prepare_response", "ws_notify")
    graph.add_edge("ws_notify", "__end__")

    return graph
```

### 3.2 async def build() 类方法

**参考**: rescue_tactical_app.py:343-390

```python
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
    """异步构建战术侦察子图，绑定Postgres checkpointer"""
    logger.info("scout_tactical_graph_init", schema=checkpoint_schema)

    instance = cls(
        risk_repository=risk_repository,
        device_directory=device_directory,
        amap_client=amap_client,
        orchestrator_client=orchestrator_client,
        task_repository=task_repository,
        postgres_dsn=postgres_dsn,
        checkpoint_schema=checkpoint_schema,
    )

    checkpointer, close_cb = await create_async_postgres_checkpointer(
        dsn=postgres_dsn,
        schema=checkpoint_schema,
        min_size=1,
        max_size=5,
    )
    instance._checkpointer = checkpointer
    instance._checkpoint_close = close_cb
    instance._compiled = instance._graph.compile(checkpointer=checkpointer)

    logger.info("scout_tactical_graph_ready", schema=checkpoint_schema)
    return instance
```

### 3.3 invoke() 方法重写

**参考**: rescue_tactical_app.py:907-921

```python
async def invoke(self, state: ScoutTacticalState) -> ScoutTacticalState:
    """执行战术侦察图

    durability="sync": 长流程，每步完成后同步保存checkpoint
    参考：docs/新业务逻辑md/langgraph资料/references/concept-durable-execution.md:88-90
    """
    if self._compiled is None:
        raise RuntimeError("ScoutTacticalGraph 尚未初始化完成")

    return await self._compiled.ainvoke(
        state,
        config={
            "configurable": {"thread_id": state["thread_id"]},
            "durability": "sync",  # 关键配置
        },
    )
```

---

## 4. 新增 @task 函数（4 个）

### 4.1 risk_overlay_task

```python
@task
async def risk_overlay_task(
    waypoints: List[ReconWaypoint],
    risk_repository: RiskDataRepository,
) -> List[WaypointRisk]:
    """为每个航点叠加风险数据

    幂等性保证：相同航点返回相同风险评估
    """
    risks: List[WaypointRisk] = []
    for waypoint in waypoints:
        coord = waypoint["location"]
        # 查询该坐标附近的风险区域
        nearby_zones = await risk_repository.find_zones_near(
            lng=coord["lng"],
            lat=coord["lat"],
            radius_meters=500,
        )
        risks.append({
            "waypoint_sequence": waypoint["sequence"],
            "risk_level": max((z.severity for z in nearby_zones), default=0),
            "hazard_types": [z.hazard_type for z in nearby_zones],
        })
    return risks
```

### 4.2 persist_scout_task

```python
@task
async def persist_scout_task(
    scout_task: Dict[str, Any],
    task_repository: RescueTaskRepository,
) -> Dict[str, Any]:
    """持久化侦察任务到数据库

    幂等性保证：使用 task_id（code 字段）作为唯一标识
    """
    task_input = TaskCreateInput(
        task_type="uav_recon",
        status="pending",
        priority=90,
        description=scout_task["description"],
        deadline=None,
        target_entity_id=None,
        event_id=scout_task["incident_id"],
        created_by=scout_task["user_id"],
        updated_by=scout_task["user_id"],
        code=scout_task["task_id"],  # 幂等性关键
    )

    # 先检查是否已存在（基于 code）
    existing = await task_repository.find_by_code(scout_task["task_id"])
    if existing:
        logger.info("scout_task_already_exists", task_id=scout_task["task_id"])
        return {"task_record_id": existing.id}

    record = await task_repository.create_task(task_input)
    logger.info("scout_task_persisted", task_id=record.id)
    return {"task_record_id": record.id}
```

### 4.3 prepare_ui_actions_task

```python
@task
def prepare_ui_actions_task(
    state: ScoutTacticalState,
) -> Dict[str, Any]:
    """生成前端 UI Actions

    幂等性保证：纯计算，无副作用
    """
    route = state.get("recon_route")
    devices = state.get("selected_devices", [])

    ui_actions = []
    if route and route["waypoints"]:
        ui_actions.append({
            "action": "preview_route",
            "data": {"waypoints": route["waypoints"]},
        })

    if devices:
        ui_actions.append({
            "action": "open_scout_panel",
            "data": {"devices": devices},
        })

    return {"ui_actions": ui_actions}
```

### 4.4 notify_backend_task

```python
@task
def notify_backend_task(
    payload: Dict[str, Any],
    orchestrator: OrchestratorClient,
) -> Dict[str, Any]:
    """推送侦察任务到 Java 后台

    幂等性保证：Orchestrator 需要支持幂等性（使用 task_id 去重）
    """
    response = orchestrator.publish_scout_scenario(payload)
    logger.info("scout_scenario_published", task_id=payload.get("taskId"))
    return response
```

---

## 5. 数据库适配

### 5.1 复用现有表结构

**分析**:
- tasks 表已有 `plan_step jsonb` 字段（operational.sql:7222）
- 可存储 selected_devices, sensor_assignments

**无需新增字段或表**

### 5.2 持久化策略

```python
# persist_task 节点中
task_input = TaskCreateInput(
    task_type="uav_recon",  # 使用现有枚举
    # ... 基础字段
)

# 将 Scout 特有数据存入 plan_step
route_input = TaskRoutePlanCreateInput(
    task_id=task_record.id,
    # ... recon_route 数据
)
```

---

## 6. 实施检查清单

- [ ] 移除 @dataclass 装饰器
- [ ] 将 Optional 依赖改为 Required
- [ ] 新增 __init__() 方法
- [ ] 新增 4 个 @task 函数
- [ ] 实现 _build_graph() 方法（8 个节点）
- [ ] 实现 async def build() 类方法
- [ ] 重写 invoke() 方法（配置 durability="sync"）
- [ ] 添加 structlog 日志到每个节点
- [ ] 更新单元测试
- [ ] 更新集成测试
- [ ] 验证语法 `python3 -m py_compile src/emergency_agents/graph/scout_tactical_app.py`

---

## 7. 参考文档

- `/docs/新业务逻辑md/new_0.1/LangGraph最佳实践对比.md` - 最佳实践基线
- `src/emergency_agents/graph/rescue_tactical_app.py` - 参考实现
- `/docs/新业务逻辑md/langgraph资料/references/concept-durable-execution.md` - @task 和 durability 官方文档
- `openspec/changes/enhance-scout-tactical-graph/` - OpenSpec 需求规范
