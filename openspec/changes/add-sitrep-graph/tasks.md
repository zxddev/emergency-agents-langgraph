# Tasks: 新增态势上报子图（SITREPGraph）

## Phase 0: 准备工作

- [ ] 阅读LangGraph最佳实践文档
  - 文件: `/docs/新业务逻辑md/langgraph资料/references/concept-durable-execution.md`
  - 文件: `/docs/新业务逻辑md/langgraph资料/references/concept-human-in-the-loop.md`
  - 确认@task装饰器使用模式
  - 确认durability配置方法

- [ ] 学习现有子图实现模式
  - 文件: `src/emergency_agents/graph/rescue_tactical_app.py`
  - 重点：State定义、@task使用、build函数结构
  - 重点：LLM调用模式（参考agents/situation.py）

- [ ] 确认数据源可用性
  - 验证 `IncidentDAO` 可用
  - 验证 `TaskDAO` 可用
  - 验证 `RiskCacheManager` 可用
  - 验证 `RescueDAO` 可用
  - 验证 `IncidentSnapshotRepository` 可用

## Phase 1: 核心子图实现

### 1.1 创建State定义

- [ ] 创建 `src/emergency_agents/graph/sitrep_app.py`
- [ ] 定义 `SITREPState(TypedDict)` - 使用TypedDict + NotRequired（符合LangGraph官方规范）
  ```python
  class SITREPState(TypedDict):
      # 必填字段（默认，无需标记）
      report_id: str
      user_id: str
      thread_id: str
      triggered_at: datetime
      # 可选字段（使用NotRequired标记）
      active_incidents: NotRequired[List[IncidentRecord]]
      # ... 其他NotRequired字段
  ```

### 1.2 实现数据采集节点（@task包装）

- [ ] 实现 `fetch_active_incidents` 节点
  - 使用@task装饰器
  - 调用 `incident_dao.list_active_incidents()`
  - 日志: `sitrep_fetch_incidents_start/completed`
  - 返回: `{"active_incidents": List[IncidentRecord]}`

- [ ] 实现 `fetch_task_progress` 节点
  - 使用@task装饰器
  - 调用 `task_dao.list_recent_tasks(hours=time_range)`
  - 日志: `sitrep_fetch_tasks_start/completed`
  - 返回: `{"task_progress": List[TaskSummary]}`

- [ ] 实现 `fetch_risk_zones` 节点
  - 使用@task装饰器
  - 调用 `risk_cache_manager.get_active_zones()`
  - 日志: `sitrep_fetch_risks_start/completed`
  - 返回: `{"risk_zones": List[RiskZoneRecord]}`

- [ ] 实现 `fetch_resource_usage` 节点
  - 使用@task装饰器
  - 调用 `rescue_dao.list_rescuers()`
  - 统计资源使用情况
  - 日志: `sitrep_fetch_resources_start/completed`
  - 返回: `{"resource_usage": Dict[str, Any]}`

### 1.3 实现分析节点

- [ ] 实现 `aggregate_metrics` 节点（纯计算，无@task）
  - 计算活跃事件数
  - 计算已完成任务数
  - 计算风险区域数
  - 计算部署队伍数
  - 返回: `{"metrics": Dict[str, Any]}`

- [ ] 实现 `llm_generate_summary` 节点
  - 创建 `_call_llm_for_sitrep` @task函数
  - 参考 `agents/situation.py:_call_llm_for_situation`
  - 构建Prompt（包含metrics和关键数据）
  - temperature=0
  - 日志: `sitrep_llm_call_start/completed`
  - 返回: `{"llm_summary": str}`

### 1.4 实现持久化和输出节点

- [ ] 实现 `persist_report` 节点
  - 使用@task装饰器
  - 调用 `snapshot_repo.create_snapshot()`
  - snapshot_type='sitrep_report'
  - 日志: `sitrep_persist_start/completed`
  - 返回: `{"snapshot_id": str}`

- [ ] 实现 `finalize` 节点
  - 构建最终响应数据
  - 包含: report_id, generated_at, summary, metrics, snapshot_id
  - 日志: `sitrep_finalized`
  - 返回: `{"sitrep_report": Dict[str, Any]}`

### 1.5 实现graph构建函数

- [ ] 实现 `build_sitrep_graph` 函数
  - 参考 `rescue_tactical_app.py:build_rescue_tactical_graph`
  - 创建 `StateGraph(SITREPState)`
  - 添加9个节点
  - 配置线性流程边
  - 配置interrupt_before（可选，用于审批）
  - 编译graph with checkpointer
  - 返回compiled graph

