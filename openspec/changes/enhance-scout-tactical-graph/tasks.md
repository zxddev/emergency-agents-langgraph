# Tasks: 开发战术侦察子图

## Task Checklist

### Phase 1: 数据模型和基础设施（必须先完成）

- [ ] **T1.1** 定义 ScoutTask 数据模型
  - 文件: `src/emergency_agents/db/models.py`
  - 内容: 添加 `ScoutTask` 类，包含 id、incident_id、targets、devices、waypoints、intel_requirements、risk_warnings、status、created_at、updated_at 字段
  - 验证: `pytest tests/db/test_models.py -k scout_task`

- [ ] **T1.2** 创建数据库迁移脚本
  - 文件: `sql/migrations/V004__scout_task_table.sql`
  - 内容: CREATE TABLE scout_task 语句，包含所有字段和索引
  - 验证: 手动执行迁移脚本，确认表创建成功

- [ ] **T1.3** 实现 ScoutTaskRepository
  - 文件: `src/emergency_agents/db/dao.py`
  - 方法: `create_scout_task()`, `get_scout_task()`, `update_scout_task_status()`
  - 验证: `pytest tests/db/test_dao.py -k scout_task`

### Phase 2: StateGraph 核心节点实现

- [ ] **T2.1** 重构 ScoutTacticalState 定义
  - 文件: `src/emergency_agents/graph/scout_tactical_app.py`
  - 当前问题: 使用 `TypedDict(total=False)` 缺乏强类型
  - 改为: 使用 `Required`/`NotRequired` 显式标记必填/可选字段
  - 参考: `rescue_tactical_app.py` 的 `RescueTacticalState` 定义
  - 验证: mypy 类型检查通过

- [ ] **T2.2** 实现 device_selection 节点
  - 函数: `async def device_selection(state: ScoutTacticalState) -> Dict[str, Any]`
  - 逻辑:
    1. 从 slots 中提取目标类型和坐标
    2. 调用 AssetManagementClient 查询可用设备（无人机/机器人）
    3. 根据设备能力（相机、红外、气体检测）筛选
    4. 优先选择距离目标近且电量充足的设备
    5. 返回 `{"devices": [...]}` 更新到 state
  - 日志: `logger.info("scout_devices_selected", count=len(devices), types=[...])`
  - 验证: 单元测试 mock AssetManagementClient，验证筛选逻辑

- [ ] **T2.3** 实现 recon_route_planning 节点
  - 函数: `async def recon_route_planning(state: ScoutTacticalState) -> Dict[str, Any]`
  - 逻辑:
    1. 读取 state["devices"] 和 state["targets"]
    2. 为每个目标生成巡航航点（基于坐标 + 半径生成圆形/网格航点）
    3. 调用高德 API 获取道路路径（可选，Phase 1 暂用简单算法）
    4. 返回 `{"waypoints": [{"lat": ..., "lon": ..., "alt": ...}, ...]}`
  - 使用 `@task` 装饰器包装高德 API 调用
  - 日志: `logger.info("scout_route_generated", waypoint_count=len(waypoints))`
  - 验证: 单元测试验证航点生成算法

- [ ] **T2.4** 实现 sensor_payload_assignment 节点
  - 函数: `async def sensor_payload_assignment(state: ScoutTacticalState) -> Dict[str, Any]`
  - 逻辑:
    1. 读取 state["devices"] 和 state["targets"]
    2. 根据目标类型分配传感器任务：
       - 坍塌建筑 → 相机 + 红外
       - 危化品泄漏 → 气体检测 + 相机
       - 洪水区域 → 相机 + 测距
    3. 返回 `{"sensor_payloads": [{"device_id": ..., "sensors": [...]}]}`
  - 日志: `logger.info("scout_sensors_assigned", assignments=len(payloads))`
  - 验证: 单元测试验证分配规则

