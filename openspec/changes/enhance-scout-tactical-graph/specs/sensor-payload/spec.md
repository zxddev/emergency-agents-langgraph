# Spec: 传感器载荷分配能力

## ADDED Requirements

### Requirement: 传感器需求映射表

系统MUST必须维护目标类型到传感器需求的映射表，用于自动分配传感器任务。
系统必须维护目标类型到传感器需求的映射表，用于自动分配传感器任务。

#### Scenario: 基础场景
系统必须维护目标类型到传感器需求的映射表，用于自动分配传感器任务。

- **GIVEN**:
- 目标类型为 "坍塌建筑"

- **WHEN**:
- 查询 `SENSOR_REQUIREMENTS` 映射表

- **THEN**:
- 返回 ["camera", "infrared"]

- **Acceptance Criteria**:
- [ ] 定义 `SENSOR_REQUIREMENTS: Dict[str, List[str]]` 常量
- [ ] 至少包含5种灾害类型的映射:
  - "坍塌建筑" → ["camera", "infrared"]
  - "危化品泄漏" → ["gas_detector", "camera"]
  - "洪水区域" → ["camera", "lidar"]
  - "火灾现场" → ["infrared", "camera"]
  - "人员被困" → ["camera", "infrared", "audio"]
- [ ] 未知类型默认返回 ["camera"]

---

### Requirement: 设备能力匹配

当分配传感器任务时，系统MUST必须验证设备是否具备所需传感器能力。
当分配传感器任务时，系统必须验证设备是否具备所需传感器能力。

#### Scenario: 基础场景
当分配传感器任务时，系统必须验证设备是否具备所需传感器能力。

- **GIVEN**:
- 设备 UAV-001 的能力列表为 ["camera", "infrared", "gps"]
- 任务需要传感器 ["camera", "infrared"]

- **WHEN**:
- 执行能力匹配逻辑

- **THEN**:
- 设备 UAV-001 满足条件
- 为该设备分配 ["camera", "infrared"] 传感器任务

- **Acceptance Criteria**:
- [ ] 实现 `match_device_capabilities()` 函数
- [ ] 仅分配设备实际具备的传感器
- [ ] 如果设备缺少必需传感器，记录警告日志但不阻塞流程

---

### Requirement: 传感器任务配置

当分配传感器后，系统MUST必须为每个传感器生成详细的任务配置（工作模式、采样间隔）。
当分配传感器后，系统必须为每个传感器生成详细的任务配置（工作模式、采样间隔）。

#### Scenario: 基础场景
当分配传感器后，系统必须为每个传感器生成详细的任务配置（工作模式、采样间隔）。

- **GIVEN**:
- 设备 UAV-001 被分配 ["camera", "infrared"] 传感器

- **WHEN**:
- 生成传感器任务配置

- **THEN**:
- 返回任务列表:
  ```json
  [
    {"sensor": "camera", "mode": "continuous", "interval": 1},
    {"sensor": "infrared", "mode": "continuous", "interval": 1}
  ]
  ```

- **Acceptance Criteria**:
- [ ] 每个传感器任务包含 3 个字段: sensor, mode, interval
- [ ] 默认模式为 "continuous"（连续采集）
- [ ] 默认间隔为 1 秒
- [ ] 支持按传感器类型自定义配置（如红外采样间隔 0.5 秒）

---

### Requirement: Payload 数据结构

The system MUST return sensor payload assignment results in standardized format for device control module parsing.

#### Scenario: 基础场景
传感器载荷分配结果必须以标准化格式返回，便于设备控制模块解析。

- **GIVEN**:
- 2个设备被分配传感器任务

- **WHEN**:
- `sensor_payload_assignment` 节点完成

- **THEN**:
- 返回 `sensor_payloads` 列表:
  ```json
  [
    {
      "device_id": "UAV-001",
      "sensors": ["camera", "infrared"],
      "tasks": [
        {"sensor": "camera", "mode": "continuous", "interval": 1},
        {"sensor": "infrared", "mode": "continuous", "interval": 1}
      ]
    },
    {
      "device_id": "ROBOT-002",
      "sensors": ["gas_detector"],
      "tasks": [
        {"sensor": "gas_detector", "mode": "event_triggered", "threshold": 50}
      ]
    }
  ]
  ```

- **Acceptance Criteria**:
- [ ] 每个 payload 包含 3 个字段: device_id, sensors, tasks
- [ ] `sensors` 为传感器名称列表
- [ ] `tasks` 为详细任务配置列表

---

### Requirement: State 更新

当传感器分配完成后，MUST更新 `ScoutTacticalState` 的 `sensor_payloads` 字段。
当传感器分配完成后，必须更新 `ScoutTacticalState` 的 `sensor_payloads` 字段。

#### Scenario: 基础场景
当传感器分配完成后，必须更新 `ScoutTacticalState` 的 `sensor_payloads` 字段。

- **GIVEN**:
- 传感器分配生成了 2 个 payload

- **WHEN**:
- 节点返回结果

- **THEN**:
- 返回字典 `{"sensor_payloads": [...]}`
- State 中包含 `sensor_payloads` 字段

- **Acceptance Criteria**:
- [ ] 返回的 `sensor_payloads` 为 `List[Dict[str, Any]]` 类型
- [ ] State 强类型定义中 `sensor_payloads` 字段标记为 `NotRequired[List[Dict[str, Any]]]`

---

### Requirement: 日志和监控

The system MUST record detailed logs during sensor payload assignment process.

#### Scenario: 基础场景
传感器分配过程必须记录详细日志。

- **GIVEN**:
- 传感器分配节点正在执行

- **WHEN**:
- 为2个设备分配传感器
- 总共分配 3 个传感器任务

- **THEN**:
- 记录 structlog 日志:
  ```python
  logger.info("scout_sensors_assigned",
      payload_count=2,
      total_sensors=3,
      sensor_types=["camera", "infrared", "gas_detector"]
  )
  ```

- **Acceptance Criteria**:
- [ ] 日志包含 `payload_count`, `total_sensors`, `sensor_types` 字段
- [ ] 能力不匹配时记录 `logger.warning("sensor_capability_mismatch", device=..., required=..., actual=...)`

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
