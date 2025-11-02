# 前端集成 OpenSpec 提案 - 战术救援/侦察 UI Actions 协议

**提案类型**: 接口文档与集成指南
**目标**: 最快速度实现前端与 AI 大脑的交互，展示战术救援/侦察能力
**优先级**: P0（峰会演示核心功能）
**创建日期**: 2025-11-02
**状态**: ⚠️ Python 后端核心链路已上线，但 UI Actions 协议与风险缓存使用范围需按最新实现同步更新，仍等待前端接入落地

---

## 执行摘要

### 问题陈述
用户需求："我现在要最快速度的完成和前端的交互，战术救援和战术侦察，还有战略救援和战略侦察，还有风险提醒"

### 核心发现（基于 10 层代码验证）
1. **✅ 战术链路可执行**：`RescueTacticalGraph` 与 `ScoutTacticalGraph` 均已按 StateGraph 架构落地（`src/emergency_agents/graph/rescue_tactical_app.py`、`src/emergency_agents/graph/scout_tactical_app.py:1-1479`），处理器会返回 UI 动作矩阵。
2. **📌 UI Actions 实际包含标准 + 扩展动作**：标准动作来自 `src/emergency_agents/ui/actions.py`（`camera_flyto` / `open_panel` / `show_toast` / `show_risk_warning` / `focus_entity`），再叠加 `toggle_layer`、`raw_action` 以及侦察子图内联生成的 `preview_route`、`open_scout_panel`、`show_risk_hints` 等扩展动作，文档需覆盖全部清单。
3. **⚠️ 风险缓存仅在救援链路启用**：`RescueTaskGenerationHandler` 会优先命中 `RiskCacheManager`（`src/emergency_agents/intent/handlers/rescue_task_generation.py:232-310`），`ScoutTaskGenerationHandler` 则直接访问 `RiskDataRepository`（`src/emergency_agents/intent/handlers/scout_task_generation.py`），与原描述不符。
4. **🎯 瓶颈仍在前端**：Python 端已返回结构化 `ui_actions` 队列，但缺少 Action Dispatcher 与地图/面板组件，前端需按真实协议补齐。
5. **❌ 战略层不存在**：代码中没有 StrategicGraph 实现，目前仅交付战术层能力（救援/侦察）。

### 最快速实施路径
**3 天 MVP 方案**（每天都有可演示进展）：
- **Day 1**: Action Dispatcher + 相机控制 + Toast 提示 + 基础面板
- **Day 2**: 风险警告可视化 + 地图高亮
- **Day 3**: Java 中间件集成 + 全链路联调

---

## 一、UI Actions 协议规范

### 1.1 协议概述

**数据结构**（已验证，来自 `src/emergency_agents/ui/actions.py`）：

```python
@dataclass(slots=True)
class UIAction:
    action: str                              # Action 类型（如 "camera_flyto"）
    payload: Any                             # Action 负载（类型化数据类）
    metadata: Optional[Mapping[str, Any]]    # 元数据（incident_id, task_id）
```

**序列化格式**（JSON，前端接收到的格式）：

```typescript
interface UIAction {
  action: string;                    // Action 类型
  payload: Record<string, any>;      // 负载数据
  metadata?: {                       // 元数据（可选）
    incident_id?: string;
    task_id?: string;
    [key: string]: any;
  };
}
```

### 1.2 支持的 Action 类型

#### 1.2.1 camera_flyto - 相机飞行

**用途**: 地图相机飞行到指定坐标和缩放级别

**Payload 结构**:
```typescript
interface CameraFlyToPayload {
  lng: number;        // 经度
  lat: number;        // 纬度
  zoom?: number;      // 缩放级别（可选，默认 15）
}
```

**实际示例**:
```json
{
  "action": "camera_flyto",
  "payload": {
    "lng": 121.5,
    "lat": 31.2,
    "zoom": 15
  },
  "metadata": {
    "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
    "task_id": "abc-123"
  }
}
```

**前端实现参考**（Mapbox GL）:
```typescript
function handleCameraFlyTo(payload: CameraFlyToPayload) {
  map.flyTo({
    center: [payload.lng, payload.lat],
    zoom: payload.zoom || 15,
    duration: 2000  // 2秒动画
  });
}
```

---

#### 1.2.2 open_panel - 打开侧边栏面板

**用途**: 打开侧边栏/弹窗，显示救援方案或侦察方案详情

**Payload 结构**:
```typescript
interface OpenPanelPayload {
  panel: 'rescue_plan' | 'scout_plan';  // 面板类型
  params: {
    plan: RescuePlan | ScoutPlan;       // 方案数据
  };
}

// 救援方案数据结构
interface RescuePlan {
  tasks: Array<{
    task_id: string;
    description: string;
    priority: 'high' | 'medium' | 'low';
  }>;
  resources: Array<{
    resource_id: string;
    type: string;
    quantity: number;
  }>;
  routeWarnings: Array<{
    message: string;
    zoneId?: string;
    resourceIds?: string[];
  }>;
}

// 侦察方案数据结构
interface ScoutPlan {
  targets: Array<{
    location: { lng: number; lat: number };
    priority: 'high' | 'medium' | 'low';
  }>;
  riskHints: string[];  // 风险提示数组
}
```

**实际示例**:
```json
{
  "action": "open_panel",
  "payload": {
    "panel": "rescue_plan",
    "params": {
      "plan": {
        "tasks": [
          {"task_id": "task-001", "description": "疏散被困人员", "priority": "high"}
        ],
        "resources": [
          {"resource_id": "fire-truck-01", "type": "消防车", "quantity": 2}
        ],
        "routeWarnings": [
          {"message": "路径途经高温区域，建议绕行", "zoneId": "zone-123"}
        ]
      }
    }
  },
  "metadata": {...}
}
```

