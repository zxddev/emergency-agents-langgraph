# PRD: event_update（新增新灾/次生灾）

## 1. 背景与目标
- 通过语音/文本新增灾情事件（含父子关联），用于演示上屏与后续联动（侦察/方案）。

## 2. 用户故事（例）
- “新增次生灾害：滑坡，父事件为茂县地震。”
- “新增化工泄漏事件，标题XX化工厂泄漏，描述……，状态active。”

## 3. 意图定义
- intent_type = `event_update`

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "event_type": {"type": "string"},
    "severity": {"type": "string"},
    "parent_event_id": {"type": "string"},
    "title": {"type": "string"},
    "description": {"type": "string"}
  },
  "required": ["event_type", "title"]
}
```

## 5. 解析与读回
- few‑shot抽槽；缺title/类型→追问；
- 读回：“已创建事件：{title}（类型：{event_type}，父事件：{parent_event_id|无}），确认吗？”

## 6. 流程与接口
- 路由：intent→event_update→写入演示状态→上屏；
- Java（TODO）：`POST /events` {event_type,severity,parent_event_id,title,description}。

## 7. 错误与兜底
- 父事件不存在：提示有效父事件列表；
- 事件类型不识别：读回可选项。

## 8. 验收KPI
- few‑shot≥20；F1≥0.90；上屏≤2s。
