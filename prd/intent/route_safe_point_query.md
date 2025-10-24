# PRD: route_safe_point_query（路线/安全点查询）

## 1. 背景与目标
- 通过语音/文本查询到目标坐标的候选路线（best/fastest/safest）与最近安全点，用于机动与驻扎演示（不做真实导航）。

## 2. 用户故事（例）
- “规划到31.68,103.85的最安全路线。”
- “从当前位置到茂县的最快路线是什么？”
- “最近的安全点在哪？推荐三个。”

## 3. 意图定义
- intent_type = `route_safe_point_query`
- 价值：为行进/驻扎提供可解释的选择（读回差异）。

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "lat": {"type": "number"},
    "lng": {"type": "number"},
    "location_text": {"type": "string"},
    "policy": {"enum": ["best", "fastest", "safest"], "default": "best"}
  },
  "required": ["policy"]
}
```

## 5. 解析与读回
- few‑shot抽槽；缺坐标时尝试用地名追问确认；
- 读回：“已生成 best/fastest/safest 三方案；最安全避开两处风险段，预计时长+10%。是否上屏并保存？”

## 6. 流程与接口
- 路由：intent→route_safe_point_query→生成候选（演示数据/示意GeoJSON）→上屏；
- Java（TODO）：
  - `GET /routes?lat=...&lng=...&policy=...`（返回LineString与分段代价）
  - `GET /safe-points?near=lat,lng`（返回Point列表与评分）

## 7. 错误与兜底
- 目标不可达：提示改为“best”或更远安全点；
- 无坐标且无法地理编码：要求手动选点或提供经纬度。

## 8. 验收KPI
- few‑shot≥20；F1≥0.90；读回清晰，差异解释可理解；
- 上屏≤2s（演示口径）。
