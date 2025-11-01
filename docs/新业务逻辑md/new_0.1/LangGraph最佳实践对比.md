# LangGraph最佳实践对比（2025-01-03）

## 官方资料基线
- `docs/新业务逻辑md/langgraph资料/references/tutorial-build-basic-chatbot.md`：StateGraph 入门示例，使用 `TypedDict` + `NotRequired` 显式区分必填/可选字段（`class State(TypedDict): ... topic: NotRequired[str]`，见文件 4934-4942 行）。
- `docs/新业务逻辑md/langgraph资料/references/concept-durable-execution.md`：持久化执行要求，明确“wrap any operations with side effects inside @tasks”并在执行时指定 `durability`（文件 3245-3345 行）。
- `docs/新业务逻辑md/new_0.1/子图体系开发规划.md`：Phase0 共性基座约束，要求提供 `src/emergency_agents/logging.py` 统一日志模块（文件 17392-17410 行）。

## 核心比对

### 1. 图状态建模（TypedDict 定义）
- **官方示例**：StateGraph 样例以 `TypedDict` 直接声明必填字段，并通过 `NotRequired[...]` 标注可选字段，未使用 `total=False`（参考 `references/tutorial-build-basic-chatbot.md` 4934-4942 行）。
- **项目现状**：
  - `src/emergency_agents/graph/intent_orchestrator_app.py:21` 定义 `class IntentOrchestratorState(TypedDict, total=False)`，所有字段默认变为可选。
  - `src/emergency_agents/graph/rescue_tactical_app.py:90`、`src/emergency_agents/graph/rescue_tactical_app.py:71` 等同样使用 `total=False`。
  - 其余 TypedDict（如 `RoutePlanData`, `AnalysisSummary`）也全面启用 `total=False`。
- **结论**：Phase0 报告指称“严重违反官方最佳实践”偏激。官方教程确实倾向 `NotRequired` 方案，但并未明令禁止 `total=False`，LangGraph 参考实现中也存在 `total=False` 的 TypedDict（`references/graphs` 相关 API）。风险点在于：**图状态缺乏显式必填约束**，易导致缺字段时静态检查失效，应归类为“设计质量问题”而非“违反官方禁令”。

### 2. 副作用节点缺少 `@task`
- **官方要求**：`concept-durable-execution.md` 3261-3333 行强调：“wrap any non-deterministic operations… inside @tasks… to ensure they are not repeated”。未包装的副作用在恢复时会再次执行。
- **项目现状**：
  - `src/emergency_agents/graph/rescue_tactical_app.py:214-370` 中的 `resolve_location` / `query_resources` / `kg_reasoning` / `rag_analysis` / `route_planning` / `persist_task` / `ws_notify` 直接调用外部 API、数据库、消息推送，无 `@task` 包装。
  - `persist_task` 在 `src/emergency_agents/graph/rescue_tactical_app.py:289-364` 内写入 Postgres，重复执行会产生重复任务/路线。
- **结论**：Phase0 指出的问题属实，属于高风险缺陷。官方建议与代码偏离明显，必须补齐 `@task` 包装及幂等处理。

### 3. 执行 `durability` 未配置
- **官方要求**：同一文档 3334-3345 行提供示例，要求在 `graph.invoke/stream` 时显式传入 `durability`（`"sync"`, `"async"`, `"exit"`）以匹配场景。
- **项目现状**：
  - `src/emergency_agents/graph/rescue_tactical_app.py:725-732` 调用 `self._compiled.ainvoke(state, config={"configurable": {"thread_id": ...}})`，未传 `durability`，默认退化为 `"exit"`。
  - `src/emergency_agents/intent/handlers/rescue_task_generation.py:845-913` 等入口同样缺少 `durability`；`src/emergency_agents/api/intent_processor.py:144-147` 也只设置 `thread_id`。
- **结论**：Phase0 判断正确。长流程（救援/侦察）若进程崩溃将丢失中间状态，违背官方持久化建议。

### 4. 统一日志模块缺失
- **规划要求**：`子图体系开发规划.md` 第 2 章将“日志与指标”列入 Phase0 必达，并指定落地路径 `src/emergency_agents/logging.py`。
- **项目现状**：
  - 仓库无该文件（`ls src/emergency_agents`）。
  - 各模块直接 `structlog.get_logger(__name__)`，无全局 formatter/processor；Prometheus 监控也在 DAO 内部自行注册。
- **结论**：Phase0 报告此项准确，统一日志框架尚未实现。

## 对 Phase0-问题分析报告的复核结论
| 问题编号 | Phase0 原结论 | 复核结果 | 说明 |
|----------|---------------|----------|------|
| P0-1 | `TypedDict(total=False)` 严重违反官方实践 | **部分成立** | 的确缺少必填约束，但官方文档未禁止 `total=False`，需重新表述为“未按推荐方式显式区分必填/可选，类型检查风险高”。 |
| P0-2 | 副作用缺 `@task`，破坏幂等性 | **成立** | 关键节点直接调用外部 API/数据库，重放会重复副作用，违反官方 durable execution 指南。 |
| P0-3 | 未配置 `durability`，无法故障恢复 | **成立** | 所有入口默认 `durability="exit"`，与长流程需求不符。 |
| P0-4 | 缺统一日志模块 | **成立** | 规划明确要求 `logging.py`，仓库缺失。 |

## 建议后续动作
1. **状态建模**：梳理每个状态对象的必填字段，改用 `TypedDict` + `Required/NotRequired` 或拆分 dataclass，确保类型检查能捕获缺字段；同时补充单元测试覆盖关键字段缺失场景。
2. **@task 封装**：为 `resolve_location`、`query_resources`、`route_planning`、`persist_task` 等副作用节点拆出 `@task` 包装，复用持久化结果并加上幂等校验。
3. **Durability 策略**：在所有 `invoke/ainvoke` 调用点显式传入 `durability`；长流程使用 `"sync"`，编排类流程使用 `"async"`，短链路保留 `"exit"`。
4. **日志基座**：按规划落地 `src/emergency_agents/logging.py`，统一 structlog processor、JSON/控制台渲染、trace-id 注入，同时为 Prometheus 指标提供集中注册入口。