- [ ] **T2.5** 增强 intel_requirement_builder 节点
  - 文件: `src/emergency_agents/graph/scout_tactical_app.py`
  - 当前状态: 基础实现已存在，需增强
  - 增强点:
    1. 根据风险区域类型生成更细粒度的情报需求
    2. 关联设备和传感器能力，生成"可采集项"和"缺失项"
    3. 返回 `{"intel_requirements": [...], "coverage_gaps": [...]}`
  - 验证: 单元测试验证情报需求完整性

- [ ] **T2.6** 实现 risk_overlay 节点
  - 函数: `async def risk_overlay(state: ScoutTactualState) -> Dict[str, Any]`
  - 逻辑:
    1. 读取 state["waypoints"] 和 RiskZoneRecord 数据
    2. 检测航点是否经过高风险区域
    3. 标注危险点位，生成规避建议（绕行/提升高度/加速通过）
    4. 返回 `{"risk_warnings": [{"waypoint_index": ..., "risk_type": ..., "action": "avoid"}]}`
  - 日志: `logger.warning("scout_risk_detected", waypoint=..., risk_level=...)`
  - 验证: 单元测试验证风险检测逻辑

- [ ] **T2.7** 实现 persist_task 节点
  - 函数: `async def persist_task(state: ScoutTacticalState) -> Dict[str, Any]`
  - 逻辑:
    1. 汇总 state 中的所有数据
    2. 调用 `scout_task_repository.create_scout_task()`
    3. 返回 `{"scout_task_id": ...}`
  - 使用 `@task` 装饰器包装数据库操作
  - 日志: `logger.info("scout_task_persisted", task_id=...)`
  - 验证: 集成测试验证数据库写入

- [ ] **T2.8** 实现 prepare_response 节点
  - 函数: `async def prepare_response(state: ScoutTacticalState) -> Dict[str, Any]`
  - 逻辑:
    1. 构建侦察计划摘要文本（"已分配3架无人机，规划12个航点，预计时长15分钟"）
    2. 生成 UI Actions:
       - `{"type": "fly_to", "params": {"lat": ..., "lon": ..., "zoom": 15}}`
       - `{"type": "open_scout_panel", "params": {"task_id": ...}}`
       - `{"type": "preview_route", "params": {"waypoints": [...]}}`
    3. 返回 `{"response_text": "...", "ui_actions": [...]}`
  - 验证: 单元测试验证 JSON 结构

- [ ] **T2.9** 实现 ws_notify 节点
  - 函数: `async def ws_notify(state: ScoutTacticalState) -> Dict[str, Any]`
  - 逻辑:
    1. 调用 `orchestrator_client.publish_scout_scenario(payload)`
    2. payload 包含 targets、devices、waypoints、ui_actions
  - 使用 `@task` 装饰器包装 HTTP 调用
  - 日志: `logger.info("scout_scenario_pushed", status=response.status)`
  - 验证: 集成测试 mock OrchestratorClient

### Phase 3: StateGraph 构建和配置

- [ ] **T3.1** 重构 ScoutTacticalGraph 为 StateGraph 模式
  - 文件: `src/emergency_agents/graph/scout_tactical_app.py`
  - 删除当前的 `@dataclass` 定义
  - 参考 `rescue_tactical_app.py` 创建 `_build_graph()` 方法
  - 添加所有节点到图中
  - 定义线性流程:
    ```
    device_selection → recon_route_planning → sensor_payload_assignment
    → intel_requirement_builder → risk_overlay → persist_task
    → prepare_response → ws_notify
    ```
  - 验证: 图编译成功，无环路

- [ ] **T3.2** 配置 durability 和 checkpointer
  - 文件: `src/emergency_agents/graph/scout_tactical_app.py`
  - 配置: `durability="sync"` 确保长时间任务可恢复
  - 使用 PostgreSQL checkpointer（复用现有配置）
  - 验证: 测试中断恢复功能

