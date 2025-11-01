# Spec: UI Actions 前端交互能力

## ADDED Requirements

### Requirement: fly_to 地图跳转动作

当侦察任务生成后，前端MUST自动跳转地图视角到目标区域。
当侦察任务生成后，前端必须自动跳转地图视角到目标区域。

#### Scenario: 基础场景
当侦察任务生成后，前端必须自动跳转地图视角到目标区域。

- **GIVEN**:
- 侦察任务的第一个航点坐标为 (31.2, 121.5)

- **WHEN**:
- 生成 UI Actions

- **THEN**:
- 返回 `fly_to` 动作:
  ```json
  {
    "type": "fly_to",
    "params": {
      "lat": 31.2,
      "lon": 121.5,
      "zoom": 15,
      "pitch": 45,
      "duration": 2000
    }
  }
  ```

- **Acceptance Criteria**:
- [ ] `type` 字段为 "fly_to"
- [ ] `params` 包含 5 个字段: lat, lon, zoom, pitch, duration
- [ ] 坐标为第一个航点或目标中心点
- [ ] 默认缩放级别 15（显示街区级别）
- [ ] 俯仰角 45 度（3D 视角）
- [ ] 动画时长 2 秒

---

### Requirement: open_scout_panel 面板打开动作

当侦察任务生成后，前端MUST打开侦察任务详情面板。
当侦察任务生成后，前端必须打开侦察任务详情面板。

#### Scenario: 基础场景
当侦察任务生成后，前端必须打开侦察任务详情面板。

- **GIVEN**:
- 侦察任务 ID 为 "SCOUT-20251102-ABC123"

- **WHEN**:
- 生成 UI Actions

- **THEN**:
- 返回 `open_scout_panel` 动作:
  ```json
  {
    "type": "open_scout_panel",
    "params": {
      "task_id": "SCOUT-20251102-ABC123",
      "panel_position": "right"
    }
  }
  ```

- **Acceptance Criteria**:
- [ ] `type` 字段为 "open_scout_panel"
- [ ] `params` 包含 2 个字段: task_id, panel_position
- [ ] `task_id` 为侦察任务的数据库 ID
- [ ] `panel_position` 默认为 "right"（右侧面板）

---

### Requirement: preview_route 航线预览动作

当航线规划完成后，前端MUST在地图上预览航线路径。
当航线规划完成后，前端必须在地图上预览航线路径。

#### Scenario: 基础场景
当航线规划完成后，前端必须在地图上预览航线路径。

- **GIVEN**:
- 航线包含 12 个航点

- **WHEN**:
- 生成 UI Actions

- **THEN**:
- 返回 `preview_route` 动作:
  ```json
  {
    "type": "preview_route",
    "params": {
      "waypoints": [
        {"lat": 31.2, "lon": 121.5, "alt": 80},
        {"lat": 31.201, "lon": 121.5, "alt": 80},
        ...
      ],
      "color": "#FF6B00",
      "animation": "flow"
    }
  }
  ```

- **Acceptance Criteria**:
- [ ] `type` 字段为 "preview_route"
- [ ] `params` 包含 3 个字段: waypoints, color, animation
- [ ] `waypoints` 为完整的航点列表
- [ ] `color` 默认为橙色 "#FF6B00"（区别于救援路线的蓝色）
- [ ] `animation` 为 "flow"（流动效果）或 "static"（静态线条）

---

### Requirement: UI Actions 生成函数

系统MUST必须提供统一的函数生成所有 UI Actions。
系统必须提供统一的函数生成所有 UI Actions。

#### Scenario: 基础场景
系统必须提供统一的函数生成所有 UI Actions。

- **GIVEN**:
- State 中包含航点、任务 ID

- **WHEN**:
- `prepare_response` 节点调用 `_generate_ui_actions(state)`

- **THEN**:
- 返回包含 3 个动作的列表:
  ```python
  [
    {"type": "fly_to", "params": {...}},
    {"type": "open_scout_panel", "params": {...}},
    {"type": "preview_route", "params": {...}}
  ]
  ```

- **Acceptance Criteria**:
- [ ] 实现 `_generate_ui_actions(state: ScoutTacticalState) -> List[Dict[str, Any]]` 函数
- [ ] 返回的列表顺序固定：fly_to → open_scout_panel → preview_route
- [ ] 所有动作包含 `type` 和 `params` 字段
- [ ] 生成逻辑支持扩展（未来可添加新动作类型）

---

### Requirement: State 更新

当 UI Actions 生成后，MUST更新 `ScoutTacticalState` 的 `ui_actions` 字段。
当 UI Actions 生成后，必须更新 `ScoutTacticalState` 的 `ui_actions` 字段。

#### Scenario: 基础场景
当 UI Actions 生成后，必须更新 `ScoutTacticalState` 的 `ui_actions` 字段。

