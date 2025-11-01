# 意图：annotation_sign

## 标准槽位
- `annotation_id`
- `decision`（SIGNED/REJECTED/APPROVE/REJECT）

## 当前实现
- 逻辑位于 `src/emergency_agents/agents/annotation_lifecycle.py`，将 PENDING 标注更新为 SIGNED/REJECTED，并记录 integration TODO 日志。
- 会话记忆通过 `prepare_memory_node` 写入，方便后续回顾。

## 待完成闭环
1. **对接 Java 标注接口**：调用 `/annotations/{id}/sign`，并在成功后更新状态/时间戳。
2. **错误处理**：针对找不到标注、后端失败等场景返回明确提示并重试/降级。
3. **签收记录落库**：把签收结果写入业务库（或消息队列），供前端刷新标注状态。
4. **测试覆盖**：增加集成测试验证不同决策分支。

## 依赖与注意事项
- `pending_annotations` 列表来自前序 geo_annotate 意图，注意保持上下文一致。
- 需要确认 decision 值与 Java 侧枚举保持一致。
