# Design: UI Actions 协议架构设计

## 设计目标

1. **最小化前端集成成本**：提供开箱即用的协议和代码示例
2. **保持协议向后兼容**：支持未来扩展新动作类型
3. **确保类型安全**：使用 TypeScript 类型定义，避免运行时错误
4. **支持多前端框架**：协议与 React/Vue/Angular 解耦

---

## 系统架构

### 数据流

```
用户输入
    ↓
[emergency-rescue-brain 前端]
    ↓ HTTP POST
[emergency-web-api Java 中间件]
    ↓ HTTP POST /intent/process
[emergency-agents-langgraph Python 后端]
    ├─ IntentOrchestrator (意图编排)
    ├─ RescueTacticalGraph (救援状态机)
    ├─ ScoutTacticalGraph (侦察状态机)
    └─ UI Actions 生成
    ↓ JSON Response
{
  "status": "success",
  "intent": {...},
  "result": {...},
  "ui_actions": [  ← 核心字段
    {"action": "camera_flyto", "payload": {...}},
    {"action": "open_panel", "payload": {...}},
    ...
  ]
}
    ↓
[Java 中间件透传]
    ↓
[前端 ActionDispatcher]
    ├─ 解析 ui_actions 数组
    ├─ 路由到对应 handler
    └─ 执行地图/UI 操作
```

---

## 核心组件设计

### 1. ActionDispatcher（前端核心类）

#### 职责
- 解析 `ui_actions` 数组
- 路由到对应的 handler 方法
- 处理未知动作类型（降级策略）
- 提供日志追踪（console.log）

#### 类图
```typescript
class ActionDispatcher {
  private map: mapboxgl.Map;
  private messageApi: MessageInstance;  // Ant Design message API

  constructor(map: mapboxgl.Map, messageApi: MessageInstance);

  // 核心方法
  dispatch(actions: UIAction[]): void;

  // Handler 方法
  private handleCameraFlyTo(payload: CameraFlyToPayload): void;
  private handleOpenPanel(payload: OpenPanelPayload): void;
  private handleShowToast(payload: ShowToastPayload): void;
  private handleShowRiskWarning(payload: ShowRiskWarningPayload): Promise<void>;
  private handleFocusEntity(payload: FocusEntityPayload): void;

  // 工具方法
  private blinkMarker(entityId: string): void;  // 实体图标闪烁
  private highlightRiskZone(zoneId: string): Promise<void>;  // 地图高亮
}
```

#### 实现示例
```typescript
export class ActionDispatcher {
  private map: mapboxgl.Map;
  private messageApi: MessageInstance;

  constructor(map: mapboxgl.Map, messageApi: MessageInstance) {
    this.map = map;
    this.messageApi = messageApi;
  }

  dispatch(actions: UIAction[]) {
    console.log('[ActionDispatcher] 收到动作队列:', actions);

    actions.forEach((action, index) => {
      console.log(`[ActionDispatcher] 执行动作 ${index + 1}/${actions.length}:`, action.action);

      switch(action.action) {
        case 'camera_flyto':
          this.handleCameraFlyTo(action.payload as CameraFlyToPayload);
          break;
        case 'open_panel':
          this.handleOpenPanel(action.payload as OpenPanelPayload);
          break;
        case 'show_toast':
          this.handleShowToast(action.payload as ShowToastPayload);
          break;
        case 'show_risk_warning':
          this.handleShowRiskWarning(action.payload as ShowRiskWarningPayload);
          break;
        case 'focus_entity':
          this.handleFocusEntity(action.payload as FocusEntityPayload);
          break;
        default:
          console.warn('[ActionDispatcher] 未知动作类型:', action.action);
      }
    });
  }

  private handleCameraFlyTo(payload: CameraFlyToPayload) {
    this.map.flyTo({
      center: [payload.lng, payload.lat],
      zoom: payload.zoom || 15,
      duration: 2000
    });
    console.log('[ActionDispatcher] 相机飞行到:', payload.lng, payload.lat);
  }

  private handleShowToast(payload: ShowToastPayload) {
    const duration = payload.duration_ms ? payload.duration_ms / 1000 : 3;

    switch(payload.level) {
      case 'info':
        this.messageApi.info(payload.message, duration);
        break;
      case 'warning':
        this.messageApi.warning(payload.message, duration);
        break;
      case 'error':
        this.messageApi.error(payload.message, duration);
        break;
    }
    console.log('[ActionDispatcher] 显示提示:', payload.message);
  }

  // ... 其他 handler 实现
}
```