## Phase 2: API层实现

### 2.1 创建API路由

- [ ] 创建 `src/emergency_agents/api/sitrep.py`
- [ ] 实现 `POST /sitrep/generate` 端点
  - Request Model: `SITREPGenerateRequest`
  - Response Model: `SITREPGenerateResponse`
  - 调用 graph.invoke() with durability="sync"
  - 处理错误和超时

- [ ] 实现 `GET /sitrep/history` 端点
  - Query参数: incident_id, limit, offset
  - 从snapshot_repo查询历史报告
  - Response Model: `SITREPHistoryResponse`

### 2.2 注册路由到主应用

- [ ] 修改 `src/emergency_agents/api/main.py`
  ```python
  from emergency_agents.api import sitrep
  app.include_router(sitrep.router, prefix="/sitrep", tags=["sitrep"])
  ```

- [ ] 在startup_event中初始化SITREPGraph
  ```python
  _sitrep_graph = await build_sitrep_graph(
      incident_dao=_incident_dao,
      task_dao=_task_dao,
      # ... 其他依赖
  )
  ```

## Phase 3: 测试实现

### 3.1 单元测试

- [ ] 创建 `tests/test_sitrep_graph.py`
- [ ] 测试 `fetch_active_incidents` 节点
  - Mock IncidentDAO
  - 验证返回数据结构
  - 验证日志输出

- [ ] 测试 `aggregate_metrics` 节点
  - 纯计算逻辑
  - 验证指标计算正确性

- [ ] 测试 `llm_generate_summary` 节点
  - Mock LLM客户端
  - 验证Prompt构建
  - 验证摘要格式

- [ ] 测试完整graph流程
  - Mock所有外部依赖
  - 验证State正确传递
  - 验证最终输出结构

### 3.2 集成测试

- [ ] 测试真实LLM调用
  - 使用测试配置（glm-4-flash）
  - 验证摘要内容合理性

- [ ] 测试数据库持久化
  - 验证snapshot正确保存
  - 验证snapshot可查询

- [ ] 测试API端点
  - 测试POST /sitrep/generate
  - 测试GET /sitrep/history
  - 测试错误处理

## Phase 4: 文档和部署

### 4.1 代码文档

- [ ] 添加模块docstring（sitrep_app.py）
- [ ] 添加函数docstring（所有公共函数）
- [ ] 添加类型注解（100%覆盖）
- [ ] 添加关键代码注释（中文，工程师风格）

### 4.2 技术文档

- [ ] 创建 `docs/新业务逻辑md/new_0.1/SITREP子图实现报告.md`
  - 架构设计
  - 数据流图
  - API文档
  - 使用示例
  - 故障排查

### 4.3 验证和部署

- [ ] 运行 `openspec validate add-sitrep-graph --strict`
- [ ] 修复所有validation错误
- [ ] 运行所有测试：`pytest tests/test_sitrep_graph.py -v`
- [ ] 代码审查（自检）
  - 检查强类型覆盖
  - 检查@task使用
  - 检查日志完整性
  - 检查错误处理

## Phase 5: Git提交

- [ ] 创建feature分支：`git checkout -b feature/add-sitrep-graph`
- [ ] 分批提交：
  - Commit 1: OpenSpec提案文件
  - Commit 2: 核心子图实现
  - Commit 3: API层实现
  - Commit 4: 测试文件
  - Commit 5: 文档文件

- [ ] 提交信息模板：
  ```
  feat(sitrep): 新增态势上报子图（SITREPGraph）

  - 实现9个节点的完整流程
  - 支持定时/手动生成态势报告
  - 100%独立，无其他子图依赖
  - 强类型State + @task装饰器
  - durability="sync"确保故障恢复

  OpenSpec: openspec/changes/add-sitrep-graph/

  🤖 Generated with Claude Code (https://claude.com/claude-code)

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

- [ ] 推送到GitHub：`git push origin feature/add-sitrep-graph`

## Notes

- 所有代码必须使用强类型（TypedDict + NotRequired，符合LangGraph官方规范）
- 所有副作用操作必须使用@task装饰器
- 所有关键位置必须添加structlog日志
- 不允许降级、fallback、mock实现
- 参考文件：
  - State定义: `graph/rescue_tactical_app.py:106-150`
  - @task使用: `graph/rescue_tactical_app.py:122-210`
  - LLM调用: `agents/situation.py:58-102`
  - build函数: `graph/rescue_tactical_app.py:240-340`
