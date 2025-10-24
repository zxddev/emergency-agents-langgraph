# Capability: Intent Routing

## ADDED Requirements
### Requirement: Intent routing with unified schema and HITL
The system MUST output a unified IntentResult (intent_type, slots, meta) per `prd/intent/common-schema.md`; MUST validate slots via jsonschema and trigger readback when required slots are missing; MUST require explicit human confirmation for high‑risk actions (meta.need_confirm=true); and MUST route intents to the appropriate Agent via the LangGraph "intent router" with HITL interrupt support.

#### Scenario: Route a robotdog control command with confirmation
Input: "前进三米，向右转九十度。"
Action: LLM few‑shot classifies to device_control_robotdog; slots extracted {action:move, distance_m:3} & {action:turn, angle_deg:90}; meta.need_confirm=true.
Expected: Router creates a readback "将执行机器狗动作：... 请确认" and waits for confirm; no execution before confirmation.

#### Scenario: Route a trapped report to Situation group
Input: "在水磨镇坐标31.68,103.85发现被困群众十人。"
Action: Classify to trapped_report; slots {lat,lng,count}; validate schema; route to reporting agent.
Expected: Create PENDING entity for mapping; ready for further planning.
