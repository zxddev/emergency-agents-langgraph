# Specification: 态势上报（SITREP Reporting）

## ADDED Requirements

### Requirement: 定期生成态势报告

系统 SHALL 能够定时或按需生成结构化的态势报告（SITREP），汇总当前救援进展、资源使用、风险状况和后续建议，供上级指挥部决策参考。

**Rationale**: 应急指挥需要定期向上级汇报现场态势，人工整理耗时且易遗漏关键信息。自动化SITREP生成可确保信息完整、格式标准、及时准确。

#### Scenario: 定时生成态势报告

**Given**: 系统有5个进行中的事件，23个已完成任务，8个活跃风险区域
**When**: 指挥员请求生成最近24小时的态势报告
**Then**: 系统应在30秒内返回包含以下内容的报告：
- 活跃事件统计（数量、类型、优先级）
- 任务进度统计（已完成/进行中/待办）
- 风险区域分布（类型、严重程度、影响范围）
- 资源部署情况（队伍数、人员数、装备状态）
- LLM生成的态势摘要（200-500字）
- 报告生成时间和统计时间范围

#### Scenario: 指定事件生成态势报告

**Given**: 系统有一个ID为"abc-123"的地震事件
**When**: 指挥员请求生成该事件的专项态势报告
**Then**: 系统应返回该事件的详细态势分析：
- 仅统计该事件相关的任务和资源
- 该事件影响区域内的风险评估
- 该事件的时间轴和关键节点
- 针对该事件的LLM摘要

### Requirement: 持久化态势报告

所有生成的态势报告 MUST 持久化存储，支持历史查询和趋势分析。

**Rationale**: 态势报告是重要的决策依据，需要归档保存用于事后分析、经验总结和责任追溯。

#### Scenario: 保存态势报告到数据库

**Given**: 系统成功生成了一份态势报告
**When**: 报告持久化流程执行
**Then**: 系统应：
- 将报告保存到 `operational.incident_snapshots` 表
- 设置 `snapshot_type = 'sitrep_report'`
- 包含完整的JSON payload（metrics + summary + details）
- 记录生成时间和创建者
- 返回snapshot_id用于后续查询

#### Scenario: 查询历史态势报告

**Given**: 系统已保存了10份历史态势报告
**When**: 用户查询最近7天的态势报告
**Then**: 系统应返回：
- 按时间倒序排列的报告列表
- 每份报告包含：report_id, generated_at, summary（摘要）, metrics（关键指标）
- 支持分页查询（limit/offset）
- 支持按incident_id过滤

### Requirement: LLM生成态势摘要

态势报告 MUST 包含由LLM生成的自然语言摘要，提炼关键信息和趋势变化。

**Rationale**: 纯数字统计不够直观，LLM摘要可以突出重点、发现异常、提供决策建议。

#### Scenario: 生成简明态势摘要

**Given**: 系统采集了完整的态势数据（事件、任务、风险、资源）
**When**: LLM生成摘要流程执行
**Then**: 系统应：
- 使用temperature=0确保输出稳定
- Prompt包含关键数据（metrics + 事件类型 + 资源状态）
- 生成200-500字的中文摘要
- 摘要包含：
  - 总体态势概述（1-2句）
  - 关键进展和成果（2-3点）
  - 当前风险和挑战（2-3点）
  - 后续行动建议（2-3点）
- 摘要语气专业、简洁、客观

#### Scenario: LLM调用失败时的处理

**Given**: LLM服务不可用或超时
**When**: 尝试生成态势摘要
**Then**: 系统应：
- **不降级** - 不返回fallback文本
- 记录完整错误日志（包含请求参数和错误原因）
- 向上层抛出异常
- 允许用户重试或使用上一次成功的摘要

### Requirement: 强类型State和数据模型

态势上报子图 MUST 使用强类型TypedDict定义State，明确必填字段和可选字段。

**Rationale**: 强类型可以在开发阶段捕获字段缺失错误，提高代码可维护性和可靠性。

#### Scenario: State定义符合最佳实践

**Given**: 开发SITREPGraph子图
**When**: 定义SITREPState
**Then**: 应满足：
- 使用 `TypedDict`（不使用`total=False`）
- TypedDict中字段默认为必填，无需 `Required` 标记（report_id, user_id, thread_id, triggered_at）
- 使用 `NotRequired` 标记可选字段（所有数据采集结果）
- 所有字段有明确的类型注解
- 符合LangGraph官方规范（参考：concept-durable-execution.md）
- 示例：
  ```python
  from typing import NotRequired
  from typing_extensions import TypedDict

  class SITREPState(TypedDict):
      # 必填字段（默认，无需标记）
      report_id: str
      user_id: str
      thread_id: str
      triggered_at: datetime

      # 可选字段（使用NotRequired标记）
      active_incidents: NotRequired[List[IncidentRecord]]
      metrics: NotRequired[Dict[str, Any]]
  ```

### Requirement: @task装饰器包装副作用操作

所有有副作用的操作（数据库查询、LLM调用、文件写入）MUST 使用@task装饰器包装，确保Durable Execution。

