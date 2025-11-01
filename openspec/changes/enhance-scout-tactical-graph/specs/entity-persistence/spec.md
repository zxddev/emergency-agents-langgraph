# Spec: 实体持久化能力

## ADDED Requirements

### Requirement: ScoutTask 数据模型

系统MUST必须定义 `ScoutTask` 数据模型，用于保存侦察任务的完整信息。
系统必须定义 `ScoutTask` 数据模型，用于保存侦察任务的完整信息。

#### Scenario: 基础场景
系统必须定义 `ScoutTask` 数据模型，用于保存侦察任务的完整信息。

- **GIVEN**:
- 侦察任务已规划完成
- 包含设备、航点、传感器、情报需求、风险告警等数据

- **WHEN**:
- 定义 `ScoutTask` 数据类

- **THEN**:
- 数据类包含以下字段:
  - id: str (主键，格式 "SCOUT-{timestamp}-{random}")
  - incident_id: str (关联的事件ID)
  - user_id: str (创建用户)
  - targets: List[Dict] (侦察目标列表)
  - devices: List[Dict] (分配的设备列表)
  - waypoints: List[Dict] (航线航点)
  - intel_requirements: List[str] (情报需求)
  - risk_warnings: List[Dict] (风险告警)
  - status: str (任务状态: pending/executing/completed/failed)
  - created_at: datetime
  - updated_at: datetime

- **Acceptance Criteria**:
- [ ] 在 `src/emergency_agents/db/models.py` 中定义 `ScoutTask` 数据类
- [ ] 使用 `@dataclass` 装饰器
- [ ] 所有字段包含类型注解
- [ ] `id` 字段默认使用 `generate_scout_task_id()` 函数生成

---

### Requirement: 数据库表结构

系统MUST必须创建 `scout_task` 数据库表用于持久化侦察任务。
系统必须创建 `scout_task` 数据库表用于持久化侦察任务。

#### Scenario: 基础场景
系统必须创建 `scout_task` 数据库表用于持久化侦察任务。

- **GIVEN**:
- PostgreSQL 数据库已连接

- **WHEN**:
- 执行数据库迁移脚本

- **THEN**:
- 创建表 `scout_task` 包含以下字段:
  ```sql
  CREATE TABLE scout_task (
      id VARCHAR(64) PRIMARY KEY,
      incident_id VARCHAR(64) NOT NULL,
      user_id VARCHAR(64) NOT NULL,
      targets JSONB NOT NULL,
      devices JSONB NOT NULL,
      waypoints JSONB NOT NULL,
      intel_requirements JSONB,
      risk_warnings JSONB,
      status VARCHAR(32) DEFAULT 'pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX idx_scout_task_incident ON scout_task(incident_id);
  CREATE INDEX idx_scout_task_user ON scout_task(user_id);
  CREATE INDEX idx_scout_task_status ON scout_task(status);
  ```

- **Acceptance Criteria**:
- [ ] 迁移脚本文件: `sql/migrations/V004__scout_task_table.sql`
- [ ] 表名为 `scout_task`
- [ ] 主键为 `id` (VARCHAR 64)
- [ ] JSONB 字段用于存储复杂对象（targets, devices, waypoints 等）
- [ ] 创建3个索引（incident_id, user_id, status）

---

### Requirement: ScoutTaskRepository 实现

系统MUST必须实现 `ScoutTaskRepository` 提供侦察任务的 CRUD 操作。
系统必须实现 `ScoutTaskRepository` 提供侦察任务的 CRUD 操作。

#### Scenario: 基础场景
系统必须实现 `ScoutTaskRepository` 提供侦察任务的 CRUD 操作。

- **GIVEN**:
- `ScoutTask` 数据模型已定义
- `scout_task` 表已创建

- **WHEN**:
- 实现 Repository 方法

- **THEN**:
- 提供以下方法:
  - `async def create_scout_task(task: ScoutTask) -> str` - 创建任务，返回task_id
  - `async def get_scout_task(task_id: str) -> Optional[ScoutTask]` - 查询任务
  - `async def update_scout_task_status(task_id: str, status: str) -> bool` - 更新状态
  - `async def list_scout_tasks(incident_id: str) -> List[ScoutTask]` - 列举事件的所有侦察任务

