# 意图：device-control

## 标准槽位
- `device_type`
- `device_id`
- `action`
- `action_params`（可选，dict）

## 当前实现
- 代码路径：`src/emergency_agents/intent/handlers/device_control.py`
- 功能：
  - 查询 `operational.device` 校验设备存在；
  - 根据 `device_type`/槽位推断厂商，当前自动接入鼎桥机器狗（`dqDog`）；
  - 构造 `/api/v3/device-access/control` 的 `move` 指令，通过 `AdapterHubClient` 调用 `emergency-adapter-hub`；
  - 成功时返回 `status=dispatched`，附带命令与适配器响应；失败场景会区分配置缺失、动作不支持、适配器错误。
- 会话侧：`/intent/process` 将结果写入 `operational.messages`，前端可直接展示执行状态。

## 待完成闭环
1. **扩展厂商映射**：目前仅覆盖鼎桥机器狗，后续需对接大数云智等其它设备。
2. **高级参数**：支持 `action_params`（速度、角度、路径点等）映射到厂商协议。
3. **执行回执**：结合遥测/告警，将执行结果回写对话和日志。
4. **权限审计**：补充权限校验、速率限制、审计流水，降低误操作风险。

## 依赖与注意事项
- 需要配置 `ADAPTER_HUB_BASE_URL`、`ADAPTER_HUB_TIMEOUT`，`DEFAULT_ROBOTDOG_ID` 可作为兜底设备编号。
- 目前仅支持 `ActionType` 定义的标准动作（`forward/back/up/down/turnLeft/turnRight/stop` 等）。
- 仍依赖 `operational.device` 中的设备记录，未登记设备会返回 `not_found`。