---

### 2. UI Actions 协议（Python 后端）

#### 协议定义位置
`src/emergency_agents/ui/actions.py`

#### 核心数据结构
```python
@dataclass(slots=True)
class UIAction:
    action: str                              # Action 类型
    payload: Any                             # Action 负载
    metadata: Optional[Mapping[str, Any]]    # 元数据
```

#### 序列化流程
```python
def serialize_actions(actions: list[UIAction]) -> list[dict[str, Any]]:
    """
    将 UIAction 对象列表序列化为 JSON 可序列化的字典列表
    """
    result = []
    for action in actions:
        serialized = {
            "action": action.action,
            "payload": _serialize_payload(action.payload),
        }
        if action.metadata:
            serialized["metadata"] = dict(action.metadata)
        result.append(serialized)
    return result
```

---

## 技术决策记录

### Decision 1：为什么使用 Action 队列而非单个 Action

**背景**：
- 救援场景可能需要多个 UI 操作（飞行 + 打开面板 + 显示提示 + 高亮风险区域）
- 单个 Action 会导致多次 API 调用

**决策**：
- 使用 `ui_actions: UIAction[]` 数组
- Python 后端一次性返回所有动作
- 前端顺序执行（简化实现）

**优势**：
- ✅ 减少网络往返
- ✅ 保证动作执行顺序
- ✅ 易于调试（一次性看到所有动作）

**劣势**：
- ⚠️ 前端需要处理数组
- ⚠️ 无法中断执行（未来可扩展）

---

### Decision 2：为什么使用字符串类型的 action 而非枚举

**背景**：
- TypeScript 可以使用 `enum` 或 `union type`
- Python 可以使用 `Literal` 或 `Enum`

**决策**：
- 使用字符串 `action: str`
- 前端使用 `switch-case` 匹配

**优势**：
- ✅ 易于扩展（新增动作类型无需修改协议）
- ✅ 前端可以优雅降级（未知类型 → console.warn）
- ✅ 支持 `raw_action` 类型（兜底）

**劣势**：
- ⚠️ 无编译时类型检查（拼写错误）
- **缓解**：提供 TypeScript 类型定义，使用 `as` 断言

---

### Decision 3：为什么选择 Mapbox GL 而非 Leaflet/OpenLayers

**背景**：
- 前端已使用 Mapbox GL JS 作为地图引擎

**决策**：
- ActionDispatcher 示例代码使用 Mapbox GL API
- 协议本身与地图引擎无关

**优势**：
- ✅ 复用现有基建
- ✅ 代码示例可直接运行

**劣势**：
- ⚠️ 如果前端切换地图引擎，需要修改 handler 实现
- **缓解**：协议层不绑定具体实现

---

### Decision 4：为什么使用 Ant Design Message 而非自定义 Toast

**背景**：
- 前端已使用 Ant Design 组件库

**决策**：
- ActionDispatcher 示例代码使用 `message.info/warning/error`
- 协议本身不依赖 Ant Design

**优势**：
- ✅ 复用现有组件
- ✅ 减少开发工作量

**劣势**：
- ⚠️ 如果前端不使用 Ant Design，需要自行实现
- **缓解**：协议层不绑定具体实现

---

## 扩展性设计

### 支持新增动作类型

**场景**：未来需要支持 `export_report` 动作（导出 PDF 报告）

**实现步骤**：
1. **Python 后端**：在 `actions.py` 新增 `export_report()` 工厂函数
2. **前端**：在 `ActionDispatcher` 新增 `handleExportReport()` 方法
3. **文档**：更新协议规范文档

**无需修改**：
- ✅ `UIAction` 数据结构
- ✅ `serialize_actions()` 序列化逻辑
- ✅ Java 中间件透传逻辑

---

### 支持动作撤销/重做（未来）

**设计思路**：
- 在 `UIAction` 中新增 `undo_action: str` 字段
- 前端维护动作历史栈
- 用户点击"撤销"时执行 `undo_action`