- **Acceptance Criteria**:
- [ ] 在 `src/emergency_agents/db/dao.py` 中实现 `ScoutTaskRepository` 类
- [ ] 所有方法包含类型注解和 docstring
- [ ] 使用参数化查询防止 SQL 注入
- [ ] 错误处理：数据库异常转换为自定义异常（如 `ScoutTaskNotFoundError`）

---

### Requirement: persist_task 节点实现

当侦察任务规划完成后，`persist_task` 节点MUST将任务数据保存到数据库。
当侦察任务规划完成后，`persist_task` 节点必须将任务数据保存到数据库。

#### Scenario: 基础场景
当侦察任务规划完成后，`persist_task` 节点必须将任务数据保存到数据库。

- **GIVEN**:
- State 中包含完整的侦察任务数据（devices, waypoints, sensor_payloads, intel_requirements, risk_warnings）

- **WHEN**:
- `persist_task` 节点执行

- **THEN**:
- 构建 `ScoutTask` 对象
- 调用 `scout_task_repository.create_scout_task(task)`
- 返回 `{"scout_task_id": task.id}`

- **Acceptance Criteria**:
- [ ] 函数签名: `async def persist_task(state: ScoutTacticalState) -> Dict[str, Any]`
- [ ] 使用 `@task` 装饰器包装数据库操作（幂等性保证）
- [ ] 日志记录: `logger.info("scout_task_persisted", task_id=...)`
- [ ] 数据库写入失败时抛出异常（不降级）

---

### Requirement: 幂等性保证

当 `persist_task` 节点因故障重试时，MUST保证幂等性（不重复创建记录）。
当 `persist_task` 节点因故障重试时，必须保证幂等性（不重复创建记录）。

#### Scenario: 基础场景
当 `persist_task` 节点因故障重试时，必须保证幂等性（不重复创建记录）。

- **GIVEN**:
- 任务 SCOUT-001 已写入数据库
- 节点因网络故障重试

- **WHEN**:
- 再次执行 `persist_task` 节点

- **THEN**:
- 检测到任务已存在（通过 task_id）
- 跳过插入操作，直接返回已存在的 task_id
- 或使用 `INSERT ... ON CONFLICT DO NOTHING` 语句

- **Acceptance Criteria**:
- [ ] 使用 `@task` 装饰器自动处理幂等性
- [ ] 或在函数内部检查 `scout_task_repository.get_scout_task(task_id)` 是否已存在
- [ ] 日志区分 "created" 和 "already_exists" 场景

---

### Requirement: State 更新

当持久化完成后，MUST更新 `ScoutTacticalState` 的 `scout_task_id` 字段。
当持久化完成后，必须更新 `ScoutTacticalState` 的 `scout_task_id` 字段。

#### Scenario: 基础场景
当持久化完成后，必须更新 `ScoutTacticalState` 的 `scout_task_id` 字段。

- **GIVEN**:
- 任务成功保存到数据库
- task_id 为 "SCOUT-20251102-ABC123"

- **WHEN**:
- 节点返回结果

- **THEN**:
- 返回字典 `{"scout_task_id": "SCOUT-20251102-ABC123"}`
- State 中包含 `scout_task_id` 字段

- **Acceptance Criteria**:
- [ ] 返回的 `scout_task_id` 为 `str` 类型
- [ ] State 强类型定义中 `scout_task_id` 字段标记为 `NotRequired[str]`

---

### Requirement: 审计日志记录

The system MUST record scout task persistence to audit log table for traceability.

#### Scenario: 基础场景
侦察任务持久化必须记录到审计日志表，便于追溯。

- **GIVEN**:
- 侦察任务已保存
- 用户为 "user-123"

- **WHEN**:
- 任务创建成功

- **THEN**:
- 写入审计日志:
  ```json
  {
    "action": "scout_task_created",
    "user_id": "user-123",
    "task_id": "SCOUT-20251102-ABC123",
    "incident_id": "INC-001",
    "device_count": 2,
    "waypoint_count": 12
  }
  ```

- **Acceptance Criteria**:
- [ ] 调用 `audit_logger.log_action()` 记录审计事件
- [ ] 审计日志包含 action, user_id, task_id, incident_id 字段
- [ ] 审计日志写入失败不阻塞主流程（记录错误日志）

---

## MODIFIED Requirements

（无修改的需求）

---

## REMOVED Requirements

（无删除的需求）

---

**Spec 版本**: v1.0
**创建时间**: 2025-11-02
**状态**: DRAFT
