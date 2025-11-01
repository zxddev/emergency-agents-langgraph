# 救援方案草稿 API

> 版本：2025-11-01
> 负责人：AI 大脑后端

## 1. 概述
- 作用：为前端“救援方案审批”面板提供草稿读取与确认接口。
- 数据来源：`incident_snapshots` 表保存的草稿快照 + `tasks` 表。
- 关联模块：`RescueDraftService`、`RescueTaskGenerationHandler`、前端 `rescue_plan` 面板。

## 2. 草稿结构
- `plan.plan.overview`
  - `taskId`：救援任务候选 ID
  - `incidentId`：事件线程 ID
  - `situationSummary`：态势摘要
  - `analysis.matched_count`：匹配到的队伍数量
  - `riskOutline`：危险区域概要提示
  - `recommendedResourceId`：首选救援力量
- `plan.lines[]`：分线与目标（包含路线概要 `route.distanceKm`/`etaMinutes`）
- `plan.resources[]`
  - `resourceType="team"|"equipment"`
  - `evidenceIds[]` 对应 `evidenceTrace`
- `plan.risks[]`：危险区域明细（zoneId、hazardType、geometry）
- `plan.evidenceTrace[]`
  - `category="kg"|"rag"|"recommendation"`
  - `summary`：引用 KG 标准 / 案例片段 / 资源评估
- `risk_summary`：缓存原始风险摘要（兼容旧链路）
- `ui_actions[]`：前端应执行的 UI 动作序列

## 3. 接口定义

### 3.1 获取草稿
- `GET /rescue/drafts/{draft_id}`
- 响应 `200 OK`
```json
{
  "draft_id": "draft-1",
  "incident_id": "incident-1",
  "entity_id": "entity-1",
  "plan": { ... },
  "risk_summary": {"count": 1},
  "ui_actions": [ ... ],
  "created_at": "2025-11-01T14:05:33Z",
  "created_by": "tester"
}
```
- 错误：`404 未找到草稿`；`503 服务未初始化`

### 3.2 确认草稿
- `POST /rescue/drafts/{draft_id}/confirm`
```json
{
  "commander_id": "commander-1",
  "priority": 70,
  "description": "生成救援方案，匹配 3 支力量",
  "deadline": null,
  "task_code": null
}
```
- 响应 `200 OK`
```json
{
  "task_id": "task-1",
  "incident_id": "incident-1",
  "status": "pending",
  "priority": 70,
  "description": "生成救援方案，匹配 3 支力量"
}
```
- 错误：`404 未找到草稿`

## 4. 服务逻辑
1. `RescueTaskGenerationHandler`
   - 生成 `plan` 结构、记录 `ui_actions`
   - 通过 `RescueDraftService.save_draft` 写入 `incident_snapshots`
2. `RescueDraftService.load_draft`
   - 读取快照，若不存在抛出 `ValueError`
3. `RescueDraftService.confirm_draft`
   - 读取草稿 → 构造 `TaskCreateInput` → 写入 `tasks`
   - 描述生成规则：优先 `response_text`、其次 `plan.overview.analysis.matched_count`
   - 成功后删除快照

## 5. 日志与监控
- `rescue_draft_saved`：草稿落库（draft_id、incident_id）
- `rescue_draft_confirmed`：草稿确认（draft_id、task_id）
- `rescue_draft_delete_failed`：快照删除失败
- Prometheus：
  - `dao_incident_snapshot_*`（已在 DAO 层上报）

## 6. 对接要求
- 前端：
  - 渲染 `plan.*` 新结构，尤其 `resources`/`risks`/`evidenceTrace`
  - 按 `ui_actions` 执行视角切换、面板打开
  - 调用确认接口后刷新任务面板
- Java 服务：
  - 后续需迁移至权威任务表，可复用 `confirm_draft` 创建的 `tasks` 记录

## 7. 测试用例
- `tests/services/test_rescue_draft_service.py`
  - 草稿保存/读取/确认
- `tests/api/test_rescue_draft_api.py`
  - GET/POST 正常流程、404、503

## 8. TODO
- 草稿确认后触发 AdapterHub 下发任务
- 草稿列表查询接口 `/rescue/drafts?incident_id=`
- 与审批流整合（Draft → Proposed → Approved）
