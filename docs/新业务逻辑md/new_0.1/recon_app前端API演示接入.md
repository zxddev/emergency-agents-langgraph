# recon_app 前端 API 演示接入(专业侦察方案-文本摘要)

目标: 前端以 REST API 方式调用侦察子图,基于事件与口令输出专业侦察方案,并返回可直接用于专家展示的文本摘要(plan_summary)。

## 接口

- 路径: `POST /recon/plans`
- 入参(Body JSON):
  - `event_id: UUID` 事件ID(来自 operational.events)
  - `command_text: string` 指挥口令,可包含中文与坐标(如"危化泄漏 北侧坐标 103.80,31.66")
- 出参(JSON):
  - `plan`: ReconPlan(结构化方案,供后续落库/派单)
  - `plan_summary`: string(用于专家演示的文本方案摘要)
  - `plan_payload`: object(方案json,与 `plan` 等价)
  - `tasks`: TaskPlanPayload[](任务写库载荷,包含坐标/设备/能力/时长等)

示例:

```bash
curl -X POST http://<host:port>/recon/plans \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": "f681b2fb-4261-400c-9c1d-561e532d4549",
    "command_text": "北侧危化泄漏 103.80,31.66 无人机热成像巡检"
  }'
```

关键点:
- 本接口不涉及语音,只返回文本与结构化方案。
- 用 `plan_summary` 字段做演示(中文专业摘要: 指令/目标/任务/约束)。

## 专业性保障(来自代码实现)

- 规则与校验:
  - 设备存在/可用/不冲突校验; 持续时长与设备续航一致; 已存在任务冲突拒绝; 受阻道路→执行约束; 严重性影响扇区优先级与安全提示。
  - 参考: `src/emergency_agents/planner/recon_pipeline.py:188-313,318-519`
- LLM 输出受限:
  - 严格 JSON schema 与枚举,超限自动截断; 结构不合法直接报错。
  - 参考: `src/emergency_agents/planner/recon_llm.py:72-139,141-187`
- 草稿摘要可读:
  - 文本按“指令/目标/任务/约束”组织; 任务载荷结构化便于后续落库。
  - 参考: `src/emergency_agents/external/recon_gateway.py:262-333,360-520`

## 可靠性(工程基线)

- 持久化与恢复: 使用 PostgreSQL checkpointer(`schema: recon_checkpoint`), 防止重复副作用。
- 副作用幂等: 关键节点(方案/草稿)用 `@task` 包装,节点内部 `.result()` 获取结果。
- 日志: 关键节点开始/结束/统计与异常全量记录(structlog)。

接线位置:
- 注入: `src/emergency_agents/api/main.py` 启动阶段创建 `_recon_graph` 并 `app.state.recon_graph = _recon_graph`。
- 图构建: `src/emergency_agents/graph/recon_app.py: build_recon_graph_async`。

## 环境要求

- 数据库: 复用全局 `POSTGRES_DSN`, 无需新增表。checkpoint 使用 schema: `recon_checkpoint`。
- LLM: 需设置 `RECON_LLM_MODEL`, `RECON_LLM_BASE_URL`, `RECON_LLM_API_KEY`。
  - 若未配置,启动时报错(遵循“无兜底/不降级”)。

## 日志观察

- `recon_generate_plan_start/done` : 方案生成起止、任务数量
- `recon_prepare_draft_start/done` : 草稿生成起止、任务载荷数量
- `recon_graph_checkpointer_ready` : checkpoint schema 就绪

