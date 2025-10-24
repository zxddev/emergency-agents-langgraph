# 意图识别 PRD（侦察优先）

## 目的与范围
- 面向专家出题的演示系统：语音/文本 → 意图识别 → Agent执行 → HITL签收 → 证据化方案/任务 → 3D地图上屏。
- 基于现有架构：LangGraph（编排/HITL）、Neo4j（KG：REQUIRES/TRIGGERS/COMPOUNDS）、Qdrant（RAG：历史案例）。
- 不做真实飞控；UAV仅“轨迹模拟至地图”。
- 与 Java 的接口仅留 TODO（明确入参/出参），后期替换真实端点。

## 统一原则
- LLM-first + Schema-first：few‑shot 范式，统一 IntentResult 输出，jsonschema 校验缺槽触发读回追问。
- 高风险统一读回确认；标注流程 PENDING→SIGNED/REJECTED（HITL）。
- 证据化方案：资源可用性检查 + KG≥3 命中 + RAG≥2 引用，不足则不允许自动“下发”。

## 目录
- `common-schema.md`：IntentResult 与通用槽位定义
- 侦察与标注：`recon_plan.md` / `recon_point.md` / `recon_route.md` / `video_analyze.md` / `geo_annotate.md` / `annotation_sign.md`
- 控制/媒体/状态：`device_control_uav.md` / `device_control_robotdog.md` / `media_control.md` / `device_status_query.md`
- 联动/指挥：`route_safe_point_query.md` / `plan_task_approval.md` / `rfa_request.md` / `event_update.md` / `evidence_bookmark_playback.md`

## 验收KPI（演示）
- 意图识别：控制/对话 F1≥0.95；侦察/视频 F1≥0.90；串联解析成功率≥0.90。
- 地图：签收/报告后 → 上屏 ≤2s。
- 方案：资源检查 + KG≥3 + RAG≥2 不足即拒绝下发。
