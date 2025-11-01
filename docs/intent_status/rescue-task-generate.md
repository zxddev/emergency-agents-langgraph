# 意图：rescue-task-generate / rescue_task_generate

## 标准槽位
- `mission_type`
- `location_name`
- `coordinates`
- `disaster_type`
- `impact_scope`
- `simulation_only`
- `task_id`（可选）

## 当前实现
- Handler：`src/emergency_agents/intent/handlers/rescue_task_generation.py`
- 实现九步流程：地名解析、高德路径、资源查询、KG 推理、RAG 案例、能力匹配、路径规划缓存、结果组装、WS 通知。

## 待完成闭环
1. **外部服务联调**：确保 KG、RAG、高德 API 均可用，补充异常兜底与熔断策略。
2. **WS 通道**：把 `ws_payload` 通过 `emergency-web-api` 推送前端，确认协议。
3. **任务落库**：将生成的任务写入业务库，支持人工调整与二次审批。
4. **性能监控**：接入 Prometheus 指标（调用耗时、缓存命中等）。

## 依赖与注意事项
- 需要配置高德 API key 以及 KG/RAG 端点。
- 因流程复杂，务必保持单元测试与集成测试覆盖。
