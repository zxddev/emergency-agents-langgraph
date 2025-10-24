# PRD: rfa_request（资源/增援请求）

## 1. 背景与目标
- 以语音/文本发起资源与增援请求（单位类型/数量/装备清单/优先级/时间窗），形成标准RFA条目。

## 2. 用户故事（例）
- “请求工程队两支，含100吨吊车一台，优先级高。”
- “增派医疗队一支，带担架与生命探测仪。”

## 3. 意图定义
- intent_type = `rfa_request`

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "unit_type": {"type": "string"},
    "count": {"type": "number", "minimum": 1},
    "equipment": {"type": "array", "items": {"type": "string"}},
    "priority": {"enum": ["HIGH", "MED", "LOW"], "default": "MED"},
    "window": {"type": "string"}
  },
  "required": ["unit_type", "count"]
}
```

## 5. 解析与读回
- few‑shot抽槽；缺关键字段→追问；
- 读回：“将发起RFA：{unit_type}×{count}，装备{equipment}，优先级{priority}。确认吗？”

## 6. 流程与接口
- 路由：intent→rfa_request→生成RFA条目→可在审查后上送；
- Java（TODO）：`POST /rfa` {unit_type,count,equipment,priority,window}。

## 7. 错误与兜底
- 设备/单位类型不识别：读回可选项；
- 与现有方案冲突：提示由plan_task_approval审定。

## 8. 验收KPI
- few‑shot≥20；F1≥0.90；字段读回清晰、一致。
