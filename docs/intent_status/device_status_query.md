# 意图：device_status_query

## 标准槽位
- `device_type`
- `metric`
- `device_id`（可选）

## 当前实现
- 仅在 `src/emergency_agents/intent/schemas.py` 中定义 Schema，尚无 Handler/Agent 实现。

## 待完成闭环
1. **梳理需求**：明确 metric 列表（电量、在线状态等）与数据来源。
2. **实现查询逻辑**：编写 Handler，查询 `operational.device`、实时遥测或外部监控服务。
3. **结果格式化**：制定统一返回体，便于前端展示；必要时附带多设备列表。
4. **监控与告警**：失败时提供可诊断的错误信息，并记录日志。

## 依赖与注意事项
- 可能需要对接设备遥测队列或缓存；提前确认接口与刷新频率。
- 需考虑批量查询与分页能力，避免阻塞主流程。
