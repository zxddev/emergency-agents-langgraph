# Spec: 设备选择能力

## ADDED Requirements

### Requirement: 设备能力查询

系统MUST必须查询资产管理系统获取所有在线设备（无人机/机器人），并筛选出满足任务需求的设备列表。
系统必须查询资产管理系统获取所有在线设备（无人机/机器人），并筛选出满足任务需求的设备列表。

#### Scenario: 侦察子图启动时查询在线设备

**GIVEN**:
- 侦察任务已触发，`ScoutTaskGenerationSlots` 包含目标坐标和目标类型
- 资产管理系统中存在设备记录（状态、位置、能力标签）

- **WHEN**:
- `device_selection` 节点执行

- **THEN**:
- 调用 `AssetManagementClient.query_devices(status="online", types=["uav", "robot"])`
- 返回设备列表包含: id、type、capabilities、location、battery_level、status

- **Acceptance Criteria**:
- [ ] 查询结果过滤仅在线设备（status=online）
- [ ] 设备类型仅包含 uav 和 robot
- [ ] 每个设备记录包含完整的元数据字段

---

### Requirement: 传感器能力匹配

当获取到设备列表后，系统MUST必须根据目标类型（坍塌/危化/洪水）筛选出具备必要传感器能力的设备。
当获取到设备列表后，系统必须根据目标类型（坍塌/危化/洪水）筛选出具备必要传感器能力的设备。

#### Scenario: 基础场景

- **GIVEN**:
- 设备列表已查询
- 目标类型为 "坍塌建筑"（需要 camera + infrared）

- **WHEN**:
- 执行能力匹配逻辑

- **THEN**:
- 筛选出同时具备 ["camera", "infrared"] 能力的设备
- 不满足条件的设备被过滤

- **Acceptance Criteria**:
- [ ] 实现 `SENSOR_REQUIREMENTS` 映射表（目标类型 → 传感器列表）
- [ ] 设备的 `capabilities` 字段包含所有必需传感器时才通过筛选
- [ ] 如果无设备满足条件，抛出 `DeviceNotAvailableError` 异常（不使用 fallback）

---

### Requirement: 设备评分排序

当多个设备满足能力要求时，系统MUST必须根据距离、电量、状态计算综合评分，选择最优设备。
当多个设备满足能力要求时，系统必须根据距离、电量、状态计算综合评分，选择最优设备。

#### Scenario: 基础场景
当多个设备满足能力要求时，系统必须根据距离、电量、状态计算综合评分，选择最优设备。

- **GIVEN**:
- 3个设备满足能力要求
- 设备A: 距离500米、电量90%、状态idle
- 设备B: 距离1000米、电量50%、状态busy
- 设备C: 距离200米、电量70%、状态idle

- **WHEN**:
- 执行评分排序算法

- **THEN**:
- 设备评分规则:
  - 距离近 +100分（每公里扣10分）
  - 电量高 +50分（battery_level / 2）
  - 空闲状态 +30分
- 返回评分最高的前3个设备
- 设备C得分最高（100 - 2 + 35 + 30 = 163）

- **Acceptance Criteria**:
- [ ] 实现 `calculate_device_score()` 函数
- [ ] 评分结果附加到设备记录的 `score` 字段
- [ ] 按 `score` 降序排序
- [ ] 默认返回前3个设备（可配置）

---

### Requirement: State 更新

当设备选择完成后，MUST更新 `ScoutTacticalState` 的 `devices` 字段。
当设备选择完成后，必须更新 `ScoutTacticalState` 的 `devices` 字段。

#### Scenario: 基础场景
当设备选择完成后，必须更新 `ScoutTacticalState` 的 `devices` 字段。

- **GIVEN**:
- 设备选择逻辑已执行
- 筛选出2个最优设备

- **WHEN**:
- 节点返回结果

- **THEN**:
- 返回字典 `{"devices": [...]}`
- `devices` 字段包含设备的完整信息（id, type, capabilities, location, battery, score）

- **Acceptance Criteria**:
- [ ] 返回的 `devices` 为 `List[Dict[str, Any]]` 类型
- [ ] 每个设备包含至少 7 个字段: id, type, capabilities, location, battery_level, status, score
- [ ] State 强类型定义中 `devices` 字段标记为 `NotRequired[List[Dict[str, Any]]]`

---

### Requirement: 日志和监控

The system MUST record detailed logs and report Prometheus metrics during device selection process for troubleshooting and monitoring.

#### Scenario: 基础场景
设备选择过程必须记录详细日志并上报 Prometheus 指标，便于排查和监控。

- **GIVEN**:
- 设备选择节点正在执行

- **WHEN**:
- 查询设备成功
- 筛选后得到2个设备

- **THEN**:
- 记录 structlog 日志:
  ```python
  logger.info("scout_devices_selected",
      device_count=2,
      device_types=["uav", "robot"],
      avg_distance=350.0,
      avg_battery=80.0
  )
  ```
- 上报 Prometheus 指标:
  ```python
  scout_device_selection_count.labels(device_type="uav").inc()
  ```

- **Acceptance Criteria**:
- [ ] 日志包含 `device_count`, `device_types`, `avg_distance`, `avg_battery` 字段
- [ ] Prometheus 指标 `scout_device_selection_total` 按设备类型分类
- [ ] 查询失败时记录 `logger.error("device_query_failed", error=...)`

---

## MODIFIED Requirements

### Requirement: State 强类型定义（修改）

The system MUST refactor `ScoutTacticalState` from `TypedDict(total=False)` to explicit `Required`/`NotRequired` field markers for strong typing.

#### Scenario: 基础场景
当前 `ScoutTacticalState` 使用 `TypedDict(total=False)`，缺乏显式的必填/可选字段区分，需修改为使用 `Required`/`NotRequired`。

- **GIVEN**:
- 现有 State 定义:
  ```python
  class ScoutTacticalState(TypedDict, total=False):
      incident_id: str
      slots: ScoutTaskGenerationSlots
      devices: List[Dict]
  ```

- **WHEN**:
- 重构 State 定义

- **THEN**:
- 修改为:
  ```python
  class ScoutTacticalState(TypedDict):
      incident_id: Required[str]
      user_id: Required[str]
      thread_id: Required[str]
      slots: Required[ScoutTaskGenerationSlots]
      devices: NotRequired[List[Dict[str, Any]]]
      # ...其他 NotRequired 字段
  ```

- **Acceptance Criteria**:
- [ ] 必填字段使用 `Required[T]` 标注
- [ ] 可选字段使用 `NotRequired[T]` 标注
- [ ] mypy 类型检查通过

---

## REMOVED Requirements

（无删除的需求）

---

**Spec 版本**: v1.0
**创建时间**: 2025-11-02
**状态**: DRAFT
