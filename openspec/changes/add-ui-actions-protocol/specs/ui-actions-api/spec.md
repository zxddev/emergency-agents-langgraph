# Capability: UI Actions API

## Overview
提供标准化的 UI 动作协议，使 AI 大脑能够控制前端地图、面板、提示等 UI 组件，实现智能交互。

---

## ADDED Requirements

### Requirement: 支持标准 UI Actions 数据结构

系统MUST提供统一的 UIAction 数据结构，包含 action、payload、metadata 三个字段。

#### Scenario: Python 后端生成 UIAction 对象

**Given**: 救援意图处理器完成方案生成
**When**: 调用 `camera_fly_to(lng=121.5, lat=31.2, zoom=15)`
**Then**:
- 返回 `UIAction` 对象
- `action` 字段为 `"camera_flyto"`
- `payload` 字段包含 `{"lng": 121.5, "lat": 31.2, "zoom": 15}`
- `metadata` 字段可选，包含 `incident_id` 和 `task_id`

---

#### Scenario: UIAction 序列化为 JSON

**Given**: 有一个 `UIAction` 对象列表
**When**: 调用 `serialize_actions(actions)`
**Then**:
- 返回 JSON 可序列化的字典列表
- 每个字典包含 `action`, `payload`, `metadata` 字段
- `payload` 中的数据类嵌套对象已转换为字典

---

### Requirement: 支持 camera_flyto 动作类型

系统MUST支持 `camera_flyto` 动作类型，用于控制地图相机飞行到指定坐标。

#### Scenario: 生成相机飞行动作

**Given**: 救援方案包含事件坐标 `(121.5, 31.2)`
**When**: 调用 `camera_fly_to(lng=121.5, lat=31.2, zoom=15)`
**Then**:
- 返回 `UIAction` 对象
- `action` 字段为 `"camera_flyto"`
- `payload.lng` 为 `121.5`
- `payload.lat` 为 `31.2`
- `payload.zoom` 为 `15`（可选，默认 `None`）

---

#### Scenario: 前端执行相机飞行动作

**Given**: 收到包含 `camera_flyto` 动作的响应
**When**: 前端 ActionDispatcher 解析动作
**Then**:
- 调用 Mapbox GL `map.flyTo()` 方法
- 传入 `center: [payload.lng, payload.lat]`
- 传入 `zoom: payload.zoom || 15`
- 传入 `duration: 2000`（2 秒动画）

---

### Requirement: 支持 open_panel 动作类型

系统MUST支持 `open_panel` 动作类型，用于打开侧边栏面板显示详细信息。

#### Scenario: 生成打开面板动作（救援方案）

**Given**: 救援方案生成完成
**When**: 调用 `open_panel("rescue_plan", params={"plan": rescue_plan_data})`
**Then**:
- 返回 `UIAction` 对象
- `action` 字段为 `"open_panel"`
- `payload.panel` 为 `"rescue_plan"`
- `payload.params.plan` 包含救援方案数据（任务、资源、路径警告）

---

#### Scenario: 前端执行打开面板动作

**Given**: 收到包含 `open_panel` 动作的响应
**When**: 前端 ActionDispatcher 解析动作
**Then**:
- 调用 `setDrawerVisible(true)` 打开侧边栏
- 调用 `setDrawerType(payload.panel)` 设置面板类型
- 调用 `setDrawerContent(payload.params.plan)` 设置面板内容

---

### Requirement: 支持 show_toast 动作类型

系统MUST支持 `show_toast` 动作类型，用于显示临时文本提示消息。

#### Scenario: 生成信息提示动作

**Given**: 救援方案生成成功
**When**: 调用 `show_toast("已生成救援方案，等待指挥员确认。", level="info")`
**Then**:
- 返回 `UIAction` 对象
- `action` 字段为 `"show_toast"`
- `payload.message` 为 `"已生成救援方案，等待指挥员确认。"`
- `payload.level` 为 `"info"`
- `payload.duration_ms` 为 `None`（可选，默认 3000）

---

#### Scenario: 生成警告提示动作