**示例**：
```python
camera_fly_to(
    lng=121.5, lat=31.2,
    metadata={"undo_action": "camera_flyto", "undo_payload": {"lng": 120.0, "lat": 30.0}}
)
```

---

## 错误处理策略

### 前端错误处理

| 错误类型 | 处理策略 | 用户体验 |
|---------|---------|---------|
| **未知动作类型** | `console.warn()` 记录，跳过执行 | 不影响其他动作 |
| **Payload 格式错误** | `console.error()` 记录，Toast 提示 | 显示错误提示 |
| **地图 API 调用失败** | `try-catch` 捕获，Toast 提示 | 显示错误提示 |
| **后端 API 超时** | 显示 Loading，3 秒后 Toast 提示 | 显示超时提示 |
| **网络断开** | 检测 `navigator.onLine`，禁用输入 | 显示离线提示 |

### Python 后端错误处理

| 错误类型 | 处理策略 | 返回数据 |
|---------|---------|---------|
| **动作生成失败** | 记录日志，返回空数组 | `ui_actions: []` |
| **序列化失败** | 记录日志，返回空数组 | `ui_actions: []` |
| **LLM 调用失败** | 降级到规则引擎 | 生成默认动作 |

---

## 性能优化

### 前端优化

1. **批量执行动作**
   - 当前：顺序执行（`forEach`）
   - 优化：并行执行（`Promise.all`）
   - 适用场景：多个独立动作（camera_flyto + show_toast）

2. **地图渲染优化**
   - 当前：每次调用 `map.addLayer()`
   - 优化：批量添加图层（`map.getStyle()` + 批量修改）
   - 适用场景：高亮多个风险区域

3. **防抖/节流**
   - 当前：每次响应都执行动作
   - 优化：对频繁触发的动作（camera_flyto）进行节流
   - 适用场景：用户快速输入多次

---

## 安全考虑

### XSS 防护
- **问题**：`show_toast` 的 `message` 字段可能包含恶意脚本
- **缓解**：Ant Design `message` API 默认转义 HTML
- **建议**：前端使用 DOMPurify 额外清洗

### CSRF 防护
- **问题**：恶意网站伪造 `/intent/process` 请求
- **缓解**：Java 中间件验证 CSRF Token
- **建议**：使用 SameSite Cookie

---

## 测试策略

### 单元测试（Python）
```python
def test_serialize_camera_flyto():
    action = camera_fly_to(lng=121.5, lat=31.2, zoom=15)
    serialized = serialize_actions([action])
    assert serialized[0]["action"] == "camera_flyto"
    assert serialized[0]["payload"]["lng"] == 121.5
```

### 集成测试（Python + FastAPI）
```python
async def test_intent_process_returns_ui_actions():
    response = await client.post("/intent/process", json={
        "user_id": "test-user",
        "thread_id": "test-thread",
        "message": "生成救援方案",
        "channel": "web"
    })
    assert "ui_actions" in response.json()
    assert len(response.json()["ui_actions"]) > 0
```

### 前端单元测试（Jest + React Testing Library）
```typescript
test('ActionDispatcher dispatches camera_flyto', () => {
  const mockMap = { flyTo: jest.fn() };
  const dispatcher = new ActionDispatcher(mockMap as any, messageApi);

  dispatcher.dispatch([{
    action: 'camera_flyto',
    payload: { lng: 121.5, lat: 31.2, zoom: 15 }
  }]);

  expect(mockMap.flyTo).toHaveBeenCalledWith({
    center: [121.5, 31.2],
    zoom: 15,
    duration: 2000
  });
});
```

### 端到端测试（Cypress / Playwright）
```typescript
test('full rescue flow', async () => {
  await page.goto('http://localhost:3000');
  await page.fill('input[name="message"]', '生成救援方案');
  await page.click('button[type="submit"]');

  // 验证地图飞行
  await page.waitForSelector('.mapboxgl-canvas');
  // 验证侧边栏打开
  await page.waitForSelector('.ant-drawer');
  // 验证 Toast 提示
  await page.waitForSelector('.ant-message');
});
```

---

## 参考实现

### 完整的 ActionDispatcher 示例
参见：`design.md` 第 1 节

### 完整的 Python 协议示例
参见：`src/emergency_agents/ui/actions.py`

### 完整的 API 响应示例
参见：`specs/ui-actions-api/spec.md` 中的 Scenarios
