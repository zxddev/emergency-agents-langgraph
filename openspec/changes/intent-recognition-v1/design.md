# Design: intent-recognition-v1

## Approach
- LLM-first + Schema-first 意图识别：few-shot + Top-K 样例检索；统一 IntentResult（intent_type/slots/meta）；jsonschema 校验缺槽触发读回；高风险 need_confirm。
- LangGraph 编排：新增“intent router”入口节点与中断（HITL），将意图分派到对应 Agent。
- UAV 不做真实飞控：仅输出轨迹LineString（alt/time/steps）用于3D上屏；写入 timeline 事件。
- 证据化门槛：资源检查 + KG≥3 + RAG≥2，不足禁止自动 dispatch；仅建议 + 审定。
- 第三方集成：当前阶段全部为 TODO，仅记录请求/响应契约，并在实际调用前打印 "READY TO CALL JAVA API" 日志确认。

## Mapping (Intent → Agent groups)
- trapped_report / hazard_report → Situation Group（侦察/标绘）
- geo_annotate / annotation_sign → Situation Mapping Agent（标注生命周期）
- recon_minimal（plan/point/route合一） → Situation Group（生成轨迹与AOI展示）
- route_safe_point_query → Planning/Resource Group（路线与安全点）
- device_status_query / robotdog_control → Resource/Execution（设备状态与控制）
- plan_task_approval → Planning Group（审批HITL）
- rfa_request → Resource Group（增援需求）
- event_update → Situation Group（事件树）
- video_analyze（report-mode） → Situation Group（报告优先，无实时视频）
- rescue_task_generate → Planning Group（证据化方案/任务生成，需HITL审批）
- evidence_bookmark_playback → Execution/Observability（证据书签/回放/导出）

## Data & Layers
- GeoJSON/WGS84；annotations/uav_tracks/routes/safe_points/events/tasks；证据链包含 KG 关系与 RAG 案例引用。

## Java Integration (TODO-only)
- 仅在规范中给出请求/响应示例；实现阶段替换；实际调用前打印日志确认。

## Validation
- openspec validate intent-recognition-v1 --strict。
