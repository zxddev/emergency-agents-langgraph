# Proposal: 新增态势上报子图（SITREPGraph）

## Why

当前系统缺少定期态势上报能力，无法向上级指挥部汇报救援进展。SITREP（Situation Report）是军事/应急领域的标准概念，用于定期汇总当前事件状态、资源使用、风险评估和后续行动建议。

**业务价值**：
- 自动化态势汇报，减少人工整理负担
- 标准化报告格式，确保信息完整性
- 定时/按需生成，支持指挥决策
- 结构化数据 + LLM摘要，兼顾可读性和可分析性

**技术价值**：
- 100%独立子图，不依赖其他子图的执行结果
- 演示LangGraph的数据聚合和LLM摘要能力
- 完整实现@task装饰器、durability、强类型State等最佳实践

## What Changes

### 新增文件
1. `src/emergency_agents/graph/sitrep_app.py` - 核心子图实现（9个节点）
2. `src/emergency_agents/api/sitrep.py` - REST API端点
3. `tests/test_sitrep_graph.py` - 单元测试和集成测试
4. `docs/新业务逻辑md/new_0.1/SITREP子图实现报告.md` - 实现文档

### 修改文件
1. `src/emergency_agents/api/main.py` - 注册SITREP路由
   ```python
   # 新增路由注册
   from emergency_agents.api import sitrep
   app.include_router(sitrep.router, prefix="/sitrep", tags=["sitrep"])
   ```

2. `src/emergency_agents/db/dao.py` - （可选）如需新增辅助查询方法
   - 如 `IncidentDAO.list_recent_active_incidents(hours: int)`
   - 如 `TaskDAO.list_recent_completed_tasks(hours: int)`

### 不需要SQL变更
- 复用 `operational.incident_snapshots` 表
- `snapshot_type = 'sitrep_report'`
- 所有数据源表已存在（events, tasks, risk_zones等）

### 子图架构

**State定义** (强类型，TypedDict + NotRequired模式):
```python
class SITREPState(TypedDict):
    # 必填字段（TypedDict默认必填，无需标记）
    report_id: str  # UUID
    user_id: str
    thread_id: str
    triggered_at: datetime

    # 可选字段（使用NotRequired标记）
    incident_id: NotRequired[str]  # 可选，指定事件ID
    time_range_hours: NotRequired[int]  # 统计时间范围

    # 数据采集结果
    active_incidents: NotRequired[List[IncidentRecord]]
    task_progress: NotRequired[List[TaskSummary]]
    risk_zones: NotRequired[List[RiskZoneRecord]]
    resource_usage: NotRequired[Dict[str, Any]]

    # 分析结果
    metrics: NotRequired[Dict[str, Any]]
    llm_summary: NotRequired[str]

    # 输出
    sitrep_report: NotRequired[Dict[str, Any]]
    snapshot_id: NotRequired[str]
```

**9个关键节点**:
1. `ingest` - 初始化，验证输入参数
2. `fetch_active_incidents` - @task包装，查询IncidentDAO
3. `fetch_task_progress` - @task包装，查询TaskDAO
4. `fetch_risk_zones` - @task包装，从RiskCacheManager获取
5. `fetch_resource_usage` - @task包装，查询RescueDAO
6. `aggregate_metrics` - 纯计算，统计各项指标
7. `llm_generate_summary` - @task包装LLM调用，生成态势摘要
8. `persist_report` - @task包装，写入IncidentSnapshotRepository
9. `finalize` - 返回最终结果

**依赖注入** (参考rescue_tactical_app模式):
- `incident_dao: IncidentDAO`
- `task_dao: TaskDAO`
- `risk_cache_manager: RiskCacheManager`
- `rescue_dao: RescueDAO`
- `snapshot_repo: IncidentSnapshotRepository`
- `llm_client: LLMClientProtocol`
- `checkpointer: AsyncPostgresSaver`

**Durability**: `sync` (长流程，确保每步持久化)

## Impact

### Affected Specs
- **新增**: `sitrep-reporting` - 态势上报能力规范

### Affected Code
- **新增**: `src/emergency_agents/graph/sitrep_app.py` (~400行)
- **新增**: `src/emergency_agents/api/sitrep.py` (~100行)
- **修改**: `src/emergency_agents/api/main.py` (+5行，注册路由)
- **可选修改**: `src/emergency_agents/db/dao.py` (如需辅助查询方法)

### 数据库变更
- **无新增表** - 复用 `incident_snapshots` 表
- **无schema变更**

### External Dependencies
- **LLM服务** - 已有（glm-4-flash或配置的模型）
- **PostgreSQL** - 已有（事件、任务、风险数据）
- **Neo4j** - 不依赖（SITREP无需知识图谱）
- **Qdrant** - 不依赖（SITREP无需RAG检索）

### Backward Compatibility
- **100%兼容** - 纯新增功能，不修改任何现有代码逻辑
- **独立部署** - 可通过feature flag控制是否启用

### Risk Assessment
- **低风险** - 所有依赖已验证存在
- **无breaking change** - 不修改现有API或数据结构
- **可回滚** - 纯新增功能，删除路由即可回滚

## API Design

### POST /sitrep/generate
生成态势报告（同步或异步）

**Request Body**:
```json
{
  "incident_id": "uuid-optional",
  "time_range_hours": 24,
  "async_mode": false
}
```

**Response**:
```json
{
  "report_id": "uuid",
  "generated_at": "2025-11-02T10:30:00Z",
  "summary": "LLM生成的态势摘要",
  "metrics": {
    "active_incidents_count": 5,
    "completed_tasks_count": 23,
    "active_risk_zones_count": 8,
    "deployed_teams_count": 15
  },
  "details": {
    "incidents": [...],
    "tasks": [...],
    "risks": [...]
  },
  "snapshot_id": "uuid"
}
```

### GET /sitrep/history
查询历史态势报告

**Query Parameters**:
- `incident_id` (optional)
- `limit` (default: 10)
- `offset` (default: 0)

## Implementation Plan

**Phase 1: 核心子图实现** (2-3小时)
- [ ] 创建 `sitrep_app.py`
- [ ] 实现9个节点函数
- [ ] 实现State定义
- [ ] 实现build_sitrep_graph构建函数

**Phase 2: API层实现** (1小时)
- [ ] 创建 `api/sitrep.py`
- [ ] 实现POST /sitrep/generate
- [ ] 实现GET /sitrep/history
- [ ] 注册到main.py

**Phase 3: 测试和文档** (2小时)
- [ ] 单元测试（Mock LLM）
- [ ] 集成测试（真实LLM）
- [ ] 编写实现文档
- [ ] 更新API文档

**Total Estimate**: 4-5小时

## Success Criteria

- [ ] `openspec validate add-sitrep-graph --strict` 通过
- [ ] 所有节点函数使用@task包装副作用操作
- [ ] State定义使用TypedDict + NotRequired强类型（符合LangGraph官方规范）
- [ ] durability="sync"配置正确
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试通过（端到端流程）
- [ ] LLM生成的摘要格式正确
- [ ] 报告成功保存到incident_snapshots表
- [ ] API返回结构符合设计规范

---

**创建时间**: 2025-11-02
**状态**: DRAFT
**预计开发时间**: 4-5小时
**风险等级**: LOW
