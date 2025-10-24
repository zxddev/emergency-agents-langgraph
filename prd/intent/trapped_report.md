# PRD: trapped_report（被困报告 · 口述/文本）

## 1. 背景与目标
- 专家在演示中以语音/文本报告“某地发现被困群众”，系统应抽取地点/经纬度/人数/时间等，生成实体并可上图，作为救援方案生成与任务拆解的触发源之一（不依赖视频链）。

## 2. 用户故事（例）
- “在水磨镇坐标31.68,103.85发现被困群众十人。”
- “在A村口有人被困，大约五到六人。”
- “在（31.700,103.900）发现两人被困，时间刚刚10分钟。”

## 3. 意图定义
- intent_type = `trapped_report`
- 价值：报告驱动，无需视频，直接形成可用实体与地图要素。

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "location_text": {"type": "string"},
    "lat": {"type": "number"},
    "lng": {"type": "number"},
    "count": {"type": "number", "minimum": 1},
    "time_reported": {"type": "string"},
    "description": {"type": "string"}
  },
  "required": ["count"],
  "additionalProperties": false
}
```

## 5. 解析与读回
- few‑shot抽槽；优先使用经纬度，缺失则基于地名提示“是否采用X解析到(…, …)？”；
- 读回：“已记录被困报告：位置(31.68,103.85)/水磨镇，人数字段=10，状态PENDING上图。确认吗？”

## 6. 流程与接口
- 路由：intent→trapped_report→生成实体（Point + count + 描述）→PENDING上图→可联动 rescue_task_generate；
- Java（TODO）：
  - `POST /entities` {type:"TRAPPED", point:{lat,lng}, count, description, time_reported}
  - 可选 `POST /events` {type:"people_trapped", parent_event_id?, title, description}

## 7. 错误与兜底
- 未提供坐标且无法解析地名：要求用户点击选点或提供经纬度；
- 人数不明确（“几人”）：读回“是否按N人记？”并允许修正。

## 8. 验收KPI
- few‑shot≥20；槽位抽取准确率≥0.90；读回追问命中率≥0.90；
- 上图≤2s（演示口径），可作为后续方案生成的输入。
