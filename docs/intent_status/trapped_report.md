# 意图：trapped_report

## 标准槽位
- `count`
- 可选：`location_text`、`lat`、`lng`、`time_reported`、`description`

## 当前实现
- `src/emergency_agents/agents/report_intake.py`：生成 PENDING 被困实体，写 timeline、审计日志，记录 Java TODO。

## 待完成闭环
1. **实体落库**：将 PENDING 实体写入 Java 后端并返回正式 ID。
2. **告警推送**：对重大被困数量发出通知（短信/广播）。
3. **重复检测**：避免同一地点被多次录入，可按坐标+时间去重。
4. **后续流程**：与救援任务生成联动，自动触发能力匹配。

## 依赖与注意事项
- 需要与事件/任务库对齐字段含义与坐标系。
- 改变 `count` 逻辑时注意负值/异常值的校验。