**前端实现参考**（Ant Design）:
```typescript
function handleOpenPanel(payload: OpenPanelPayload) {
  setDrawerVisible(true);
  setDrawerType(payload.panel);
  setDrawerContent(payload.params.plan);
}

// JSX
<Drawer visible={drawerVisible} onClose={() => setDrawerVisible(false)}>
  {drawerType === 'rescue_plan' && <RescuePlanPanel plan={drawerContent} />}
  {drawerType === 'scout_plan' && <ScoutPlanPanel plan={drawerContent} />}
</Drawer>
```

---

#### 1.2.3 show_toast - 显示临时提示

**用途**: 顶部/右上角显示临时提示消息，自动消失

**Payload 结构**:
```typescript
interface ShowToastPayload {
  message: string;                           // 提示内容
  level: 'info' | 'warning' | 'error';       // 提示级别
  duration_ms?: number;                      // 持续时间（毫秒）
}
```

**实际示例**:
```json
// 信息提示（默认 3 秒）
{
  "action": "show_toast",
  "payload": {
    "message": "已生成救援方案，等待指挥员确认。",
    "level": "info"
  }
}

// 风险警告（8 秒）
{
  "action": "show_toast",
  "payload": {
    "message": "附近存在2处危险区域：高温区、有毒气体。",
    "level": "warning",
    "duration_ms": 8000
  }
}
```

**前端实现参考**（Ant Design）:
```typescript
function handleShowToast(payload: ShowToastPayload) {
  const duration = payload.duration_ms ? payload.duration_ms / 1000 : 3;

  if (payload.level === 'info') {
    message.info(payload.message, duration);
  } else if (payload.level === 'warning') {
    message.warning(payload.message, duration);
  } else {
    message.error(payload.message, duration);
  }
}
```

---

#### 1.2.4 show_risk_warning - 显示风险警告

**用途**: 在地图上高亮风险区域，显示警告弹窗

**Payload 结构**:
```typescript
interface ShowRiskWarningPayload {
  message: string;                  // 警告消息
  related_resources?: string[];     // 相关设备 ID 列表（可选）
  risk_zones?: string[];            // 风险区域 ID 列表（可选）
}
```

**实际示例**:
```json
{
  "action": "show_risk_warning",
  "payload": {
    "message": "路径途经高温区域，建议绕行",
    "related_resources": ["fire-truck-01", "ambulance-02"],
    "risk_zones": ["zone-123"]
  },
  "metadata": {...}
}
```

**前端实现参考**（Mapbox GL + 后端 API）:
```typescript
async function handleShowRiskWarning(payload: ShowRiskWarningPayload) {
  // 1. 显示警告弹窗
  Modal.warning({
    title: '风险警告',
    content: payload.message
  });

  // 2. 高亮风险区域
  if (payload.risk_zones) {
    for (const zoneId of payload.risk_zones) {
      // 调用后端 API 获取区域几何数据
      const geoJson = await fetch(`/api/risk-zones/${zoneId}`).then(r => r.json());

      // 在地图上绘制红色多边形
      map.addSource(zoneId, { type: 'geojson', data: geoJson });
      map.addLayer({
        id: `${zoneId}-fill`,
        type: 'fill',
        source: zoneId,
        paint: {
          'fill-color': '#ff0000',
          'fill-opacity': 0.3
        }
      });
    }
  }

  // 3. 闪烁相关设备图标（可选）
  if (payload.related_resources) {
    payload.related_resources.forEach(deviceId => {
      blinkDeviceMarker(deviceId);  // 实现设备图标闪烁效果
    });
  }
}
```

---

#### 1.2.5 focus_entity - 聚焦实体（救援链路已产出）

**状态**: ✅ 当救援意图解析到实体信息时，`RescueTaskGenerationHandler` 会直接输出 `focus_entity` 动作（`src/emergency_agents/intent/handlers/rescue_task_generation.py:792-809`），用于地图聚焦被困目标。

**Payload 结构**:
```typescript
interface FocusEntityPayload {
  entity_id: string;      // 被困实体 ID
  zoom?: number;          // 可选：聚焦时的缩放级别
}
```

**实际示例**:
```json
{
  "action": "focus_entity",
  "payload": {
    "entityId": "rescue-target-001",
    "zoom": 18
  },
  "metadata": {
    "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
    "task_id": "task-123"
  }
}
```

**前端处理建议**:
- 调用地图 API 聚焦到实体坐标，可与 `camera_flyto` 联动降低跳转延迟。
- 在实体图标上叠加闪烁/描边，提升指挥员识别度。

---

#### 1.2.6 toggle_layer - 图层开关

**用途**: 从后端远程控制应急地图的专题图层（`src/emergency_agents/ui/actions.py:20-65`）。

**Payload 结构**:
```typescript
interface ToggleLayerPayload {
  layer_code: string;             // 图层编码（需与前端约定）
  layer_name?: string;            // 图层名称（可选，用于提示）
  on: boolean;                    // true 开启 / false 关闭
}
```

**解析要点**:
- 建议前端维护 “layer_code → 数据源 / 样式” 映射表。
- 当图层不存在时记录告警日志，不做静默失败。

---

#### 1.2.7 raw_action - 兼容自定义动作

**用途**: 作为应急兜底接口传输暂未建模的 UI 指令，保持协议向后兼容（`src/emergency_agents/ui/actions.py:181-186`）。

**解析要点**:
- `payload`、`metadata` 均为 `Record<string, any>`；前端在消费前需校验 `action` 字段。
- 建议在接入阶段对未识别的 `action` 做日志标记，以便回填正式类型。

---

### 1.3 侦察子图扩展动作

