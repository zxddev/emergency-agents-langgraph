# 意图：geo_annotate

## 标准槽位
- `label`
- `geometry_type`
- 可选：`lat`、`lng`、`coordinates`、`confidence`、`description`

## 当前实现
- `src/emergency_agents/agents/annotation_lifecycle.py` 中创建 PENDING 标注，写入 timeline、记忆，并记录 Java 集成 TODO。

## 待完成闭环
1. **标注落库**：对接 Java `/annotations` 接口，存入业务库并返回新 ID。
2. **几何校验**：对不同 geometry_type 做坐标合法性检查，避免画出错误要素。
3. **同步前端**：通过 WebSocket 或 REST，通知前端刷新标注层。
4. **撤销/变更**：提供撤销或修改能力，与 `annotation_sign` 协同。

## 依赖与注意事项
- 与地图底层坐标系保持一致（默认 WGS84？需确认）。
- 需要考虑多用户并发编辑与冲突解决策略。
