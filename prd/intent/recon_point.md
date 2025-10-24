# PRD: recon_point（点位观察/环绕）

## 1. 背景与目标
- 设定目标点与航参，执行定点观察或环绕（仅地图模拟轨迹）。

## 2. 用户故事
- “到A点定点观察，高五十米。” / “飞到桥头环绕二十米，一分钟。”

## 3. 意图定义
- intent_type = `recon_point`

## 4. 槽位Schema
```json
{
  "type": "object",
  "properties": {
    "point": {"$ref": "#/definitions/Point"},
    "alt_m": {"type": "number", "minimum": 10, "maximum": 300},
    "radius_m": {"type": "number", "minimum": 5, "maximum": 200},
    "duration_min": {"type": "number", "minimum": 0.5, "maximum": 30}
  },
  "required": ["point", "alt_m"],
  "definitions": {
    "Point": {"type": "object", "properties": {"type": {"const": "Point"}, "coordinates": {"type": "array"}}, "required": ["type", "coordinates"]}
  }
}
```

## 5. 解析与读回
- few‑shot抽槽；缺点/高度→追问；
- 读回：“到目标点，高50m，环绕20m，1分钟。确认吗？”

## 6. 流程与接口
- 路由：intent→recon_point→轨迹LineString上屏；
- Java：无（可选）：/plans 记录（TODO）。

## 7. 验收
- few‑shot≥20；槽位准确率≥0.9；确认命中率100%。
