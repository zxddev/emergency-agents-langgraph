# 侦察方案输出（预览接口）

> 版本：0.1
> 状态：骨架已落地，后续将补充设备分配、航线规划模块。

## 1. 触发链路
- 入口意图：`scout-task-generate`
- Handler：`ScoutTaskGenerationHandler`
- 子图：`graph/scout_tactical_app.py`
- 数据源：`RiskDataRepository`（基于 `IncidentDAO` 的危险区域表）

## 2. 输出结构
```jsonc
{
  "scout_plan": {
    "overview": {
      "incidentId": "incident-1",
      "targetType": "hazard",
      "objective": "确认化工园泄漏范围",
      "generatedAt": "2025-11-01T14:20:33Z",
      "riskSummary": {
        "total": 3,
        "highSeverity": 1
      }
    },
    "targets": [
      {
        "targetId": "risk-1",
        "hazardType": "chemical_leak",
        "severity": 4,
        "location": {"lng": 120.0, "lat": 30.0},
        "priority": "HIGH",
        "notes": "疑似有毒气体泄漏"
      }
    ],
    "intelRequirements": [
      {"type": "commander_objective", "description": "确认化工园泄漏范围"},
      {"type": "hazard_assessment", "targetId": "risk-1", "hazard": "chemical_leak"}
    ],
    "recommendedSensors": ["gas_detector", "visible_light_camera"],
    "riskHints": ["化工园东侧：chemical_leak 等级 4"]
  },
  "response_text": "已整理 1 个侦察目标，其中 1 个高风险点。已列出优先检查清单。",
  "ui_actions": [
    {"action": "camera_flyto", "payload": {"lng": 120.0, "lat": 30.0}},
    {"action": "open_panel", "payload": {"panel": "scout_plan", "params": {"plan": "..."}}},
    {"action": "show_risk_warning", "payload": {"message": "化工园东侧：chemical_leak 等级 4"}}
  ]
}
```

## 3. 前端对接建议
- 新增 `scout_plan` 面板：展示 `targets`、`intelRequirements`、`recommendedSensors`。
- 已推送 `show_risk_warning` 动作，可与原有风险提示 UI 复用。
- `camera_flyto` 将定位到首个侦察目标，前端需在地图高亮对应区域。

## 4. 后续 TODO
- 根据设备与任务约束，补足 `devices`/`waypoints` 输出。
- 与 Adapter Hub 对接，完成侦察任务下发。
- 联动 `RiskPredictor` 输出的 `last_result`，提供趋势播报。
