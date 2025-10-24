# Proposal: intent-recognition-v1

## Summary
以 `prd/intent/` 的PRD为草稿来源，规范化“意图识别 → 专用Agent → HITL签收 → 证据化方案/任务 → 3D地图上屏”的演示闭环。UAV不做真实飞控，仅进行轨迹模拟。与Java联调暂缓，仅在规范中提供 TODO 契约（请求/响应示例）。

## Scope
- ADDED: 统一 IntentResult Schema、意图路由、HITL 读回/确认策略。
- ADDED: 报告驱动（被困/灾情）、标注生命周期、路线/安全点查询、设备状态与机器狗控制、事件更新。
- ADDED: 证据化策略（资源检查 + KG≥3 + RAG≥2）、3D地图图层规范、UAV轨迹模拟规范、Java API 契约（TODO）。
- ADDED: 救援方案/任务生成（带证据化Gate）、证据书签/回放能力（第三方接口TODO，仅日志确认）。
- OUT-OF-SCOPE: 真实飞控、实时视频链、正式Java实现与鉴权、复杂空域合规校验。

## Architecture Impact
- LangGraph 增加“意图路由入口”与中断点（HITL）。
- 与 `specs/06-agent-architecture.md` 对齐：各意图映射到对应分组/智能体或其工具链。
- 数据一致性：严格使用 GeoJSON/WGS84 与统一 IntentResult；审计留痕与时间线事件。

## References (PRD Sources)
- emergency-agents-langgraph/prd/intent/00-README.md
- .../common-schema.md / recon_plan.md / recon_point.md / recon_route.md
- .../video_analyze.md（报告驱动）/ geo_annotate.md / annotation_sign.md
- .../route_safe_point_query.md / device_status_query.md / device_control_robotdog.md
- .../plan_task_approval.md / rfa_request.md / event_update.md
- .../trapped_report.md / hazard_report.md / evidence-policy.md
- .../map-layers-spec.md / uav-track-simulation.md / java-api-contract-todo.md

## KPIs (Demo)
- 意图识别：控制/对话 F1≥0.95；侦察/报告类 F1≥0.90；串联解析成功率≥0.90。
- 地图：签收/报告后 ≤2s 上屏（演示）。
- 方案：资源检查 + KG≥3 + RAG≥2 不足即禁止 dispatch（仅建议+审定）。

## Risks & Trade-offs
- 为保持确定性，采用 few-shot + Schema-first，牺牲部分性能换取稳定与可审计。
- 不做真实飞控，重点展示“从意图到证据化方案”的合理性与可解释性。

## Validation
- 本提案完成后，执行：`openspec validate intent-recognition-v1 --strict`。
