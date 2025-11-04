# 侦察方案 API（简明指南）

- 路径：`POST /recon/plans`
- 说明：根据事件ID与口令生成专业侦察方案；仅返回文字与结构化数据（无语音）。
- Header：`Content-Type: application/json`

## 入参（Body）
- `event_id: string(UUID)` 事件ID（operational.events.id）。
- `command_text: string` 指挥口令，可含坐标（如 `103.80,31.66`）。

示例
```bash
curl -X POST http://<host:port>/recon/plans \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": "f681b2fb-4261-400c-9c1d-561e532d4549",
    "command_text": "北侧危化泄漏 103.80,31.66 无人机热成像巡检"
  }'
```

## 出参（JSON）
- `plan_summary: string`
  - 中文方案摘要，按“指令/目标/任务/约束”组织，直接给专家展示。
- `plan: object` ReconPlan（结构化方案，用于对账/落库）
  - `objectives: string[]` 方案目标（≤3 条）。
  - `sectors: { sector_id, name, area: GeoPoint[], priority, tasks: string[] }[]`
  - `tasks: { task_id, title, mission_phase, objective, priority, target_points: GeoPoint[], required_capabilities: string[], recommended_devices: string[], duration_minutes?: number, safety_notes?: string }[]`
  - `assets: { asset_id, asset_type, usage, duration_minutes? }[]`
  - `constraints: { name, detail?, severity }[]`
  - `justification: { summary, reasoning_chain: string[], risk_warnings: string[] }`
  - `meta: { generated_by, schema_version, data_sources: string[], missing_fields: string[], warnings: string[] }`
- `plan_payload: object` 与 `plan` 等价的 JSON 载荷（便于直接存储）。
- `tasks: object[]` TaskPlanPayload（任务写库载荷）
  - `scheme_id, task_id, objective, target_points: GeoPoint[], required_capabilities: string[], recommended_devices: string[], duration_minutes?, safety_notes?, dependencies: string[], assigned_unit?`

GeoPoint
- `{ lon: number, lat: number }` 经/纬度（度）。

## 行为与错误
- 幂等与恢复：已启用 PostgreSQL checkpoint 和 @task 包装（重复调用不重复副作用）。
- 可能错误：
  - 400 参数缺失（如 `event_id`/`command_text`）。
  - 500 业务校验失败（无可用设备/续航不符/任务冲突/LLM 输出结构不合法等）。

## 备注
- 使用同一数据库实例；checkpoint schema：`recon_checkpoint`。
- LLM 需配置 `RECON_LLM_MODEL/BASE_URL/API_KEY` 才能生成方案。
