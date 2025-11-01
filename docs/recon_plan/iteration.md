# 侦察方案迭代计划（阶段 C）

## 范围确认
- LangGraph 当前仅提供救援态势流程（`src/emergency_agents/graph/app.py:16`），侦察规划尚未接入图节点。
- 侦察流水线与强类型模型已落地，可复用 `ReconPipeline` 结构（`src/emergency_agents/planner/recon_pipeline.py:28`）。
- 数据持久层缺少侦察专用网关，需对接最新 `operational` schema（`sql/operational.sql:2549`）。

## 本轮目标
1. 建立 Postgres 侦察数据网关：实现上下文读取与方案写入，封装在 `external.recon_gateway`。
2. 将 `ReconPipeline` 注入 LangGraph/REST：统一在启动阶段初始化，避免重复创建实例。
3. 新增 `/recon/plans` API：输入自然语言指令 + 事件 ID，返回方案与写库结果。
4. 为以上改动补充 FastAPI 层与 Graph 层测试（使用 stub gateway），验证无副作用。

## 技术约束
- 所有 Python 代码维持强类型注解，方法体补充中文注释说明数据流。
- 不修改既有救援任务语义；侦察流程独立，不复用 `RescueState`。
- 数据写入遵循 `operational.scheme`/`operational.tasks` 字段约束，不引入降级 fallback。
- 侦察方案生成专用 LLM 需单独配置 `RECON_LLM_MODEL/RECON_LLM_BASE_URL/RECON_LLM_API_KEY`（参见 `config/dev.env`、`src/emergency_agents/config.py`），缺失即阻断启动。

## 参考材料
- 《AI 应急大脑实施规划》战略/战术接口章节：docs/应急AI人机协作方案/AI大脑实施规划/战术与战略能力实施规划.md:44
- 侦察方案契约：docs/ai/recon-plan-contract.md:1
- 数据库结构基线：sql/operational.sql:2549

## 验证清单
- ✅ 网关读取逻辑已单测覆盖（psycopg 游标转换、安全解析）。
- ✅ `/recon/plans` 接口依赖 LangGraph 执行链，侦察 Graph 缺失时返回 503（参见 tests/api/test_recon_endpoint.py）。
- ✅ LangGraph 侦察节点独立编排（src/emergency_agents/graph/recon_app.py:1），不影响救援主图。
- ✅ 坐标解析支持粘连格式（`tests/planner/test_recon_pipeline.py::test_parse_intent_supports_compact_coordinates`）。
- ✅ LLM 规划结果必须引用真实且可用的设备，违例直接失败（`tests/planner/test_recon_pipeline.py::test_pipeline_rejects_invalid_device`）。
- ✅ 网关仅返回方案草稿（summary + plan_payload + tasks_payload），实际入库交由 Java 审批后执行。
- ✅ 数据来源限定：仅统计 `car_supply_select`/`car_device_select` 打勾且设备未被 `operational.tasks` 在建任务占用的条目。

## 阶段进展
- 构建侦察 LangGraph：`src/emergency_agents/graph/recon_app.py`。
- FastAPI 启动时注入侦察 Graph 并在 `/recon/plans` 调用：`src/emergency_agents/api/main.py`、`src/emergency_agents/api/recon.py`。
- 测试覆盖：`tests/graph/test_recon_graph.py`、`tests/api/test_recon_endpoint.py`。
- 侦察方案通过 LLM 生成并经管线校验：`src/emergency_agents/planner/recon_llm.py`、`src/emergency_agents/planner/recon_pipeline.py`；用例见 `tests/planner/test_recon_pipeline.py::test_pipeline_build_plan`。
- HTTP 端到端返回示例详见当前工作记录，可供前端/Java 对照映射；重点字段映射参考计划输出表格。
- 草稿生成接口：`src/emergency_agents/external/recon_gateway.py`，LangGraph 结果由 Java 负责入库。
- 数据表要求：`operational.device` 需新增 `is_recon` 字段，并维护 `operational.device_capability` 提供设备能力标签。
