# Capability: RFA (Resource/Augmentation Request)

## ADDED Requirements
### Requirement: Structured RFA entries with readback and alternatives
The system MUST allow creating RFA entries with unit_type, count, equipment[], priority, and window; readback MUST confirm the ask and include basic ETA assumptions or alternatives when resources are insufficient.

#### Scenario: Request engineering teams
Input: "请求工程队两支，含100吨吊车一台，优先级高。"
Action: Extract slots; create RFA entry; readback.
Expected: Entry created with HIGH priority; readback with concise summary.