- [ ] **T3.3** 添加 Prometheus 监控指标
  - 文件: `src/emergency_agents/graph/scout_tactical_app.py`
  - 指标:
    - `scout_task_total` (Counter) - 总任务数，按状态分类
    - `scout_task_duration_seconds` (Histogram) - 任务执行时长
    - `scout_device_selection_count` (Counter) - 设备选择次数
    - `scout_waypoint_count` (Histogram) - 航点数量分布
  - 验证: curl /metrics 查看指标

### Phase 4: 外部集成扩展

- [ ] **T4.1** 扩展 OrchestratorClient 添加 publish_scout_scenario
  - 文件: `src/emergency_agents/external/orchestrator_client.py`
  - 方法签名: `def publish_scout_scenario(self, payload: ScoutScenarioPayload) -> Dict[str, Any]`
  - 端点: `POST /api/v1/scout/scenario`
  - 验证: 单元测试 mock HTTP 请求

- [ ] **T4.2** 定义 ScoutScenarioPayload 模型
  - 文件: `src/emergency_agents/external/models.py` (新建或复用)
  - 字段: incident_id, targets, devices, waypoints, intel_requirements, risk_warnings, ui_actions
  - 验证: Pydantic 模型验证通过

- [ ] **T4.3** (可选) 实现 AssetManagementClient
  - 文件: `src/emergency_agents/external/asset_client.py` (新建)
  - 方法: `async def query_available_devices(device_type: str, location: Dict) -> List[Device]`
  - 如果暂无后台接口，先使用 mock 数据
  - 验证: 单元测试 mock 响应

### Phase 5: Handler 集成

- [ ] **T5.1** 更新 ScoutTaskGenerationHandler 调用完整子图
  - 文件: `src/emergency_agents/intent/handlers/scout_task_generation_handler.py`
  - 当前: 直接调用 `scout_graph.invoke()`
  - 改为: 调用 LangGraph 编译后的 app
  - 传递完整的 state（包含 incident_id、user_id、thread_id、slots）
  - 验证: 集成测试从意图分类到子图执行

### Phase 6: 测试和文档

- [ ] **T6.1** 编写单元测试
  - 文件: `tests/graph/test_scout_tactical_app.py`
  - 覆盖所有节点函数
  - Mock 外部依赖（AmapClient、AssetManagementClient、OrchestratorClient）
  - 验证: `pytest tests/graph/test_scout_tactical_app.py -v`

- [ ] **T6.2** 编写集成测试
  - 文件: `tests/integration/test_scout_workflow.py`
  - 测试完整流程：意图输入 → 子图执行 → 数据持久化 → 前端推送
  - 使用真实的 PostgreSQL 和 Neo4j（测试环境）
  - 验证: `pytest tests/integration/test_scout_workflow.py -v`

- [ ] **T6.3** 更新业务文档
  - 文件: `docs/新业务逻辑md/new_0.1/战术侦察子图实现细节.md` (新建)
  - 内容:
    - State 定义说明
    - 节点流程图
    - 设备选择规则
    - 航线规划算法
    - 传感器分配策略
    - 前端集成协议
  - 验证: 技术负责人审阅通过

- [ ] **T6.4** 添加 API 文档
  - 文件: `docs/api/scout-tactical-api.md` (新建)
  - 内容: Handler 输入输出格式、错误码、示例请求
  - 验证: 前端团队确认可对接

### Phase 7: 部署和验证

- [ ] **T7.1** 本地环境验证
  - 启动完整服务栈（PostgreSQL、Neo4j、Qdrant、LangGraph）
  - 通过 WebSocket 发送侦察意图
  - 验证前端收到 UI Actions
  - 验证数据库保存 ScoutTask 记录

- [ ] **T7.2** 性能测试
  - 测试100个并发侦察任务的处理能力
  - 监控 Prometheus 指标
  - 确保单个任务处理时间 < 5秒

- [ ] **T7.3** 提交代码和归档
  - 提交所有改动到 GitHub
  - 运行 `openspec archive enhance-scout-tactical-graph --yes`
  - 更新 CHANGELOG.md

---

**任务总数**: 31
**预计工期**: 4-5天
**优先级**: 高（峰会演示关键功能）