**Given**: 检测到路径途经危险区域
**When**: 调用 `show_toast("附近存在2处危险区域：高温区、有毒气体。", level="warning", duration_ms=8000)`
**Then**:
- 返回 `UIAction` 对象
- `payload.level` 为 `"warning"`
- `payload.duration_ms` 为 `8000`（8 秒）

---

### Requirement: 支持 show_risk_warning 动作类型

系统MUST支持 `show_risk_warning` 动作类型，用于在地图上高亮风险区域并显示警告。

#### Scenario: 生成风险警告动作

**Given**: 救援路径途经风险区域 `zone-123`
**When**: 调用 `show_risk_warning("路径途经高温区域，建议绕行", related_resources=["fire-truck-01"], risk_zones=["zone-123"])`
**Then**:
- 返回 `UIAction` 对象
- `action` 字段为 `"show_risk_warning"`
- `payload.message` 为警告消息
- `payload.related_resources` 为相关设备 ID 列表
- `payload.risk_zones` 为风险区域 ID 列表

---

#### Scenario: 前端执行风险警告动作

**Given**: 收到包含 `show_risk_warning` 动作的响应
**When**: 前端 ActionDispatcher 解析动作
**Then**:
1. 调用 `Modal.warning()` 显示警告弹窗
2. 对于每个 `risk_zones` ID，调用后端 API 获取几何数据
3. 在地图上绘制红色多边形（`fill-color: #ff0000, fill-opacity: 0.3`）
4. 对于每个 `related_resources` ID，闪烁设备图标

---

### Requirement: 支持 focus_entity 动作类型

系统MUST支持 `focus_entity` 动作类型，用于快速定位到被困实体的位置。

#### Scenario: 生成聚焦实体动作

**Given**: 救援意图识别到被困实体 ID `rescue-target-001`
**When**: 调用 `focus_entity("rescue-target-001", zoom=18)`
**Then**:
- 返回 `UIAction` 对象
- `action` 字段为 `"focus_entity"`
- `payload.entity_id` 为 `"rescue-target-001"`
- `payload.zoom` 为 `18`（可选）

---

#### Scenario: 前端执行聚焦实体动作

**Given**: 收到包含 `focus_entity` 动作的响应
**When**: 前端 ActionDispatcher 解析动作
**Then**:
1. 查询实体坐标（从后端 API 或本地缓存）
2. 调用 `map.flyTo({ center: [lng, lat], zoom: payload.zoom || 18 })`
3. 闪烁实体图标（3 次，每次 0.5 秒）

---

### Requirement: 意图处理接口返回 ui_actions 字段

系统MUST在 `POST /intent/process` 响应体中包含 `ui_actions` 字段（数组类型）。

#### Scenario: POST /intent/process 返回 ui_actions

**Given**: 用户输入"生成救援方案"
**When**: 调用 `POST /intent/process`
**Then**:
- 响应体包含 `ui_actions` 字段（数组类型）
- `ui_actions` 数组包含至少 1 个 UIAction 对象
- 每个对象包含 `action`, `payload`, `metadata` 字段

---

### Requirement: Java 中间件透传 ui_actions 字段

Java 中间件MUST完整透传 Python 后端返回的 `ui_actions` 字段，不做任何修改或丢失。

#### Scenario: Java 代理接口透传 ui_actions

**Given**: Python 后端返回包含 `ui_actions` 的响应
**When**: Java 中间件调用 Python `/intent/process` 接口
**Then**:
- Java 响应体包含 `ui_actions` 字段（JSON 数组）
- `ui_actions` 数据与 Python 响应完全一致（无丢失、无修改）

---

## MODIFIED Requirements

### Requirement: IntentProcessResult 数据类包含 ui_actions 字段

系统MUST在 `IntentProcessResult` 数据类中新增 `ui_actions: List[Dict[str, Any]]` 字段。

#### Scenario: IntentProcessResult 包含 ui_actions

**Given**: 意图处理器完成处理
**When**: 创建 `IntentProcessResult` 对象
**Then**:
- 数据类包含 `ui_actions` 字段
- 默认值为空列表 `field(default_factory=list)`
- 现有代码无需修改（向后兼容）

---

## REMOVED Requirements

**None** - 此变更不移除任何现有需求
