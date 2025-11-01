# 意图：video_analyze

## 标准槽位
- `report_text`
- `lat` / `lng`（可选）
- `discovered_type`（可选）

## 当前实现
- 仅在 `src/emergency_agents/intent/schemas.py` 声明 JSON Schema，**没有对应的处理逻辑**。

## 待完成闭环
1. **明确业务动作**：定义该意图在触发后需要执行的分析流程（例如触发离线分析、生成报告摘要等）。
2. **实现 Handler**：在 `src/emergency_agents/intent/handlers/` 下新增处理器，解析 `report_text` 并联动相应服务。
3. **补充路由**：在 `IntentHandlerRegistry` 或 `intent_router` 中注册，使 `/intent/process` 能正确调用。
4. **测试与文档**：添加单元 / 集成测试，并更新操作指南。

## 依赖与注意事项
- 需确认该意图与 `video-analysis` 的边界，避免重复。
- 如果牵涉 NLP/RAG，需接入已有的知识图谱或案例检索组件。
