# PRD: device_status_query（设备状态查询）

## 1. 背景与目标
- 通过自然语言查询设备状态（uav/robotdog）：电量、位置、链路、温度、在位等。

## 2. 用户故事（例）
- “无人机电量多少？位置在哪里？”
- “机器狗链路稳定吗？温度多少？”
- “设备A是否在位？”

## 3. 意图定义
- intent_type = `device_status_query`
- 价值：随时掌握关键设备健康与在位情况。

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "device_type": {"enum": ["uav", "robotdog"]},
    "device_id": {"type": "string"},
    "metric": {"enum": ["battery", "position", "link", "temperature", "presence"]}
  },
  "required": ["device_type", "metric"]
}
```

## 5. 解析与读回
- few‑shot抽槽；缺device_id时读回确认“是全部还是某一台？”；
- 读回：统一格式，如“uav#A 电量78%，位置(103.85,31.68)，链路良好”。

## 6. 流程与接口
- 路由：intent→device_status_query→聚合演示数据→读回；
- Java（TODO）：`GET /devices/status?type=...&id=...&metric=...`。

## 7. 错误与兜底
- 查无此设备：提示校验设备ID或类型；
- metric不支持：提示可查询项列表。

## 8. 验收KPI
- few‑shot≥20；F1≥0.90；读回一致、口径统一。
