# 指挥系统 LangGraph 整体规划

## 1. 背景与目标
- 参考业务蓝图：`emergency-agents-langgraph/docs/业务分析/车载指挥系统-技术架构设计.md` 描述车载前突侦察指挥系统的三阶段运行（出发前、行进中、现场指挥）。
- 当前代码现状：
  - 语音入口 `src/emergency_agents/api/voice_chat.py:1` 直接串联 ASR → IntentHandler → `process_intent_core`，未纳入 LangGraph 子图。
  - 意图识别 `src/emergency_agents/api/intent_processor.py:149-523` 负责会话管理、Mem0检索、意图判定、路由，逻辑集中且难以复用。
  - 战术救援逻辑主要集中在 `src/emergency_agents/intent/handlers/rescue_task_generation.py`，虽使用 LangGraph `StateGraph`，但与其他任务耦合。
  - RAG 能力由 `src/emergency_agents/rag/pipe.py`（Qdrant + LlamaIndex）提供，KG 能力由 `src/emergency_agents/graph/kg_service.py` 提供，路线规划通过 `src/emergency_agents/external/amap_client.py` 调高德。
  - 外部执行层依赖 Java Orchestrator (`src/emergency_agents/external/orchestrator_client.py`) 和设备适配 (`src/emergency_agents/external/adapter_client.py`)。
- 目标：在 LangGraph 官方推荐（`docs/新业务逻辑md/langgraph资料/`）指导下，将所有核心流程拆解为强类型、可恢复的子图，实现战术/战略/态势/疏散的端到端体系。

## 2. 分层架构
```
语音/文本入口 → 意图编排子图 → 任务子图矩阵 → 共享能力层 → 外部执行/前端呈现
```

| 层级 | 职责 | 现有实现 | 拆分策略 |
| --- | --- | --- | --- |
| 输入适配 | WebSocket语音、REST文本、灾情数据入口 | `voice_chat.py`, `intent_processor.py`, Java `/api/incidents` | ASR保持服务型；意图调用 LangGraph；灾情数据统一封装 DAO |
| 编排路由 | 意图解析与分发 | `intent_processor.py` | 抽象 `IntentOrchestratorGraph`，使用 Postgres checkpointer，`Command` 分发 |
| 任务执行 | 战术救援、战术侦察、设备控制、态势分析、疏散规划、战略任务 | 分散在 handlers、pipeline、plan_generator | 每类任务独立 StateGraph，按 LangGraph 节点模式组合 |
| 共享能力 | RAG、KG、路线规划、Mem0、GIS | `rag/pipe.py`, `graph/kg_service.py`, `external/amap_client.py`, `memory/mem0_facade.py` | 统一注入，工具节点显式调用，结构化日志 |
| 外部执行 | Java Orchestrator、AdapterHub、前端 | `external/orchestrator_client.py`, `external/adapter_client.py` | 在任务子图末端统一 `dispatch_*` 节点 |

## 3. 子图矩阵规划

### 3.1 意图编排子图（IntentOrchestratorGraph）
- 状态结构：
  ```python
  class IntentState(TypedDict, total=False):
      thread_id: str
      user_id: str
      channel: Literal["voice", "text"]
      raw_text: str
      messages: list[LangChainMessage]
      prediction: IntentPrediction
      validated_slots: dict[str, Any]
      memory_hits: list[dict[str, Any]]
      audit_log: list[dict[str, Any]]
  ```
- 节点：`ingest → classify (src/emergency_agents/intent/classifier.py) → validate/prompt_missing → context_enrich(mem0_facade) → route`。
- 路由采用 `router_next` + `graph.add_conditional_edges` 或 `Command(goto=...)`，确保在图内部完成跳转；只在人工确认场景使用 `interrupt/Command(resume=...)`。
- Checkpointer：Postgres Saver；日志 `intent_processing_start`、`intent_using_default_incident`、`intent_routed`。

### 3.2 战术救援子图（RescueTacticalGraph）
- 参考 `src/emergency_agents/intent/handlers/rescue_task_generation.py`（节点实现已存在），需要拆分纯函数节点：
  1. `resolve_location`
  2. `query_resources`（Postgres `operational.rescuers`）
  3. `kg_reasoning`（KGService）
  4. `rag_analysis`（RagPipeline）
  5. `match_resources`
  6. `route_planning`（AmapClient）
  7. `prepare_response`
  8. `dispatch_java`（OrchestratorClient → `/api/v1/rescue/scenario`）
- 输出：救援方案、资源计划、Java 推送；日志 `rescue_scenario_publish_*`。

### 3.3 战术侦察子图（ReconTacticalGraph）
- 将 `src/emergency_agents/planner/recon_pipeline.py`、`recon_llm.py` 迁移到 LangGraph：`collect_context → hazard_scan → rag_equip → llm_plan → structure_tasks → persist_draft (Postgres) → notify_java`。
- 保持 `POST /recon/plans` 入口兼容 Java。

### 3.4 设备控制子图（DeviceControlGraph）
- 补齐缺失模块（见 `docs/新业务逻辑md/语音控制子图规划.md`）
  - 文件需存在：`src/emergency_agents/api/voice_control.py`、`src/emergency_agents/graph/voice_control_app.py`、`src/emergency_agents/control/models.py`