`ScoutTacticalGraph` 会在节点 `prepare_ui_actions_task` 中追加扩展动作（`src/emergency_agents/graph/scout_tactical_app.py:1320-1374`），其结构与标准 UIAction 不同，前端需单独适配：

| 动作 ID | 数据结构 | 触发条件 | 作用 |
|---------|----------|----------|------|
| `preview_route` | `{ waypoints: ReconWaypoint[]; total_distance_m: number; total_duration_sec: number }` | 生成完整航线后输出 | 地图展示侦察路线，为行动人员预演路径 |
| `open_scout_panel` | `{ devices: SelectedDevice[]; device_count: number }` | 存在可执行设备时输出 | 打开侦察面板，展示设备分配 |
| `show_risk_hints` | `{ hints: string[] }` | 侦察计划包含风险提示时输出 | 在 UI 上弹出风险提示列表 |

> ⚠️ 以上扩展动作当前由侦察子图直接返回，为保持一致性，可在前端解析后转化为标准组件（例如调用现有面板/地图模块）。

---

## 二、API 接口规范

### 2.1 意图处理接口

**端点**: `POST /intent/process`

**请求体**:
```typescript
interface IntentProcessRequest {
  user_id: string;         // 用户 ID
  thread_id: string;       // 会话 ID（同一用户可以有多个会话）
  message: string;         // 用户输入的文本
  incident_id: string;     // 事件 ID（可选，默认使用 demo incident）
  channel: 'web' | 'voice' | 'mobile';  // 渠道
}
```

**响应体**:
```typescript
interface IntentProcessResponse {
  status: 'success' | 'needs_input' | 'unknown' | 'error';
  intent: {
    intent_type: string;      // 意图类型（如 "rescue-task-generation"）
    confidence: number;        // 置信度（0-1）
    slots: Record<string, any>;  // 槽位数据
  };
  result: {
    response_text: string;     // 文本回复
    [key: string]: any;        // 业务数据（rescue_plan, scout_plan 等）
  };
  ui_actions: UIAction[];      // ⭐ 核心：UI 动作数组
  history: Array<{             // 对话历史
    role: 'user' | 'assistant';
    content: string;
  }>;
  memory_hits: any[];          // 记忆检索结果
  audit_log: any[];            // 审计日志
}
```

### 2.2 完整请求/响应示例

#### 场景 1: 战术救援任务生成

**请求**:
```bash
curl -X POST http://localhost:8008/intent/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "commander-001",
    "thread_id": "rescue-thread-001",
    "message": "某化工厂发生火灾，有3名工人被困，请生成救援方案",
    "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
    "channel": "web"
  }'
```

**响应**（简化版，重点关注 ui_actions）:
```json
{
  "status": "success",
  "intent": {
    "intent_type": "rescue-task-generation",
    "confidence": 0.95,
    "slots": {
      "event_type": "火灾",
      "location": "化工厂",
      "trapped_count": 3
    }
  },
  "result": {
    "response_text": "已生成救援方案，等待指挥员确认。",
    "rescue_plan": {
      "tasks": [...],
      "resources": [...],
      "routeWarnings": [
        {"message": "路径途经高温区域，建议绕行", "zoneId": "zone-123"}
      ]
    }
  },
  "ui_actions": [
    {
      "action": "camera_flyto",
      "payload": {"lng": 121.5, "lat": 31.2, "zoom": 15},
      "metadata": {"incident_id": "fef8469f-...", "task_id": "..."}
    },
    {
      "action": "open_panel",
      "payload": {
        "panel": "rescue_plan",
        "params": {"plan": {...}}
      },
      "metadata": {...}
    },
    {
      "action": "show_toast",
      "payload": {
        "message": "已生成救援方案，等待指挥员确认。",
        "level": "info"
      },
      "metadata": {...}
    },
    {
      "action": "show_toast",
      "payload": {
        "message": "附近存在2处危险区域：高温区、有毒气体。",
        "level": "warning",
        "duration_ms": 8000
      },
      "metadata": {...}
    },
    {
      "action": "show_risk_warning",
      "payload": {
        "message": "路径途经高温区域，建议绕行",
        "risk_zones": ["zone-123"]
      },
      "metadata": {...}
    }
  ]
}
```

#### 场景 2: 战术侦察任务生成

**请求**:
```bash
curl -X POST http://localhost:8008/intent/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "commander-001",
    "thread_id": "scout-thread-001",
    "message": "派无人机侦察受灾区域，评估次生灾害风险",
    "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
    "channel": "web"
  }'
```

**响应** (ui_actions 示例):
```json
{
  "status": "success",
  "ui_actions": [
    {
      "action": "camera_flyto",
      "payload": {"lng": 121.48, "lat": 31.25, "zoom": 16},
      "metadata": {"incident_id": "..."}
    },
    {
      "action": "open_panel",
      "payload": {
        "panel": "scout_plan",
        "params": {
          "plan": {
            "targets": [
              {"location": {"lng": 121.48, "lat": 31.25}, "priority": "high"}
            ],
            "riskHints": ["注意东侧水库大坝稳定性"]
          }
        }
      },
      "metadata": {...}
    },
    {
      "action": "show_risk_warning",
      "payload": {"message": "注意东侧水库大坝稳定性"},
      "metadata": {...}
    }
  ]
}
```

#### 场景 3: 槽位缺失，需要补充信息

**请求**:
```json
{
  "user_id": "commander-001",
  "thread_id": "rescue-thread-002",
  "message": "生成救援方案",  // 缺少灾害类型、位置等信息
  "channel": "web"
}
```

**响应**:
```json
{
  "status": "needs_input",
  "intent": {"intent_type": "rescue-task-generation"},
  "result": {
    "response_text": "请补充以下关键信息：灾害类型、具体位置、被困人数。",
    "missing_fields": ["event_type", "location", "trapped_count"]
  },
  "ui_actions": []  // 空数组，因为还没生成方案
}
```

