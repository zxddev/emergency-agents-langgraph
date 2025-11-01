# 意图：task-progress-query

## 标准槽位
- `task_id`
- `task_code`
- `need_route`

## 当前实现
- Handler：`src/emergency_agents/intent/handlers/task_progress.py`
- 查询任务、最新日志、路线规划，并拼装文本描述与结构化 payload。

## 待完成闭环
1. **数据一致性**：确保 `operational.tasks`、`task_log`、`task_route_plans` 数据按计划刷新。
2. **前端展示**：根据 payload 绘制路线、显示日志，必要时支持多条路线。
3. **异常提示**：对查询不到任务的场景提供更细的引导（时间范围、输入格式）。
4. **性能优化**：若查询频繁，考虑增加缓存或索引。

## 依赖与注意事项
- 需要 PostgreSQL 连接池配置正确。
- 建议给 `task_code`、`updated_at` 补充索引以提升查询效率。
