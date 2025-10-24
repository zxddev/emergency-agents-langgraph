# PRD: recon_route（沿线勘察）

## 1. 背景与目标
- 设定路线（道路/河段）与航参，进行沿线侦察（地图模拟轨迹）。

## 2. 用户故事
- “沿这条路低空侦察回传，高四十米，速度五米每秒。”

## 3. 意图定义
- intent_type = `recon_route`

## 4. 槽位Schema
```json
{
  "type": "object",
  "properties": {
    "route": {"$ref": "#/definitions/LineString"},
    "alt_m": {"type": "number", "minimum": 10, "maximum": 300},
    "speed": {"type": "number", "minimum": 1, "maximum": 15}
  },
  "required": ["route", "alt_m"],
  "definitions": {
    "LineString": {"type": "object", "properties": {"type": {"const": "LineString"}, "coordinates": {"type": "array"}}, "required": ["type", "coordinates"]}
  }
}
```

## 5. 解析与读回
- few‑shot抽槽；缺路线/高度→追问；
- 读回：“沿线飞行，高40m，速5m/s。确认吗？”

## 6. 流程与接口
- 路由：intent→recon_route→轨迹LineString上屏；
- Java：无（可选）：/plans 记录（TODO）。

## 7. 验收
- few‑shot≥20；槽位准确率≥0.9；确认命中率100%。
