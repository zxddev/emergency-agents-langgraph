# 基于进度的救援方案 API（简明指南）

- 路径：`POST /ai/plan/from-progress`
- 说明：根据指定事件的任务进度与可用资源，生成下一个作战周期的救援方案（结构化 + 中文摘要）。
- Header：`Content-Type: application/json`

## 入参（Body）
- `incident_id: string(UUID)` 事件ID（必填）。
- `time_range_hours: number` 统计范围（1–168，默认24）。

示例
```bash
curl -X POST http://<host:port>/ai/plan/from-progress \
  -H 'Content-Type: application/json' \
  -d '{
    "incident_id": "f681b2fb-4261-400c-9c1d-561e532d4549",
    "time_range_hours": 24
  }'
```

## 出参（JSON）
- `plan_summary: string`
  - 中文方案摘要（作战目标→投入力量→任务总览）。
- `operational_period: { start_iso: string, end_iso: string }`
  - 本次推荐的作战周期（UTC）。
- `coas: { [label: string]: { label: string, teams: string[], assignments: { unit_id, role, task, target }[] } }`
  - 多套方案（COA-A/B/C），含队伍与分配。
- `recommend: string`
  - 推荐的 COA 标签（如 `"A"`）。
- `justification: { summary: string, factors: object[], references: object[] }`
  - 可解释性信息（评分因子、引用）。
- `constraints_applied: { weather?, aftershock_risk?, roads_blocked?, no_fly? }`
  - 规划时应用的约束（当前为简化版本）。
- `explain_mode: "primary" | "fallback"`
  - 解释模式。

## 行为与错误
- 需要事件几何（event_point/event_range）；缺失将返回 `400`。
- 若最近时间窗内无任务或无可用资源，将返回 `400`。
- 无兜底/不降级：外部依赖失败或数据缺失将直接报错。

## 说明
- 使用同一数据库；内部复用设备网关与任务DAO，严格强类型。
- 规划逻辑与 `/ai/plan/recommend` 保持一致，保证一致性与可解释性。