---

## 三、前端实现方案

### 3.1 核心组件清单

前端需要实现的 **5 个核心组件**（按优先级排序）：

#### 1. Action Dispatcher（最高优先级）

**文件**: `src/components/ActionDispatcher.ts`

**职责**: 消费 `/intent/process` 返回的 `ui_actions` 数组，分发到各个处理器

**实现示例**:
```typescript
import { message, Modal } from 'antd';
import mapboxgl from 'mapbox-gl';

interface UIAction {
  action: string;
  payload: Record<string, any>;
  metadata?: Record<string, any>;
}

export class ActionDispatcher {
  private map: mapboxgl.Map;

  constructor(map: mapboxgl.Map) {
    this.map = map;
  }

  dispatch(actions: UIAction[]) {
    actions.forEach(action => {
      switch(action.action) {
        case 'camera_flyto':
          this.handleCameraFlyTo(action.payload);
          break;
        case 'open_panel':
          this.handleOpenPanel(action.payload);
          break;
        case 'focus_entity':
          this.handleFocusEntity(action.payload);
          break;
        case 'show_toast':
          this.handleShowToast(action.payload);
          break;
        case 'show_risk_warning':
          this.handleShowRiskWarning(action.payload);
          break;
        default:
          console.warn('Unknown action type:', action.action);
      }
    });
  }

  private handleCameraFlyTo(payload: any) {
    this.map.flyTo({
      center: [payload.lng, payload.lat],
      zoom: payload.zoom || 15,
      duration: 2000
    });
  }

  private handleOpenPanel(payload: any) {
    // 触发 Redux action 或 Context 更新
    window.dispatchEvent(new CustomEvent('open-panel', { detail: payload }));
  }

  private handleShowToast(payload: any) {
    const duration = payload.duration_ms ? payload.duration_ms / 1000 : 3;

    if (payload.level === 'info') {
      message.info(payload.message, duration);
    } else if (payload.level === 'warning') {
      message.warning(payload.message, duration);
    } else {
      message.error(payload.message, duration);
    }
  }

  private async handleShowRiskWarning(payload: any) {
    // 显示警告弹窗
    Modal.warning({
      title: '风险警告',
      content: payload.message
    });

    // 高亮风险区域（如果有 risk_zones）
    if (payload.risk_zones) {
      for (const zoneId of payload.risk_zones) {
        await this.highlightRiskZone(zoneId);
      }
    }
  }

  private async highlightRiskZone(zoneId: string) {
    // 调用后端 API 获取区域几何数据
    const response = await fetch(`/api/risk-zones/${zoneId}`);
    const geoJson = await response.json();

    // 在地图上绘制红色多边形
    if (!this.map.getSource(zoneId)) {
      this.map.addSource(zoneId, {
        type: 'geojson',
        data: geoJson
      });

      this.map.addLayer({
        id: `${zoneId}-fill`,
        type: 'fill',
        source: zoneId,
        paint: {
          'fill-color': '#ff0000',
          'fill-opacity': 0.3
        }
      });

      this.map.addLayer({
        id: `${zoneId}-outline`,
        type: 'line',
        source: zoneId,
        paint: {
          'line-color': '#ff0000',
          'line-width': 2
        }
      });
    }
  }

  private handleFocusEntity(payload: any) {
    // Phase 2 实现
    console.log('Focus entity:', payload.entity_id);
  }
}
```

#### 2. 救援方案面板 (RescuePlanPanel)

**文件**: `src/components/RescuePlanPanel.tsx`

**实现示例**:
```tsx
import React from 'react';
import { Descriptions, List, Tag } from 'antd';

interface RescuePlan {
  tasks: Array<{
    task_id: string;
    description: string;
    priority: 'high' | 'medium' | 'low';
  }>;
  resources: Array<{
    resource_id: string;
    type: string;
    quantity: number;
  }>;
  routeWarnings: Array<{
    message: string;
    zoneId?: string;
  }>;
}

interface Props {
  plan: RescuePlan;
}

export const RescuePlanPanel: React.FC<Props> = ({ plan }) => {
  return (
    <div>
      <h3>救援任务</h3>
      <List
        dataSource={plan.tasks}
        renderItem={task => (
          <List.Item>
            <List.Item.Meta
              title={task.description}
              description={
                <Tag color={task.priority === 'high' ? 'red' : 'blue'}>
                  {task.priority}
                </Tag>
              }
            />
          </List.Item>
        )}
      />

      <h3>所需资源</h3>
      <Descriptions column={1}>
        {plan.resources.map(res => (
          <Descriptions.Item key={res.resource_id} label={res.type}>
            {res.quantity} 个
          </Descriptions.Item>
        ))}
      </Descriptions>

      {plan.routeWarnings.length > 0 && (
        <>
          <h3>路径警告</h3>
          <List
            dataSource={plan.routeWarnings}
            renderItem={warning => (
              <List.Item>
                <Tag color="red">{warning.message}</Tag>
              </List.Item>
            )}
          />
        </>
      )}
    </div>
  );
};
```

#### 3. 侦察方案面板 (ScoutPlanPanel)

**文件**: `src/components/ScoutPlanPanel.tsx`

