# Phase 0 数据访问基座梳理

## 1. 目标
- 识别当前 `emergency-agents-langgraph` 内所有直接访问 PostgreSQL 的路径，为 Phase 0 的强类型模型与 DAO 设计提供依据；
- 明确优先建模的表与字段，避免一次性覆盖全部 60+ 张表；
- 制定封装策略，后续逐步替换散落的 SQL 片段。

## 2. 现有数据库访问入口

| 模块 | 文件 | 说明 | 主要 SQL 目标表 |
| --- | --- | --- | --- |
| 意图：定位 | `intent/handlers/location_positioning.py` | 通过 `AsyncConnectionPool` 查询事件、队伍、POI 的坐标 | `operational.events`, `operational.event_entities`, `operational.entities`, `operational.poi_points` |
| 意图：设备控制 | `intent/handlers/device_control.py` | 根据设备 ID 查询基础信息后调用 Adapter Hub | `operational.device` |
| 意图：任务进度 | `intent/handlers/task_progress.py` | 查询任务概况、最新日志、路线规划 | `operational.tasks`, `operational.task_log`, `operational.task_route_plans` |
| 意图：视频分析 | `intent/handlers/video_analysis.py` | 拉取录像地址与设备信息 | `operational.device_video_link`, `operational.device` |
| 战术救援图 | `graph/rescue_tactical_app.py` | 调用 DAO 获取救援力量、生成方案并通知编排 | `operational.rescuers`, `operational.tasks`, `operational.task_route_plans` |
| 会话记忆 | `memory/conversation_manager.py` | 维护 `conversations`、`messages` 以及自定义字段 | `operational.conversations`, `operational.messages` |
| 侦察网关 | `external/recon_gateway.py` | 提供侦察设备、人员、风险的查询接口 | `operational.event_alerts`, `operational.events`, `operational.device`, `operational.device_detail`, `operational.telemetry_virtual`, `operational.rescuers`, `operational.hazard_zones` |
| 设备目录 | `external/device_directory.py` | 从库存/选配表读取设备与车辆信息 | `operational.device`, `operational.car_device_select`, `operational.car_supply_select` |

> 其余文件（如 RAG 管道、日志系统）未直接触达数据库，可暂缓。

## 3. Phase 0 优先建模表

结合业务流与现有 SQL，优先级如下：

1. **事件/事故上下文**
   - `operational.events`（事件主体）
   - `operational.event_entities`（事件关联实体）
2. **实体层**
   - `operational.entities`（地图实体）
   - `operational.entity_detail`（扩展字段）
3. **任务/行动**
   - `operational.missions`、`operational.mission_plans`、`operational.mission_entities`
   - `operational.tasks`、`operational.task_route_plans`、`operational.task_log`
4. **风险与路径**
   - `operational.hazard_zones`
   - `operational.navigation_routes`（若后续引用）
5. **设备与队伍**
   - `operational.device`
   - `operational.rescue_teams_2025`、`operational.rescuers`
6. **遥测**
   - `operational.telemetry_latest`、`operational.telemetry_virtual`

上述集合覆盖战术救援、战术侦察、风险提醒与设备控制当前所需上下文。

## 4. 封装策略

1. **强类型模型**  
   - 使用 `dataclasses.dataclass(slots=True)` + `typing_extensions.TypedDict` 表达行结构与查询参数；
   - 尽量按业务场景拆分视图模型（例如 `EntitySummary`, `TaskProgress`, `HazardZone`），避免暴露整个表。

2. **DAO/Repository 分层**  
   - `emergency_agents.db.models`：定义基础模型与枚举；
   - `emergency_agents.db.dao`：提供异步方法（`get_event`, `list_entities_by_ids` 等），内部统一使用 `psycopg`；
   - `emergency_agents.db.repositories.*`：按业务（救援、侦察、风险）组合 DAO 调用，面向上层图节点。

3. **迁移策略**  
   - Phase 0 先封装查询（读），写操作在 Phase 1A/1B 并行推进时逐步接入；
   - 逐个替换现有 Handler/Graph 中的 SQL 调用，保持函数签名不变，分阶段提交。

4. **测试与观测**  
   - 为 DAO 编写最小单元测试（使用 pytest + async fixtures + Testcontainers/Mock）；
   - 引入 `dao_call_total`、`dao_call_duration_seconds` 等指标，为后续性能分析铺路。

## 5. 下一步

1. 建立 `emergency_agents/db/models.py` 与 `dao.py` 骨架，覆盖第 3 节的核心模型；
2. 先改造 `location_positioning`、`task_progress`、`device_control` 等“简单查询”场景，验证 API；
3. 同步更新文档与测试，确认 Phase 0 交付项可用后再展开战术救援图的深度接入。

## 6. 实施进度（实时更新）
- ✅ 已落地 `db/models.py` 与 `db/dao.py`，封装 `LocationDAO`、`TaskDAO`、`DeviceDAO`，提供强类型返回；
- ✅ `location_positioning`、`task_progress`、`device_control`、`video_analysis` 改用 DAO，移除散落 SQL；
- ✅ 战术救援图已接入 `RescueDAO`、`RescueTaskRepository`，完成救援资源查询与任务/路线写入；
- ✅ DAO 添加结构化日志与 Prometheus 指标（`dao_call_total`, `dao_call_duration_seconds`），便于观测；
- ✅ 新增 `IncidentDAO`/`IncidentSnapshotRepository`，覆盖事件主体、实体关联、风险区与快照写入；`sql/operational.sql` 引入 `incident_snapshots` 表结构；
- ✅ UI Action 全链路串接：`IntentProcessResult` 输出 `ui_actions`、`voice_chat`/REST 直接返回结构化动作，`HttpUIBridge` 重用 `serialize_actions`；
- ✅ LLM 客户端作用域工厂具备单测覆盖（`tests/llm/test_llm_factory.py`），确保作用域 → key 映射生效。
- ✅ 引入 `RiskCacheManager`（启动预热 + 周期刷新），统一缓存危险区域明细，救援/侦察可直接复用。
- ⏳ 后续将把战术救援、侦察图及会话模块逐步迁移到新的仓储接口。
