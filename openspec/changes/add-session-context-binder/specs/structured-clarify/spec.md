## ADDED Requirements

### Requirement: 当 `video-analysis` 缺少 `device_name` 时，系统 MUST 返回结构化澄清 `ClarifyRequest`
- System SHALL return a structured ClarifyRequest payload when device_name is missing.
- `slot = device_name`
- `options = [{label, device_id}]`（最多10条）
- `default_index` 指向默认选项
- `reason` 为中文简述

#### Scenario: 缺少设备名触发澄清
- Given: 用户意图 `video-analysis`，未提供 `device_name`
- When: 进入路由校验
- Then: 返回 `status=needs_input` 且 `ui_actions` 含 `ClarifyRequest`

### Requirement: 系统 MUST 将最近设备置顶为默认选项
- System SHALL set the most recently used device as options[0] and default_index=0 when available.
- 澄清 options MUST 优先包含“最近一次使用的设备”作为第一项（若存在且不重复），并设置 `default_index=0`。

#### Scenario: 置顶最近设备
- Given: 上一轮已对设备 X 成功执行 `video-analysis`
- And: 本轮仍为 `video-analysis` 未给设备名
- When: 后端构造澄清
- Then: options[0] = X，`default_index=0`