**实现示例**:
```tsx
import React from 'react';
import { List, Tag } from 'antd';

interface ScoutPlan {
  targets: Array<{
    location: { lng: number; lat: number };
    priority: 'high' | 'medium' | 'low';
  }>;
  riskHints: string[];
}

interface Props {
  plan: ScoutPlan;
}

export const ScoutPlanPanel: React.FC<Props> = ({ plan }) => {
  return (
    <div>
      <h3>侦察目标</h3>
      <List
        dataSource={plan.targets}
        renderItem={(target, idx) => (
          <List.Item>
            <List.Item.Meta
              title={`目标 ${idx + 1}`}
              description={
                <>
                  <div>坐标: {target.location.lng.toFixed(4)}, {target.location.lat.toFixed(4)}</div>
                  <Tag color={target.priority === 'high' ? 'red' : 'blue'}>
                    {target.priority}
                  </Tag>
                </>
              }
            />
          </List.Item>
        )}
      />

      {plan.riskHints.length > 0 && (
        <>
          <h3>风险提示</h3>
          <List
            dataSource={plan.riskHints}
            renderItem={hint => (
              <List.Item>
                <Tag color="orange">{hint}</Tag>
              </List.Item>
            )}
          />
        </>
      )}
    </div>
  );
};
```

#### 4. 面板管理器 (PanelManager)

**文件**: `src/components/PanelManager.tsx`

**实现示例**:
```tsx
import React, { useState, useEffect } from 'react';
import { Drawer } from 'antd';
import { RescuePlanPanel } from './RescuePlanPanel';
import { ScoutPlanPanel } from './ScoutPlanPanel';

export const PanelManager: React.FC = () => {
  const [visible, setVisible] = useState(false);
  const [panelType, setPanelType] = useState<'rescue_plan' | 'scout_plan' | null>(null);
  const [planData, setPlanData] = useState<any>(null);

  useEffect(() => {
    // 监听 open-panel 事件
    const handleOpenPanel = (event: CustomEvent) => {
      const { panel, params } = event.detail;
      setPanelType(panel);
      setPlanData(params.plan);
      setVisible(true);
    };

    window.addEventListener('open-panel', handleOpenPanel as EventListener);
    return () => window.removeEventListener('open-panel', handleOpenPanel as EventListener);
  }, []);

  return (
    <Drawer
      title={panelType === 'rescue_plan' ? '救援方案' : '侦察方案'}
      visible={visible}
      onClose={() => setVisible(false)}
      width={400}
    >
      {panelType === 'rescue_plan' && <RescuePlanPanel plan={planData} />}
      {panelType === 'scout_plan' && <ScoutPlanPanel plan={planData} />}
    </Drawer>
  );
};
```

#### 5. 意图处理 API 客户端

**文件**: `src/services/intentApi.ts`

**实现示例**:
```typescript
import { ActionDispatcher } from '@/components/ActionDispatcher';

interface IntentRequest {
  user_id: string;
  thread_id: string;
  message: string;
  incident_id?: string;
  channel?: 'web' | 'voice' | 'mobile';
}

interface IntentResponse {
  status: 'success' | 'needs_input' | 'unknown' | 'error';
  intent: any;
  result: any;
  ui_actions: any[];
  history: any[];
  memory_hits: any[];
  audit_log: any[];
}

export class IntentAPI {
  private baseUrl: string;
  private dispatcher: ActionDispatcher;

  constructor(baseUrl: string, dispatcher: ActionDispatcher) {
    this.baseUrl = baseUrl;
    this.dispatcher = dispatcher;
  }

  async processIntent(req: IntentRequest): Promise<IntentResponse> {
    const response = await fetch(`${this.baseUrl}/intent/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ...req,
        channel: req.channel || 'web'
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data: IntentResponse = await response.json();

    // 自动分发 UI Actions
    if (data.ui_actions && data.ui_actions.length > 0) {
      this.dispatcher.dispatch(data.ui_actions);
    }

    return data;
  }
}
```

### 3.2 集成示例

**主页面组件** (`src/pages/CommandCenter.tsx`):

```tsx
import React, { useEffect, useState } from 'react';
import { Input, Button, message } from 'antd';
import mapboxgl from 'mapbox-gl';
import { ActionDispatcher } from '@/components/ActionDispatcher';
import { PanelManager } from '@/components/PanelManager';
import { IntentAPI } from '@/services/intentApi';

