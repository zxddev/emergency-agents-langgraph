# Spec: 航线规划能力

## ADDED Requirements

### Requirement: 圆形巡航航点生成

当目标为单点坐标时，系统MUST必须生成围绕目标的圆形巡航航点，用于全方位侦察。
当目标为单点坐标时，系统必须生成围绕目标的圆形巡航航点，用于全方位侦察。

#### Scenario: 基础场景
当目标为单点坐标时，系统必须生成围绕目标的圆形巡航航点，用于全方位侦察。

- **GIVEN**:
- 目标坐标为 (31.2, 121.5)
- 巡航半径为 100 米
- 航点数量设置为 8

- **WHEN**:
- `recon_route_planning` 节点执行圆形模式

- **THEN**:
- 生成8个航点，均匀分布在目标周围（每45度一个）
- 每个航点包含: lat, lon, alt (固定80米), speed (5m/s), action ("patrol")
- 航点顺序为顺时针环绕

- **Acceptance Criteria**:
- [ ] 实现 `generate_waypoints_circle()` 函数
- [ ] 使用地理计算函数 `destination_point(center, radius, bearing)` 计算航点坐标
- [ ] 返回的航点列表长度等于 `num_points` 参数
- [ ] 航点高度统一为 80 米（可配置）

---

### Requirement: 网格扫描航点生成

当目标为区域（矩形边界框）时，系统MUST必须生成蛇形网格扫描航点，用于全覆盖侦察。
当目标为区域（矩形边界框）时，系统必须生成蛇形网格扫描航点，用于全覆盖侦察。

#### Scenario: 基础场景
当目标为区域（矩形边界框）时，系统必须生成蛇形网格扫描航点，用于全覆盖侦察。

- **GIVEN**:
- 目标区域边界框: {"min_lat": 31.2, "max_lat": 31.22, "min_lon": 121.5, "max_lon": 121.52}
- 航点间距为 50 米

- **WHEN**:
- `recon_route_planning` 节点执行网格模式

- **THEN**:
- 生成蛇形扫描航点（第一行向东，第二行向西，交替进行）
- 航点间距约为 50 米
- 覆盖整个区域边界框

- **Acceptance Criteria**:
- [ ] 实现 `generate_waypoints_grid()` 函数
- [ ] 使用 `meters_to_degrees_lat()` 和 `meters_to_degrees_lon()` 计算步长
- [ ] 蛇形扫描模式（避免设备频繁转向）
- [ ] 边界航点不超出 bbox 范围

---

### Requirement: 航线模式自动选择

系统MUST必须根据 `slots.recon_objective` 和目标类型自动选择合适的航线生成模式。
系统必须根据 `slots.recon_objective` 和目标类型自动选择合适的航线生成模式。

#### Scenario: 基础场景
系统必须根据 `slots.recon_objective` 和目标类型自动选择合适的航线生成模式。

- **GIVEN**:
- 目标类型为 "坍塌建筑"（单点）
- `recon_objective` 为 "结构评估"

- **WHEN**:
- 执行航线规划逻辑

- **THEN**:
- 自动选择圆形巡航模式（适合单点目标）
- 巡航半径设置为 100 米

- **Acceptance Criteria**:
- [ ] 实现 `select_route_mode()` 函数
- [ ] 模式选择规则:
  - 单点目标 → 圆形巡航
  - 区域目标 → 网格扫描
  - 线性目标（河道/道路） → 跟踪飞行（Phase 2）
- [ ] 默认模式为圆形巡航

---

### Requirement: 高德路径规划集成（Phase 2）

当目标为复杂地形（城市道路、河道）时，系统MUST应调用高德API获取真实路径规划。
当目标为复杂地形（城市道路、河道）时，系统应调用高德API获取真实路径规划。

#### Scenario: 基础场景
当目标为复杂地形（城市道路、河道）时，系统应调用高德API获取真实路径规划。

- **GIVEN**:
- 目标类型为 "河道洪水监测"
- 起点坐标 (31.2, 121.5)
- 终点坐标 (31.25, 121.55)

- **WHEN**:
- 执行高德路径规划（Phase 2实现）

- **THEN**:
- 调用 `AmapClient.driving_route()` 获取道路路径
- 将路径步骤转换为航点列表
- 使用 `@task` 装饰器包装 API 调用（幂等性）

- **Acceptance Criteria**:
- [ ] 实现 `@task async def amap_route_planning_task()`
- [ ] 相同起终点多次调用返回相同结果
- [ ] 日志记录 `logger.info("amap_route_planned", waypoint_count=...)`
- [ ] API调用失败时抛出异常（不降级）

---

### Requirement: State 更新

当航线规划完成后，MUST更新 `ScoutTacticalState` 的 `waypoints` 字段。
当航线规划完成后，必须更新 `ScoutTacticalState` 的 `waypoints` 字段。

#### Scenario: 基础场景
当航线规划完成后，必须更新 `ScoutTacticalState` 的 `waypoints` 字段。

- **GIVEN**:
- 航线规划生成了 12 个航点

- **WHEN**:
- 节点返回结果

- **THEN**:
- 返回字典 `{"waypoints": [...]}`
- `waypoints` 字段为航点列表，每个航点包含: lat, lon, alt, speed, action

- **Acceptance Criteria**:
- [ ] 返回的 `waypoints` 为 `List[Dict[str, Any]]` 类型
- [ ] 每个航点至少包含 5 个字段: lat, lon, alt, speed, action
- [ ] State 强类型定义中 `waypoints` 字段标记为 `NotRequired[List[Dict[str, Any]]]`

---

### Requirement: 日志和监控

The system MUST record detailed logs and report Prometheus metrics during route planning process.

#### Scenario: 基础场景
航线规划过程必须记录详细日志并上报 Prometheus 指标。

- **GIVEN**:
- 航线规划节点正在执行

- **WHEN**:
- 生成12个航点
- 总距离约 1.2 公里
- 预计飞行时间 4 分钟

- **THEN**:
- 记录 structlog 日志:
  ```python
  logger.info("scout_route_generated",
      waypoint_count=12,
      total_distance_km=1.2,
      estimated_time_min=4.0,
      route_mode="circle"
  )
  ```
- 上报 Prometheus 指标:
  ```python
  scout_waypoint_count.observe(12)
  ```

- **Acceptance Criteria**:
- [ ] 日志包含 `waypoint_count`, `total_distance_km`, `estimated_time_min`, `route_mode` 字段
- [ ] Prometheus 直方图 `scout_waypoint_count` 记录航点数量分布
- [ ] 规划失败时记录 `logger.error("route_planning_failed", error=...)`

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
