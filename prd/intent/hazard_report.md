# PRD: hazard_report（灾情报告 · 口述/文本）

## 1. 背景与目标
- 专家以语音/文本报告“新增灾情/次生灾害”，系统抽取灾种/地点/经纬度/严重度/时间，创建事件并可上图，作为侦察/路线与方案生成的触发源。（无视频链）

## 2. 用户故事（例）
- “在XX乡发生山体滑坡，坐标31.70,103.90。”
- “河岸处疑似溃决，严重度高。”
- “化工厂发生泄漏，位置在(31.71,103.88)。”

## 3. 意图定义
- intent_type = `hazard_report`

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "event_type": {"type": "string"},
    "location_text": {"type": "string"},
    "lat": {"type": "number"},
    "lng": {"type": "number"},
    "severity": {"enum": ["LOW", "MED", "HIGH"]},
    "time_reported": {"type": "string"},
    "description": {"type": "string"},
    "parent_event_id": {"type": "string"}
  },
  "required": ["event_type"],
  "additionalProperties": false
}
```

## 5. 解析与读回
- few‑shot抽槽；优先使用经纬度，缺失则地名追问；
- 读回：“已创建事件：{event_type}@位置(…, …)/{location_text}，严重度{severity}，状态active。确认吗？”

## 6. 流程与接口
- 路由：intent→hazard_report→创建事件实体→上图→可联动 recon_minimal / route_safe_point / rescue_task_generate；
- Java（TODO）：`POST /events` {event_type,lat,lng,location_text,severity,time_reported,description,parent_event_id}

## 7. 错误与兜底
- 事件类型不识别：读回可选项（滑坡/化工泄漏/洪水/道路阻断…）；
- 坐标缺失且无法解析：要求选点或提供经纬度。

## 8. 验收KPI
- few‑shot≥20；F1≥0.90；上图≤2s；可作为下游输入。