export const CommandCenter: React.FC = () => {
  const [map, setMap] = useState<mapboxgl.Map | null>(null);
  const [intentAPI, setIntentAPI] = useState<IntentAPI | null>(null);
  const [userInput, setUserInput] = useState('');
  const [loading, setLoading] = useState(false);

  // 初始化地图和 API 客户端
  useEffect(() => {
    const mapInstance = new mapboxgl.Map({
      container: 'map',
      style: 'mapbox://styles/mapbox/streets-v11',
      center: [121.5, 31.2],
      zoom: 12
    });

    setMap(mapInstance);

    const dispatcher = new ActionDispatcher(mapInstance);
    const api = new IntentAPI('http://localhost:8008', dispatcher);
    setIntentAPI(api);

    return () => mapInstance.remove();
  }, []);

  // 处理用户输入
  const handleSubmit = async () => {
    if (!userInput.trim() || !intentAPI) return;

    setLoading(true);
    try {
      const response = await intentAPI.processIntent({
        user_id: 'commander-001',
        thread_id: `thread-${Date.now()}`,
        message: userInput,
        incident_id: 'fef8469f-5f78-4dd4-8825-dbc915d1b630'
      });

      if (response.status === 'needs_input') {
        message.info(response.result.response_text);
      } else if (response.status === 'success') {
        message.success('处理完成');
      }

      setUserInput('');
    } catch (error) {
      message.error('处理失败：' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 地图容器 */}
      <div id="map" style={{ flex: 1 }} />

      {/* 面板管理器 */}
      <PanelManager />

      {/* 底部输入框 */}
      <div style={{ padding: 16, background: '#fff', borderTop: '1px solid #d9d9d9' }}>
        <Input.Search
          placeholder="输入指令，如：生成救援方案、派无人机侦察"
          value={userInput}
          onChange={e => setUserInput(e.target.value)}
          onSearch={handleSubmit}
          loading={loading}
          enterButton="发送"
        />
      </div>
    </div>
  );
};
```

---

## 四、Java 中间件集成方案

### 4.1 职责定义

Java 中间件（emergency-web-api）需要实现 **2 个核心功能**：

1. **转发意图处理请求**（HTTP 代理）
2. **权限校验和审计日志**

### 4.2 实现示例

**Controller** (`IntentController.java`):

```java
package com.cykj.emergency.controller;

import com.cykj.emergency.dto.IntentProcessRequest;
import com.cykj.emergency.dto.IntentProcessResponse;
import com.cykj.emergency.service.AuditLogService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

@Slf4j
@RestController
@RequestMapping("/web-api/intent")
@RequiredArgsConstructor
public class IntentController {

    private final WebClient.Builder webClientBuilder;
    private final AuditLogService auditLogService;

    @Value("${ai-brain.base-url}")
    private String aiBrainBaseUrl;

    @PostMapping("/process")
    public ResponseEntity<IntentProcessResponse> processIntent(@RequestBody IntentProcessRequest request) {
        log.info("收到意图处理请求: userId={}, threadId={}, message={}",
            request.getUserId(), request.getThreadId(), request.getMessage());

        // 1. 权限校验（示例：检查用户是否有权限操作该 incident）
        validateUserPermission(request.getUserId(), request.getIncidentId());

        // 2. 转发到 Python AI 大脑
        WebClient webClient = webClientBuilder.baseUrl(aiBrainBaseUrl).build();

        IntentProcessResponse aiResponse = webClient.post()
            .uri("/intent/process")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(IntentProcessResponse.class)
            .timeout(Duration.ofSeconds(60))  // 60 秒超时
            .block();

        // 3. 记录审计日志到业务数据库
        if (aiResponse != null && aiResponse.getIntent() != null) {
            auditLogService.save(
                request.getUserId(),
                request.getThreadId(),
                aiResponse.getIntent().getIntentType(),
                aiResponse.getStatus()
            );
        }

        // 4. 原样返回 AI 响应（包含 ui_actions）
        return ResponseEntity.ok(aiResponse);
    }

    private void validateUserPermission(String userId, String incidentId) {
        // TODO: 实现权限校验逻辑
        // 如果无权限，抛出 ForbiddenException
    }
}
```

**配置文件** (`application.yml`):

```yaml
ai-brain:
  base-url: http://localhost:8008  # Python AI 大脑地址
  timeout: 60000  # 60 秒

spring:
  webflux:
    webclient:
      max-connections: 100
      connection-timeout: 60000
```

**DTO** (`IntentProcessRequest.java`):

```java
package com.cykj.emergency.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class IntentProcessRequest {
    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("thread_id")
    private String threadId;

    private String message;

    @JsonProperty("incident_id")
    private String incidentId;

    private String channel = "web";
}
```

**DTO** (`IntentProcessResponse.java`):

```java
package com.cykj.emergency.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class IntentProcessResponse {
    private String status;
    private Map<String, Object> intent;
    private Map<String, Object> result;

    @JsonProperty("ui_actions")
    private List<Map<String, Object>> uiActions;  // ⭐ 核心字段，直接透传

    private List<Map<String, Object>> history;

    @JsonProperty("memory_hits")
    private List<Map<String, Object>> memoryHits;

    @JsonProperty("audit_log")
    private List<Map<String, Object>> auditLog;
}
```

### 4.3 关键配置

**依赖** (`pom.xml`):

```xml
<dependencies>
    <!-- Spring WebFlux (用于 WebClient) -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-webflux</artifactId>
    </dependency>

    <!-- Resilience4j (熔断器，可选) -->
    <dependency>
        <groupId>io.github.resilience4j</groupId>
        <artifactId>resilience4j-spring-boot2</artifactId>
        <version>1.7.1</version>
    </dependency>
</dependencies>
```

### 4.4 Java 中间件不需要做的事

- ❌ 解析或修改 `ui_actions` 内容
- ❌ 实现 Action 调度逻辑（这是前端职责）
- ❌ 存储 `ui_actions` 到数据库（AI 大脑已有 audit_log）
- ❌ 实现业务逻辑（救援规划、风险预测等都在 Python）

---

## 五、集成测试方案

### 5.1 前端独立测试（无需等待 Java 中间件）

#### Step 1: 启动 Python AI 大脑

```bash
cd /home/msq/gitCode/new_1/emergency-agents-langgraph
source .venv/bin/activate
./scripts/dev-run.sh

# 验证服务启动
curl http://localhost:8008/healthz
# 预期输出: {"status":"ok"}
```

#### Step 2: 测试战术救援 UI Actions

```bash
curl -X POST http://localhost:8008/intent/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "thread_id": "test-rescue-'$(date +%s)'",
    "message": "某化工厂发生火灾，3人被困，需要救援方案",
    "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
    "channel": "web"
  }' | jq '.ui_actions'
```

**预期输出**（验证 5 个 Actions）:

```json
[
  {
    "action": "camera_flyto",
    "payload": {"lng": 121.5, "lat": 31.2, "zoom": 15}
  },
  {
    "action": "open_panel",
    "payload": {"panel": "rescue_plan", "params": {...}}
  },
  {
    "action": "show_toast",
    "payload": {"level": "info", "message": "已生成救援方案..."}
  },
  {
    "action": "show_toast",
    "payload": {"level": "warning", "duration_ms": 8000, "message": "附近存在..."}
  },
  {
    "action": "show_risk_warning",
    "payload": {"message": "路径途经高温区域...", "risk_zones": [...]}
  }
]
```

#### Step 3: 测试战术侦察 UI Actions

```bash
curl -X POST http://localhost:8008/intent/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "thread_id": "test-scout-'$(date +%s)'",
    "message": "派无人机侦察受灾区域",
    "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
    "channel": "web"
  }' | jq '.ui_actions'
