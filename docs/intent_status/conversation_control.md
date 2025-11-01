# 意图：conversation_control

## 标准槽位
- `command`（cancel/retry/help/back 等）

## 当前实现
- 在 `src/emergency_agents/intent/router.py` 中实现，直接操作状态：取消流程、重置验证、输出帮助文本或回退验证次数。
- 无外部依赖，交互结果会写入会话历史。

## 待完成闭环
1. **指令扩展**：评估是否需要新增“暂停”“恢复”等高级指令。
2. **提示文案配置化**：将帮助文本迁移到配置或文档，便于更新。
3. **多轮上下文协同**：与前端 UI 一致展示当前状态，避免用户误判。

## 依赖与注意事项
- 属于内部控制指令，不需要外部 API；注意不要误路由到业务 handler。
- cancel/retry 会影响 validator 的 `validation_attempt` 计数，使用时确保状态清理完整。
