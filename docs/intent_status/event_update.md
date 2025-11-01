# 意图：event_update

## 标准槽位
- `event_type`
- `title`
- 其他可选：`lat`、`lng`、`severity`、`description`、`parent_event_id`

## 当前实现
- 仅存在 Schema 定义，无对应 Handler/Agent。

## 待完成闭环
1. **制定业务流程**：明确更新事件时要写入哪些表（如 `operational.events`）。
2. **实现 Handler**：完成字段校验、落库逻辑，以及必要的权限检查。
3. **通知链路**：更新后推送前端 / Java 服务刷新事件态势。
4. **历史追踪**：记录更新历史与操作人，便于审计。

## 依赖与注意事项
- 与 `hazard_report`、`trapped_report` 产生的实体存在关联，需保证状态同步。
- 注意避免覆盖真实生产数据，最好支持增量更新策略。
