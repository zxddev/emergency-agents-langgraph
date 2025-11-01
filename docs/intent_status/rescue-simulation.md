# 意图：rescue-simulation / rescue_simulation

## 标准槽位
- 同 `rescue-task-generate`（共用 Schema）

## 当前实现
- Handler：`RescueSimulationHandler`（同文件 `rescue_task_generation.py`），复用任务生成流程但跳过 WS 推送，返回文字报告。

## 待完成闭环
1. **结果持久化**：决定是否需要存档模拟结果，供后续评估。
2. **参数区分**：在日志与监控中标记 `simulation_mode`，便于分流统计。
3. **差距建议**：根据匹配结果提供结构化的补充建议（目前主要是文本）。

## 依赖与注意事项
- 与任务生成共享外部依赖；需保证模拟不会误触发真实执行。
- 建议在前端醒目标注“模拟结果”。
