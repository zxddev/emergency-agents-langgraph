# 侦察方案数据契约（Recon Plan Contract）

> 本文定义 AI 侦察方案的结构化响应格式，供 Python LangGraph、Java Web API、前端 UI 统一实现。`

## 1. 顶层结构 `ReconPlan`

| 字段 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `objectives` | `List[str]` | 是 | 方案目标列表（按优先级排序） |
| `sectors` | `List[ReconSector]` | 是 | 作战扇区信息 |
| `tasks` | `List[ReconTask]` | 是 | 单个侦察任务集合（仅包含侦察、警戒、救援引导，不与救援任务混淆） |
| `assets` | `List[ReconAssetPlan]` | 否 | 资产使用计划（无人机、机器人犬等） |
| `constraints` | `List[ReconConstraint]` | 否 | 执行约束（禁飞区、气象、通信约束等） |
| `justification` | `ReconJustification` | 是 | AI 推理说明，包含证据与风险提示 |
| `meta` | `ReconPlanMeta` | 是 | 元信息（生成来源、缺失字段、数据来源） |

### 1.1 `ReconSector`
- `sector_id: str` 扇区ID
- `name: str` 扇区名称
- `area: List[GeoPoint]` 扇区边界多边形，按经纬度顺序
- `priority: Literal[critical|high|medium|low]`
- `tasks: List[str]` 扇区涉及的任务ID列表

### 1.2 `ReconTask`
| 字段 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `task_id` | `str` | 是 | 任务 ID，与 `operational.tasks.code` 或自定义编号对应 |
| `title` | `str` | 是 | 任务标题，便于前端展示 |
| `mission_phase` | `Literal["recon", "alert", "rescue", "logistics"]` | 是 | 侦察阶段标识；**侦察任务限定使用 `recon`/`alert`**，不得与救援主体任务混用 |
| `objective` | `str` | 是 | 任务目标描述 |
| `priority` | `Literal[critical|high|medium|low]` | 是 | 优先级 |
| `target_area` | `Optional[List[GeoPoint]]` | 否 | 任务涉及区域多边形 |
| `target_points` | `List[GeoPoint]` | 否 | 关注点坐标（如泄漏源、滑坡点） |
| `required_capabilities` | `List[str]` | 否 | 能力要求（如 thermal_imaging、gas_detection） |
| `recommended_devices` | `List[str]` | 否 | 推荐装备 ID 列表（与 `ReconDevice.device_id` 对应） |
| `assigned_unit` | `Optional[str]` | 否 | 指定队伍/车辆 ID（如前突侦察车） |
| `duration_minutes` | `Optional[int]` | 否 | 预计执行时间（分钟） |
| `safety_notes` | `Optional[str]` | 否 | 安全提示 |
| `dependencies` | `List[str]` | 否 | 依赖任务 ID |

### 1.3 `ReconAssetPlan`
- `asset_id: str` 资产编号（设备或队伍）
- `asset_type: Literal[uav|robot_dog|usv|sensor|team]`
- `usage: str` 使用说明
- `duration_minutes: Optional[int]`
- `remarks: Optional[str]`

### 1.4 `ReconConstraint`
- `name: str` 约束名称（如 `no_fly_zone`）
- `detail: Optional[str]` 描述
- `severity: Literal[info|warning|critical]`

### 1.5 `ReconJustification`
- `summary: str` 推理概要
- `evidence: List[str]` 证据链接或 ID（视频、图像、传感器数据）
- `reasoning_chain: List[str]` 推理步骤
- `risk_warnings: List[str]` 风险提示

### 1.6 `ReconPlanMeta`
- `generated_by: Literal[ai|manual]`
- `schema_version: str` 结构版本（默认 `v1`）
- `data_sources: List[str]` 使用的数据源（如 `events`, `devices`, `weather`）
- `missing_fields: List[str]` 缺失字段提示
- `warnings: List[str]` 额外警告

## 2. `TaskPlanPayload`（写入 `operational.tasks.plan_step`）

| 字段 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `scheme_id` | `str` | 是 | 关联方案ID（对应 `operational.scheme.id`） |
| `task_id` | `str` | 是 | 任务ID |
| `objective` | `str` | 是 | 任务目标 |
| `target_points` | `List[GeoPoint]` | 否 | 任务关键坐标 |
| `required_capabilities` | `List[str]` | 否 | 能力要求 |
| `recommended_devices` | `List[str]` | 否 | 建议装备 |
| `duration_minutes` | `Optional[int]` | 否 | 预计用时 |
| `safety_notes` | `Optional[str]` | 否 | 安全提示 |
| `dependencies` | `List[str]` | 否 | 前置任务 |
| `assigned_unit` | `Optional[str]` | 否 | 指定执行单位 |

> 所有侦察任务写入 `plan_step` 时，`mission_phase` 应为 `recon` 或 `alert`，禁止与救援主体任务混用。

## 3. GeoPoint 说明

```json
{
  "lon": 103.82,
  "lat": 31.67
}
```
- 采用 WGS84，经度范围 [-180, 180]，纬度范围 [-90, 90]。

## 4. 示例 JSON

```json
{
  "objectives": ["快速识别泄漏覆盖范围", "确定安全撤离路径"],
  "sectors": [
    {
      "sector_id": "sec-north",
      "name": "北侧工业区",
      "area": [
        {"lon": 103.82, "lat": 31.67},
        {"lon": 103.85, "lat": 31.70},
        {"lon": 103.80, "lat": 31.72}
      ],
      "priority": "critical",
      "tasks": ["task-uav-01"]
    }
  ],
  "tasks": [
    {
      "task_id": "task-uav-01",
      "title": "无人机热成像巡检",
      "mission_phase": "recon",
      "objective": "识别危化泄漏扩散范围",
      "priority": "critical",
      "target_points": [
        {"lon": 103.83, "lat": 31.68}
      ],
      "required_capabilities": ["thermal_imaging"],
      "recommended_devices": ["uav-thermal-1"],
      "duration_minutes": 30,
      "safety_notes": "避免近距离穿越火源",
      "dependencies": []
    }
  ],
  "assets": [
    {
      "asset_id": "uav-thermal-1",
      "asset_type": "uav",
      "usage": "低空热成像巡检",
      "duration_minutes": 30
    }
  ],
  "constraints": [
    {
      "name": "no_fly_zone",
      "detail": "距离化工罐不足300米区域禁飞",
      "severity": "critical"
    }
  ],
  "justification": {
    "summary": "通过热成像快速定位泄漏范围",
    "evidence": ["video://leak-20251031-1"],
    "reasoning_chain": ["危化泄漏需快速定位", "无人机具备热成像能力"],
    "risk_warnings": ["注意风向变化导致扩散"]
  },
  "meta": {
    "generated_by": "ai",
    "schema_version": "v1",
    "data_sources": ["events", "devices", "weather"],
    "missing_fields": [],
    "warnings": []
  }
}
```

## 5. 数据库映射

- `operational.scheme.plan_payload` 存储完整 `ReconPlan` JSON。
- `operational.scheme.plan_data` 存 Markdown 文本摘要（供指挥席阅读）。
- `operational.tasks.plan_step` 存 `TaskPlanPayload`，仅适用于侦察/警戒等任务。
- `operational.tasks.type` 使用 `uav_recon`/`set_perimeter` 等侦察/预警类型，避免与救援任务同表混用。

## 6. 版本控制

- `schema_version` 默认 `v1`，若结构升级需兼容旧版本，可在 meta 中注明。
- Java、前端在解析时先检查 `meta.schema_version`，保证兼容处理。

---

最后更新：2025-10-31
