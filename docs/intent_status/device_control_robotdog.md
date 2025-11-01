# 意图：device_control_robotdog

## 标准槽位
- `action`
- `device_id`（可选，缺省时使用 `DEFAULT_ROBOTDOG_ID`）
- `distance_m`、`angle_deg`、`speed`（可选）
- `lat` / `lng`（可选）

## 当前实现
- 路由位于 `src/emergency_agents/intent/router.py`：先 interrupt 读回人工确认；确认后写入 `robotdog_command`，路由至 `robotdog_control` 节点。
- 控制节点 `robotdog_control_node`（同模块）调用 `AdapterHubClient`，向 `emergency-adapter-hub` 的 `/api/v3/device-access/control` 下发命令，并将结果写回 `timeline` 与 `integration_logs`。
- REST 接口由 `RobotDogControlHandler` 支持，缺省使用 `DEFAULT_ROBOTDOG_ID`，同样返回 `status=dispatched` 或相应错误码。

## 待完成闭环
1. **复合动作/路径**：根据 `distance_m`、`angle_deg` 等参数扩展命令，支持连续动作或自定义轨迹。
2. **执行回执**：监听适配器推送/遥测，回写机器狗真实执行结果、错误码。
3. **易用性**：为常见动作生成提示词与示例，减少 LLM 解析歧义。
4. **安全策略**：增加权限校验、速率限制与审计流水，防止误触。

## 依赖与注意事项
- 需要配置 `ADAPTER_HUB_BASE_URL`、`DEFAULT_ROBOTDOG_ID`，否则会返回 `adapter_not_configured` 或 `missing_device_id`。
- 仅支持 `forward/back/up/down/turnLeft/turnRight/stop` 等标准动作，其他动作落入 `invalid_action`。
- 依赖人工确认环节，未确认会直接结束并写入 `robotdog_control_rejected` 事件。
