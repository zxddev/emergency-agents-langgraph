# Capability: Rescue Task Generate

## ADDED Requirements
- Requirement: The system MUST generate rescue plans and tasks from confirmed reports/annotations with explicit HITL approval before dispatch.
- Requirement: Dispatch MUST pass the Evidence Policy gate (resources check + KG≥3 + RAG≥2), otherwise dispatch MUST be blocked and only suggestion allowed.
- Requirement: The system MUST log an explicit confirmation "READY TO CALL JAVA API" before any third-party integration (all external calls remain TODO in this phase).

#### Scenario: Generate plan and tasks from trapped report
Input: Confirmed trapped_report {lat,lng,count=10}.
Action: Propose a plan with units/equipment and produce tasks with geometry; evaluate evidence; log readiness for Java before any external call.
Expected: If evidence passes, plan can be approved and dispatched; otherwise only suggested with rationale.