**Rationale**: @task装饰器使workflow在中断后恢复时不重复执行副作用操作，节省成本并保证一致性。

#### Scenario: 数据库查询使用@task

**Given**: 需要从数据库查询活跃事件
**When**: 实现`fetch_active_incidents`节点
**Then**: 应：
- 使用 `@task` 装饰器
- 定义为独立函数（非lambda）
- 包含完整的类型注解
- 示例：
  ```python
  from langgraph.graph import task

  @task
  async def fetch_active_incidents_task(
      incident_dao: IncidentDAO
  ) -> List[IncidentRecord]:
      return await incident_dao.list_active_incidents()
  ```

#### Scenario: LLM调用使用@task

**Given**: 需要调用LLM生成态势摘要
**When**: 实现`llm_generate_summary`节点
**Then**: 应：
- 创建 `_call_llm_for_sitrep` @task函数
- 接收llm_client和必要参数
- 返回摘要字符串
- 主节点函数调用.result()获取结果
- 参考: `agents/situation.py:58-102`

### Requirement: durability="sync"配置

态势上报子图 SHALL 配置durability="sync"，确保每个节点执行后立即持久化状态。

**Rationale**: SITREP是重要决策依据，必须保证数据不丢失。sync模式虽然性能稍差，但可靠性最高。

#### Scenario: invoke调用配置durability

**Given**: API端点调用SITREPGraph
**When**: 执行graph.invoke()
**Then**: 应配置：
```python
result = graph.invoke(
    initial_state,
    config=config,
    durability="sync"  # 同步持久化
)
```

### Requirement: 完整的日志追踪

态势上报流程的每个关键步骤 MUST 记录structlog日志，包含操作类型、耗时、结果状态。

**Rationale**: 生产环境故障排查需要完整的日志链路，特别是外部依赖（LLM、数据库）的实际调用情况。

#### Scenario: 数据采集节点日志

**Given**: 执行fetch_active_incidents节点
**When**: 节点开始和结束
**Then**: 应记录：
```python
logger.info("sitrep_fetch_incidents_start", report_id=report_id)
# ... 执行查询
logger.info(
    "sitrep_fetch_incidents_completed",
    report_id=report_id,
    incident_count=len(incidents),
    duration_ms=duration * 1000
)
```

#### Scenario: LLM调用日志

**Given**: 调用LLM生成摘要
**When**: LLM请求和响应
**Then**: 应记录：
```python
logger.info(
    "sitrep_llm_call_start",
    report_id=report_id,
    model=llm_model,
    prompt_length=len(prompt)
)
# ... LLM调用
logger.info(
    "sitrep_llm_call_completed",
    report_id=report_id,
    summary_length=len(summary),
    duration_ms=duration * 1000
)
```

### Requirement: API响应时间要求

态势报告生成API SHALL 在合理时间内返回结果，避免超时。

**Rationale**: 指挥决策需要快速响应，过长的等待时间会影响决策效率。

#### Scenario: 正常情况下响应时间

**Given**: 系统运行正常，数据量适中（<100个事件）
**When**: 调用POST /sitrep/generate
**Then**: 应在30秒内返回完整报告
- 数据采集: <5秒
- LLM生成: <15秒
- 持久化: <2秒
- 总计: <30秒

#### Scenario: 超时处理

**Given**: LLM调用超过15秒未响应
**When**: 等待LLM响应
**Then**: 系统应：
- 记录超时日志
- 抛出TimeoutError异常
- 不返回不完整的报告
- 允许用户重试

### Requirement: 独立性和无依赖

态势上报子图 MUST 100%独立，不依赖其他子图的执行结果。

**Rationale**: 降低系统耦合度，提高可测试性和可维护性。

#### Scenario: 数据源独立性

**Given**: 实现SITREPGraph
**When**: 检查数据依赖
**Then**: 应仅依赖：
- DAO层（IncidentDAO, TaskDAO, RescueDAO）
- RiskCacheManager（风险缓存）
- IncidentSnapshotRepository（持久化）
- LLM Client（摘要生成）
- **不依赖**：RescueTacticalGraph、ScoutTacticalGraph等其他子图

#### Scenario: 可独立部署

**Given**: 部署SITREPGraph到生产环境
**When**: 其他子图未部署或故障
**Then**: SITREP功能应：
- 正常运行
- 能够读取历史数据
- 能够生成报告
- 不受其他子图影响

---

## Validation Checklist

在实现完成后，应验证以下检查点：

- [ ] State定义使用TypedDict + NotRequired（符合LangGraph官方规范）
- [ ] 所有副作用操作使用@task包装
- [ ] 配置durability="sync"
- [ ] 关键节点记录完整日志
- [ ] LLM调用使用temperature=0
- [ ] 报告成功保存到incident_snapshots表
- [ ] API响应时间<30秒
- [ ] 无其他子图依赖
- [ ] 单元测试覆盖率≥80%
- [ ] 集成测试通过

---

**Capability**: sitrep-reporting
**Domain**: Emergency Response
**Created**: 2025-11-02
**Status**: PROPOSED