```

**预期输出**（验证 3 个 Actions）:

```json
[
  {
    "action": "camera_flyto",
    "payload": {"lng": 121.48, "lat": 31.25, "zoom": 16}
  },
  {
    "action": "open_panel",
    "payload": {"panel": "scout_plan", "params": {...}}
  },
  {
    "action": "show_risk_warning",
    "payload": {"message": "注意东侧水库大坝稳定性"}
  }
]
```

### 5.2 前端 Action Dispatcher 验证

**测试脚本** (`test-ui-actions.html`):

```html
<!DOCTYPE html>
<html>
<head>
  <title>UI Actions Test</title>
  <style>
    body { font-family: monospace; padding: 20px; }
    .log { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>UI Actions 测试</h1>
  <button onclick="testRescue()">测试救援方案</button>
  <button onclick="testScout()">测试侦察方案</button>
  <div id="log"></div>

  <script>
  async function testRescue() {
    await testUIActions('某化工厂发生火灾，3人被困，需要救援方案');
  }

  async function testScout() {
    await testUIActions('派无人机侦察受灾区域');
  }

  async function testUIActions(message) {
    const log = document.getElementById('log');
    log.innerHTML = '';

    try {
      const resp = await fetch('http://localhost:8008/intent/process', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          user_id: 'test-user',
          thread_id: 'test-' + Date.now(),
          message: message,
          incident_id: 'fef8469f-5f78-4dd4-8825-dbc915d1b630',
          channel: 'web'
        })
      });

      const data = await resp.json();

      log.innerHTML += `<div class="log"><strong>Status:</strong> ${data.status}</div>`;
      log.innerHTML += `<div class="log"><strong>Intent:</strong> ${data.intent.intent_type}</div>`;
      log.innerHTML += `<div class="log"><strong>UI Actions (${data.ui_actions.length}):</strong></div>`;

      data.ui_actions.forEach((action, idx) => {
        log.innerHTML += `<div class="log">
          <strong>${idx + 1}. ${action.action}</strong><br>
          Payload: <pre>${JSON.stringify(action.payload, null, 2)}</pre>
        </div>`;
      });

    } catch (error) {
      log.innerHTML += `<div class="log" style="color: red;"><strong>Error:</strong> ${error.message}</div>`;
    }
  }
  </script>
