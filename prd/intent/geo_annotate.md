# PRD: geo_annotate（地图标注）

## 1. 背景与目标
- 语音/文本生成地图标注（点/线/面+标签），默认PENDING，待人工签收。

## 2. 用户故事
- “把桥头标注为道路阻断。” / “把这段河岸标为积水风险。”

## 3. 意图定义
- intent_type = `geo_annotate`

## 4. 槽位Schema
```json
{
  "type": "object",
  "properties": {
    "geom": {"oneOf": [{"$ref": "#/definitions/Point"}, {"$ref": "#/definitions/LineString"}, {"$ref": "#/definitions/Polygon"}]},
    "label": {"type": "string"},
    "evidence": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  },
  "required": ["geom", "label"],
  "definitions": {
    "Point": {"type": "object", "properties": {"type": {"const": "Point"}, "coordinates": {"type": "array"}}, "required": ["type", "coordinates"]},
    "LineString": {"type": "object", "properties": {"type": {"const": "LineString"}, "coordinates": {"type": "array"}}, "required": ["type", "coordinates"]},
    "Polygon": {"type": "object", "properties": {"type": {"const": "Polygon"}, "coordinates": {"type": "array"}}, "required": ["type", "coordinates"]}
  }
}
```

## 5. 解析与读回
- few‑shot抽槽；缺几何/标签→追问；
- 读回：“将在目标几何处标注‘道路阻断’，状态PENDING。确认吗？”

## 6. 流程与接口
- Java：`POST /annotations`（PENDING）【TODO】。

## 7. 验收
- few‑shot≥20；槽位准确率≥0.9；与签收闭环联调通过。
