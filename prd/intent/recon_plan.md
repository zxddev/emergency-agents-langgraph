# PRD: recon_plan（区域扫图/建模）

## 1. 背景与目标
- 语音/文本定义多边形与航参，生成区域扫图/建模任务（不发飞控）；UAV轨迹仅用于地图可视化。

## 2. 用户故事
- “用网格把这块区域扫图，高一百米，输出正射图。”
- “按这个多边形做三维建模，速度三米每秒。”

## 3. 意图定义
- intent_type = `recon_plan`

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "area_of_interest": {"$ref": "#/definitions/Polygon"},
    "pattern": {"enum": ["lawnmower"]},
    "alt_m": {"type": "number", "minimum": 10, "maximum": 300},
    "speed": {"type": "number", "minimum": 1, "maximum": 15},
    "product": {"enum": ["orthomap", "model3d"]}
  },
  "required": ["area_of_interest", "pattern", "alt_m", "product"],
  "definitions": {
    "Polygon": {"type": "object", "properties": {"type": {"const": "Polygon"}, "coordinates": {"type": "array"}}, "required": ["type", "coordinates"]}
  }
}
```

## 5. 解析与读回
- few‑shot 分类与抽槽；缺少多边形/高度→最小追问；
- 读回：“按网格覆盖所选区域，高100m、速5m/s，产出正射图。确认吗？”

## 6. 流程与接口
- 路由：intent→recon_plan→（生成说明与可视化轨迹LineString）→上图；
- Java：无（可选）：/plans 作为记录（TODO）。

## 7. 兜底
- AOI缺失或过大→提示缩小范围或提高高度；
- 演示期不做禁飞校验，仅提示型安全读回。

## 8. 验收
- few‑shot≥20；槽位准确率≥0.9；确认命中率100%。