</body>
</html>
```

**使用方法**:

1. 保存为 `test-ui-actions.html`
2. 在浏览器中打开（需要启动 Python AI 大脑服务）
3. 点击按钮测试，查看 UI Actions 输出

### 5.3 验证清单

前端团队需要验证的 **5 个核心点**：

- [x] `ui_actions` 数组存在且非空
- [x] 每个 Action 包含 `action`, `payload`, `metadata` 三个字段
- [x] `camera_flyto` 的 payload 包含 lng, lat（数字类型）
- [x] `open_panel` 的 payload 包含 panel（字符串）和 params（对象）
- [x] `show_risk_warning` 的 payload 包含 message（字符串）

### 5.4 常见问题排查

| 问题 | 可能原因 | 排查方法 |
|------|---------|---------|
| `ui_actions` 为空 | message 未触发正确意图 | 检查 `intent.intent_type` 是否为 rescue/scout |
| 缺少某个 Action | Handler 逻辑问题 | 查看后端日志 `ui_actions_emitted` 事件 |
| payload 格式错误 | 序列化问题 | 检查 `serialize_actions()` 逻辑 |
| 风险区域不显示 | 缺少区域几何数据 | 实现 `/api/risk-zones/{zone_id}` 端点 |
| 超时错误 | LangGraph 执行慢 | 检查 PostgreSQL/Neo4j/Qdrant 连接 |

---

## 六、最快速实施路径（3 天 MVP 方案）

### 目标
3 天内实现最小可用集成，每天都有可演示的进展。

### Day 1（前端）: Action Dispatcher + 基础 UI

**上午 4h**:
- [ ] 创建 `ActionDispatcher.ts`（switch-case 路由）
- [ ] 实现 `camera_flyto` → 调用地图 API（Mapbox/Cesium）
- [ ] 实现 `show_toast` → Ant Design Message 组件

**下午 4h**:
- [ ] 实现 `open_panel` → 侧边栏 Drawer 组件
- [ ] 创建 `RescuePlanPanel.tsx`（渲染 plan.tasks）
- [ ] 创建 `ScoutPlanPanel.tsx`（渲染 plan.targets）

**验收标准**:
- ✅ 调用 `/intent/process` 能看到相机飞行
- ✅ 能看到 Toast 提示
- ✅ 能看到救援/侦察方案面板打开

---

### Day 2（前端 + Python）: 风险警告可视化

**上午 4h（前端）**:
- [ ] 实现 `show_risk_warning` → 地图上绘制红色多边形
- [ ] 调用 `/api/risk-zones/{zone_id}` 获取几何数据（先 mock）

**下午 4h（Python）**:
- [ ] 创建 `GET /api/risk-zones/{zone_id}` 端点
- [ ] 从 RiskCacheManager 返回 GeoJSON 格式数据
- [ ] 验证风险区域高亮显示

**验收标准**:
- ✅ 救援方案生成时，地图上能看到风险区域红色覆盖
- ✅ 鼠标悬停显示风险类型（高温区、有毒气体等）

---

### Day 3（Java 中间件 + 联调）: 业务集成

**上午 4h（Java）**:
- [ ] 实现 `/web-api/intent/process` 转发接口
- [ ] 添加权限校验逻辑
- [ ] 记录审计日志到业务数据库

**下午 4h（联调）**:
- [ ] 前端改为调用 Java 中间件（而非直接调 Python）
- [ ] 验证完整流程：前端 → Java → Python → 返回 → 前端渲染
- [ ] 压测：并发 10 个请求验证性能

**验收标准**:
- ✅ 用户通过前端发起救援/侦察请求，全链路可用
- ✅ 业务数据库中能看到审计日志
- ✅ 响应时间 < 5 秒（含 LangGraph 执行）

---

### 暂不实现的功能（Phase 2）

- ❌ `focus_entity`（实体数据不完整）
- ❌ WebSocket 实时推送（先用轮询）
- ❌ 战略层图（战术层验证后再扩展）

---

## 七、技术风险控制

### 风险 1: LangGraph 执行超时

**风险描述**: 救援/侦察任务生成可能需要 10-30 秒，用户体验差

**缓解措施**:
1. **Java 层**:
   - 设置 60 秒超时（`Duration.ofSeconds(60)`）
   - 添加熔断器（Resilience4j）
   - 超时后返回"AI 处理中，请稍候"

2. **前端层**:
   - 显示加载动画（Ant Design Spin）
   - 提示用户"正在生成方案，请稍候..."
   - 允许用户取消请求

3. **Python 层**:
   - 使用 Prometheus 监控 LangGraph 执行时间
   - 优化慢查询（Neo4j、Qdrant）

---

### 风险 2: 风险区域数据缺失

**风险描述**: `/api/risk-zones/{zone_id}` 可能返回空数据

**缓解措施**:
1. **前端 Fallback**:
   - 如果 API 返回 404，只显示文本警告，不绘制多边形
   - Toast 提示："暂无该区域的详细数据"

2. **Python 层**:
   - RiskCacheManager 提供默认几何数据（圆形区域）
   - 记录缺失数据日志，便于后续补全

---

### 风险 3: 并发压力

**风险描述**: 多用户同时发起救援请求，后端性能下降

**缓解措施**:
1. **限流**:
   - Java 层添加限流器（Resilience4j RateLimiter）
   - 每用户最多 5 次/分钟

2. **监控**:
   - Prometheus 监控请求 QPS、延迟、错误率
   - Grafana 可视化仪表盘

3. **扩容方案**:
   - Python 服务可水平扩展（多实例 + Nginx 负载均衡）
   - PostgreSQL 主从复制

---

## 八、成功验收指标（1 周后检查）

### 功能指标
- ✅ 前端能实时看到救援/侦察方案
- ✅ 地图相机能自动飞行到事发地点
- ✅ 风险区域能在地图上高亮显示
- ✅ 所有操作有审计日志可追溯

### 性能指标
- ✅ 响应时间 < 5 秒（P95）
- ✅ 错误率 < 1%
- ✅ 并发支持 10 用户（无明显卡顿）

### 用户体验指标
- ✅ 无需手动刷新页面
- ✅ Toast 提示及时准确
- ✅ 面板信息清晰易读

---

## 九、附录

### 附录 A: 代码验证清单

**已验证的文件**（基于 10 层深度分析）:

1. `src/emergency_agents/ui/actions.py` (216 行) - UI Actions 协议定义（含标准动作 + `toggle_layer` / `raw_action`）
2. `src/emergency_agents/intent/handlers/rescue_task_generation.py:792-843` - Rescue UI Actions 生成
3. `src/emergency_agents/intent/handlers/scout_task_generation.py:115-129` - Scout UI Actions 生成
4. `src/emergency_agents/api/intent_processor.py:513-559` - UI Actions 提取和序列化
5. `src/emergency_agents/api/main.py:783` - `/intent/process` 端点定义
6. `src/emergency_agents/graph/scout_tactical_app.py` (1479 行，8 节点) - 侦察战术图
7. `src/emergency_agents/graph/scout_tactical_app.py:1320-1374` - 侦察子图扩展动作（`preview_route` / `open_scout_panel` / `show_risk_hints`）

### 附录 B: 相关文档

- **项目启动指导**: `/docs/新业务逻辑md/new_0.1/项目启动指导.md`
- **PyTorch 问题诊断**: `/docs/新业务逻辑md/new_0.1/PyTorch-Bus-Error问题诊断.md`
- **QUICK-START.md**: 项目快速开始指南
- **AGENTS.md**: 开发协议和规则

### 附录 C: 关键联系人

| 角色 | 职责 | 联系方式 |
|------|------|---------|
| Python 后端 | AI 大脑维护 | msq |
| 前端团队 | UI 组件实现 | （待补充） |
| Java 后台 | 中间件集成 | （待补充） |

---

## 十、总结

### 核心发现
1. **✅ 战术链路可执行**：战术救援 / 侦察图已在 StateGraph 上线，可产出 UI 动作。
2. **📌 UI Actions 含扩展动作**：需同步消费标准 + 扩展动作（含侦察子图专属）以避免信息缺失。
3. **⚠️ 风险缓存仅覆盖救援链路**：侦察链路仍直接访问 `RiskDataRepository`，缓存命中率依赖后端补齐。
4. **🎯 前端仍为瓶颈**：缺少 Dispatcher 与组件，当前动作只能落在日志中。
5. **❌ 战略层不存在**：目前范围仅限战术层功能。

### 最快实施路径
采用 **3 天 MVP 方案**，渐进式集成：
- **Day 1**: 通最小链路（相机、Toast、面板）
- **Day 2**: 风险可视化
- **Day 3**: 业务集成 + 联调

### 技术风险
主要风险为 LangGraph 超时、风险数据缺失、并发压力，均有对应缓解措施。

### 成功指标
1 周后需验证：功能完整性、性能达标（< 5 秒）、用户体验流畅。

---

**文档版本**: v1.0
**创建日期**: 2025-11-02
**维护者**: Claude Code (基于 10 层 Linus 式代码验证)
**状态**: ✅ 就绪，等待前端实现
