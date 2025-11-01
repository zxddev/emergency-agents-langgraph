# 意图：hazard_report

## 标准槽位
- `event_type`
- 可选：`title`、`lat`、`lng`、`location_text`、`severity`、`description`、`parent_event_id`

## 当前实现
- `src/emergency_agents/agents/report_intake.py`：生成 PENDING 事件对象，写入 timeline、审计日志，并记录 Java 集成 TODO。

## 待完成闭环
1. **事件落库**：将 PENDING 事件提交到 `emergency-web-api`，落地数据库并返回正式 ID。
2. **通知机制**：触发前端态势图更新、消息提醒。
3. **重复校验**：避免多次报告导致重复事件，可根据坐标/标题做去重。
4. **状态流转**：定义事件生命周期（active、resolved 等），与 Java 层对齐。

## 依赖与注意事项
- 需要保障坐标字段与 GIS 系统兼容。
- 与 `event_update`、`trapped_report` 有逻辑关联，注意数据一致性。
