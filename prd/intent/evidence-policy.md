# 证据化策略（Evidence Policy）

## 目标
- 防止“AI随便编”。救援方案/任务的自动“下发”必须满足以下证据门槛，否则仅输出“建议”并要求审定。

## 准入门槛
1) 资源可用性检查：
   - 单位/人数/ETA/装备配比需满足最低要求；
   - 缺口→自动触发RFA建议（但不得下发）。
2) KG匹配（Neo4j）：
   - REQUIRES/TRIGGERS/COMPOUNDS 命中条数 ≥ 3；
   - 返回关系ID/属性（probability/urgency…）。
3) RAG案例（Qdrant）：
   - 相似案例引用条数 ≥ 2（case_id/title/summary/source/url/similarity）。

## 违反处理
- 任一不满足：禁止“dispatch”；仅允许“approve(备注补证据)”或“reject”。

## 记录与审计
- 每份方案需携带 evidence[]：
  - resources: 单位/装备与ETA快照
  - kg: 三条以上的关系与属性
  - cases: 至少两条案例引用

## 验收
- 随机抽样10份方案，100%遵循门槛；
- openspec/specs 交叉引用至 rescue_task_generate 与 plan_task_approval。
