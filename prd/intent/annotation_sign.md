# PRD: annotation_sign（标注签收/驳回）

## 1. 背景与目标
- 对PENDING标注进行签收/驳回（SIGNED/REJECTED），完成HITL闭环与证据沉淀。

## 2. 用户故事
- “签收刚才的道路阻断标注。” / “驳回第二个候选标注。”

## 3. 意图定义
- intent_type = `annotation_sign`

## 4. 槽位Schema
```json
{
  "type": "object",
  "properties": {
    "annotation_id": {"type": "string"},
    "decision": {"enum": ["SIGNED", "REJECTED"]}
  },
  "required": ["annotation_id", "decision"]
}
```

## 5. 解析与读回
- few‑shot抽槽；读回：“将对标注 {annotation_id} 设置为 {decision}，确认吗？”

## 6. 流程与接口
- Java：`POST /annotations/{id}/sign`【TODO】。

## 7. 验收
- few‑shot≥20；槽位准确率≥0.95；闭环稳定。