- 节点：`ingest_intent → normalize → interrupt_confirm → build_command (AdapterHubClient) → dispatch → finalize`。
- 覆盖无人机、机器狗、UGV、USV，结合 `external/adapter_client.py`。
- 旧版 `intent_router_node` 中的机器狗分支将停用，所有设备控制请求统一从意图子图跳转到此子图。

### 3.5 态势分析子图（SituationAnalysisGraph）
- 新增：基于补齐态势播报、人群分布、灾情趋势。
- 节点建议：
  1. `fetch_incident`（Postgres 事件、实体表）
  2. `audit_context`（记录输入来源、操作者、时间）
  3. `rag_case_lookup`（domain=案例/地理）
  4. `kg_inference`（次生灾害预测）
  5. `gis_analysis`（PostGIS/路线/风险区计算）
  6. `llm_summary`（生成态势报告）
  7. `dispatch_report`（Orchestrator 或 REST 返回）

### 3.6 人群疏散子图（EvacuationPlanningGraph）
- 需求：综合事件受灾点、庇护所、道路状态，输出疏散批次与路线。
- 节点：`collect_population → data_audit → traffic_status → route_compute → resource_match (Rag) → llm_plan → dispatch_plan`。

### 3.7 战略级子图（StrategicRescue/StrategicRecon）
- 利用 `src/emergency_agents/agents/plan_generator.py` 和 `agents/situation.py`（Plan、SITREP）构建长期策略：
  - 节点：`collect_context → propose_plan → interrupt_approval → sitrep_generate → notify_provincial`。
  - 输出：态势上报、增援建议。

## 4. 共享能力层
| 能力 | 代码入口 | 使用场景 | 日志要求 |
| --- | --- | --- | --- |
| RAG 检索 | `src/emergency_agents/rag/pipe.py` | 态势、疏散、救援资源 | 统一封装 `rag_enrich_start/end`（基于现有 Prometheus 指标） |
| KG 推理 | `src/emergency_agents/graph/kg_service.py` | 风险预测、态势研判 | `kg_query_start/end`，记录 Cypher 片段摘要 |
| 路线规划 | `src/emergency_agents/external/amap_client.py` | 救援调度、疏散路径 | `amap_direction_start/complete`，捕获异常 |
| 灾情数据 | `Postgres operational.*`, Orchestrator API | 所有任务入口 | `incident_fetch_start/success`, `entity_fetch_start/success` |
| Mem0 | `src/emergency_agents/memory/mem0_facade.py` | 会话记忆、上下文 | 在 `IntentOrchestratorGraph` 统一拉取，写 `memory_enrich_*` |
| LLM 客户端 | `src/emergency_agents/llm/client.py` | 所有推理节点 | `llm_call_start/completed`，记录模型、token、耗时 |
| Adapter/Orchestrator | `external/adapter_client.py`, `external/orchestrator_client.py` | 下发指令、推送场景 | `adapter_dispatch_*`、`orchestrator_http_*` |

## 5. 数据流
1. **灾情输入**：Java `/api/incidents` → Postgres → Python DAO。
2. **语音/文本**：用户→ASR/REST→`IntentOrchestratorGraph`。
3. **任务执行**：子图执行节点调用 Postgres/Neo4j/Qdrant/Amap。
4. **推理生成**：LLM 节点根据 RAG/KG 结果生成建议或报告。
5. **工具执行**：
   - 救援/侦察 → Orchestrator 触发地图推送（`/api/v1/rescue/scenario`等）。
   - 设备控制 → AdapterHub。
   - 战略上报 → 省级系统接口。
6. **结果回传**：REST/WS/SSE 推送至前端；关键事件写入审计日志。

## 6. 实施步骤
1. **恢复基础服务**：补齐 `voice_control` 相关模块，解决 Uvicorn `ModuleNotFoundError`。
2. **建立意图编排子图**：拆 `process_intent_core`，引入 Postgres checkpointer，语音/文本统一接入。
3. **重构战术救援子图**：逐节点拆分，补齐 `dispatch_java` 副作用节点。
4. **迁移战术侦察子图**：LangGraph 化 `ReconPipeline`，保留兼容接口。
5. **实现设备控制子图**：按规划完成模块补齐，将 `intent_router_node` 旧分支迁移至该子图。
6. **扩展态势分析与疏散子图**：先补数据访问与审批节点，再串联 RAG/KG/GIS 输出报告/行动。
7. **构建战略层子图**：生成 SITREP、增援建议、周期上报。
8. **统一日志/监控与文档**：每个节点补日志，更新 `/docs/新业务逻辑md` 补充实施细节。

## 7. 验收标准
- 所有 Python 模块、节点函数、TypedDict 保持完整类型注解，遵循“强类型”要求。
- 子图节点仅承担单一职责，外部调用集中在末端 `dispatch_*` 节点。
- 所有外部服务调用均记录结构化日志（含耗时、状态码、异常信息）。
- checkpointer 覆盖所有长流程子图，可在故障后恢复；`interrupt` 用于审批/确认环节。
- 文档与代码保持同步，业务链路文档放置在 `/docs/新业务逻辑md`，与现有条目无重复。

---

> 本规划基于当前代码与文档事实整理，后续改造需按照此结构逐项落地，任何偏离请先评估并记录原因。
