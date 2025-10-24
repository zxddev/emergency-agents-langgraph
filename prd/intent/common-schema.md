# 通用Schema（IntentResult / Slots）

## IntentResult（统一输出）
```json
{
  "intent_type": "recon_plan",
  "slots": {"area_of_interest": {"type": "Polygon", "coordinates": [...]}, "pattern": "lawnmower", "alt_m": 80, "product": "orthomap"},
  "meta": {"confidence": 0.92, "need_confirm": true, "missing_slots": [], "text_spans": {"alt_m": "一百米"}}
}
```

### 字段
- intent_type: 枚举见各PRD文件
- slots: 按意图定义的字段子集（GeoJSON统一：Point/LineString/Polygon）
- meta:
  - confidence: 0..1；
  - need_confirm: 高风险动作用；
  - missing_slots: 缺槽位列表（触发追问）；
  - text_spans: 关键提取片段用于审计。

## 通用槽位与类型
- location_text: string（地名原文）；lat/lng: number（WGS84）
- Point/LineString/Polygon: GeoJSON 结构
- pattern: "lawnmower"|"orbit"|"route"
- alt_m/speed/duration_min: number（SI单位）
- modality: "EO"|"IR"|"Zoom"|"GAS"（保留占位）
- channel: "uav"|"robotdog_cam"（保留占位）
- target/label/evidence[]：分析目标/标签/证据URI
- annotation_id/decision：标注签收使用

## 校验与读回
- 先校验 slots 必填；缺失→读回追问；
- 高风险（移动/返航/关键变更）→读回确认模板。