- **GIVEN**:
- UI Actions 生成成功

- **WHEN**:
- `prepare_response` 节点返回结果

- **THEN**:
- 返回字典 `{"ui_actions": [...]}`
- State 中包含 `ui_actions` 字段

- **Acceptance Criteria**:
- [ ] 返回的 `ui_actions` 为 `List[Dict[str, Any]]` 类型
- [ ] State 强类型定义中 `ui_actions` 字段标记为 `NotRequired[List[Dict[str, Any]]]`

---

### Requirement: WebSocket 推送集成

当 UI Actions 生成后，`ws_notify` 节点MUST推送到 Java 后台，由后台广播到前端。
当 UI Actions 生成后，`ws_notify` 节点必须推送到 Java 后台，由后台广播到前端。

#### Scenario: 基础场景
当 UI Actions 生成后，`ws_notify` 节点必须推送到 Java 后台，由后台广播到前端。

- **GIVEN**:
- UI Actions 已生成
- OrchestratorClient 已初始化

- **WHEN**:
- `ws_notify` 节点执行

- **THEN**:
- 调用 `orchestrator_client.publish_scout_scenario(payload)`
- payload 包含:
  ```python
  ScoutScenarioPayload(
      incident_id="INC-001",
      targets=[...],
      devices=[...],
      waypoints=[...],
      intel_requirements=[...],
      risk_warnings=[...],
      ui_actions=[...]  # 包含在 payload 中
  )
  ```

- **Acceptance Criteria**:
- [ ] 使用 `@task` 装饰器包装 HTTP 调用
- [ ] payload 的 `ui_actions` 字段包含所有生成的动作
- [ ] 日志记录: `logger.info("scout_scenario_pushed", status=response.status, action_count=len(ui_actions))`
- [ ] 推送失败时抛出异常（不降级）

---

### Requirement: OrchestratorClient 扩展

系统MUST必须扩展 `OrchestratorClient` 支持侦察场景推送。
系统必须扩展 `OrchestratorClient` 支持侦察场景推送。

#### Scenario: 基础场景
系统必须扩展 `OrchestratorClient` 支持侦察场景推送。

- **GIVEN**:
- 现有 `OrchestratorClient` 仅支持 `publish_rescue_scenario`

- **WHEN**:
- 添加新方法 `publish_scout_scenario`

- **THEN**:
- 方法签名:
  ```python
  def publish_scout_scenario(self, payload: ScoutScenarioPayload) -> Dict[str, Any]:
      """推送侦察场景消息，驱动前端可视化。"""
      body = payload.to_dict()
      response = self._post("/api/v1/scout/scenario", body)
      logger.info("scout_scenario_published", response=response)
      return response
  ```

- **Acceptance Criteria**:
- [ ] 在 `src/emergency_agents/external/orchestrator_client.py` 中添加方法
- [ ] 端点为 `POST /api/v1/scout/scenario`
- [ ] payload 转换为 camelCase 格式（Java 后台约定）
- [ ] 返回响应包含 `status` 字段

---

### Requirement: ScoutScenarioPayload 数据模型

系统MUST必须定义 `ScoutScenarioPayload` 数据模型用于 Java 集成。
系统必须定义 `ScoutScenarioPayload` 数据模型用于 Java 集成。

#### Scenario: 基础场景
系统必须定义 `ScoutScenarioPayload` 数据模型用于 Java 集成。

- **GIVEN**:
- 需要推送侦察场景数据到 Java 后台

- **WHEN**:
- 定义数据类

- **THEN**:
- 数据类包含以下字段:
  ```python
  @dataclass
  class ScoutScenarioPayload:
      incident_id: str
      targets: List[Dict[str, Any]]
      devices: List[Dict[str, Any]]
      waypoints: List[Dict[str, Any]]
      intel_requirements: List[str]
      risk_warnings: List[Dict[str, Any]]
      ui_actions: List[Dict[str, Any]]

      def to_dict(self) -> Dict[str, Any]:
          return {
              "incidentId": self.incident_id,
              "targets": self.targets,
              "devices": self.devices,
              "waypoints": self.waypoints,
              "intelRequirements": self.intel_requirements,
              "riskWarnings": self.risk_warnings,
              "uiActions": self.ui_actions
          }
  ```

- **Acceptance Criteria**:
- [ ] 在 `src/emergency_agents/external/models.py` 中定义（新建文件或复用）
- [ ] 使用 `@dataclass` 装饰器
- [ ] `to_dict()` 方法转换为 camelCase（Java 约定）
- [ ] 所有字段包含类型注解

---

## MODIFIED Requirements

（无修改的需求）

---

## REMOVED Requirements

（无删除的需求）

---

**Spec 版本**: v1.0
**创建时间**: 2025-11-02
**状态**: DRAFT
