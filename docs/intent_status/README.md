# 意图识别闭环概览

> 生成时间：2025-10-28 22:26:03

| 意图 | 当前状态 | 闭环重点 |
| --- | --- | --- |
| annotation_sign | Agent 已实现，待接入 Java 标注接口 | Java API、状态同步、错误处理 |
| conversation_control | Router 内部控制已生效 | 指令扩展、提示配置化 |
| device-control | Handler 已对接鼎桥机器狗，调用适配器下发动作 | 扩展厂商、动作参数、执行回执、审计 |
| device_control_robotdog | HITL 确认后落入 `robotdog_control` 节点并调用适配器 | 复合动作、遥测回执、权限安全 |
| device_status_query | **未实现** | 需求澄清、查询实现、结果格式 |
| event_update | **未实现** | 事件落库流程、通知机制、历史追踪 |
| evidence_bookmark_playback | **未实现** | 动作语义、证据系统对接、权限审计 |
| geo_annotate | Agent 生成 PENDING 标注 | Java 落库、几何校验、前端联动 |
| hazard_report | Agent 生成 PENDING 事件 | Java 落库、通知、去重 |
| location-positioning | Handler 查询坐标并记录 TODO | 前端联动、坐标校验、日志追踪 |
| plan_task_approval | **未实现** | 审批流程设计、执行落库、审计 |
| recon_minimal | Router 生成轨迹 | 真机/仿真下发、可视化同步 |
| rescue-task-generate / rescue_task_generate | Handler 九步流程已实现 | 外部服务联调、WS 推送、任务落库 |
| rescue-simulation / rescue_simulation | Handler 模拟流程已实现 | 结果持久化、日志区分、建议结构化 |
| rfa_request | **未实现** | 调度流程、状态追踪、权限校验 |
| route_safe_point_query | **未实现** | 路径规划实现、结果呈现、缓存 |
| task-progress-query | Handler 查询任务/路线 | 前端展示、异常提示、性能优化 |
| trapped_report | Agent 生成 PENDING 实体 | Java 落库、告警推送、去重 |
| video-analysis | Handler 查流地址后返回 TODO | 视频分析服务接入、结果回传、监控 |
| video_analyze | **未实现** | 业务定义、Handler 实现、路由注册 |

> 详见同目录下各意图 Markdown 文档。
