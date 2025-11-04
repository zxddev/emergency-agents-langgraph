# Design: Session Context Binder + Structured Clarify

Context
- LangGraph 官方推荐用 `interrupt` + `checkpointer` 实现人在回路。我们已有 ClarifyRequest 结构与 API needs_input 分支；补足“会话级最近设备”并在澄清中置顶。

Data
- `operational.session_context(thread_id PK, last_device_id, last_device_name, last_device_type, last_intent_type, updated_at)`

Flow
1) `process_intent_core` 收到 `validation_status=invalid` 且 `video-analysis` 缺少 `device_name`：
   - 读取 `ContextService.get(thread_id)`；若有 `last_device_name`，将其作为 ClarifyRequest.options[0] 并 `default_index=0`。
2) `video-analysis` 成功：
   - 从 handler_result.video_analysis 取 `device_id/name`，调用 `ContextService.set_last_device()` 写回。

Constraints
- 强类型；不自动猜测；失败要显式暴露，不做隐藏降级。

