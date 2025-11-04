## ADDED Requirements

### Requirement: 系统 MUST 为每个 `thread_id` 维护最近设备上下文（`session_context`）
- System SHALL persist and retrieve last device fields per thread via session_context table.
- 字段：`last_device_id/name/type`、`last_intent_type`、`updated_at`
- 写入时机：相关意图成功后（本期覆盖 `video-analysis`）。
- 读取时机：构造澄清时。

#### Scenario: 成功后写回最近设备
- Given: `video-analysis` 在设备 Y 上执行成功
- When: 返回处理结果
- Then: `session_context.last_device_name = Y`
