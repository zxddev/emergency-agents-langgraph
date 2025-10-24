# PRD: plan_task_approval（方案/任务 审定/下发/撤回）

## 1. 背景与目标
- 通过语音/文本对“救援方案/任务”进行批准、下发或撤回，形成HITL闭环；保留版本与差异，支持审计与回放。

## 2. 用户故事（例）
- “批准主方案并下发。” / “驳回备选方案一。”
- “撤回刚才下发的任务A。” / “下发所有未下发任务。”

## 3. 意图定义
- intent_type = `plan_task_approval`
- 价值：确保关键指令由人最终拍板，且全程可追溯。

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "plan_id": {"type": "string"},
    "plan_name": {"type": "string"},
    "decision": {"enum": ["approve", "reject", "dispatch", "recall"]},
    "reason": {"type": "string"}
  },
  "required": ["decision"]
}
```

## 5. 解析与读回
- few‑shot抽槽；若未提供plan_id且存在多方案→追问“是主方案还是备选X？”；
- 读回模板：
  - approve/dispatch：“将对方案{plan_id|plan_name}执行‘批准/下发’，变更摘要：{diff}。确认吗？”
  - reject/recall：“将对方案/任务执行‘驳回/撤回’，理由：{reason}。确认吗？”

## 6. 流程与接口
- 路由：intent→plan_task_approval→读回确认→执行状态变更→版本化记录；
- Java（TODO）：
  - `POST /plans/{id}/approve` {reason?}
  - `POST /plans/{id}/dispatch`
  - `POST /tasks/dispatch` [{task_id}] / `POST /tasks/{id}/recall`

## 7. 错误与兜底
- 找不到方案/任务：提示有效列表；
- 未通过证据化门槛（资源/KG/RAG不足）的方案：拒绝“dispatch”，仅允许“approve(requires补齐)”或“reject”。

## 8. 验收KPI
- few‑shot≥20；F1≥0.95；确认命中率100%；
- 变更可回放（时间线含版本与决策者）。
