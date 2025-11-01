# 意图：video-analysis

## 标准槽位
- `device_id`
- `device_type`
- `analysis_goal`
- `analysis_params`（可选）

## 当前实现
- 代码路径：`src/emergency_agents/intent/handlers/video_analysis.py`
- 功能：校验设备存在，查找 `stream_url`（数据库为空则查配置映射），记录“待接入视频处理管线”占位日志并返回提示文案。

## 待完成闭环
1. **串联视频分析服务**：根据 `stream_url` 调用实际的视频识别/分析流水线，拿到结构化结果。
2. **结果回传机制**：把算法输出写入 `video_analysis` payload，必要时通过 WebSocket 推送前端。
3. **多路流/降级策略**：当主流失效时切换备用流，或返回明确的失败原因。
4. **监控与日志**：对接 Prometheus / 结构化日志，追踪分析耗时、成功率。

## 依赖与注意事项
- 数据源：`operational.device` + `operational.device_detail` 的 `stream_url` 字段。
- 需要明确不同 `device_type` 对应的视频协议与鉴权方式。
- 若分析流程需要 GPU/外部服务，请在配置中暴露开关与超时策略。
