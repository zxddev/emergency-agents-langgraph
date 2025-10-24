# Capability: Evidence Policy (Gate)

## ADDED Requirements
### Requirement: Evidence gate for dispatch with resource/KG/RAG thresholds
Dispatching a rescue plan/task MUST require all of: resource availability check, KG hits (≥3 across REQUIRES/TRIGGERS/COMPOUNDS), and RAG case references (≥2); otherwise it MUST be blocked and only "suggest" allowed. Evidence array MUST contain snapshots of resources, KG relation IDs with attributes, and RAG case entries (id/title/summary/source/url/similarity).

#### Scenario: Insufficient evidence blocks dispatch
Input: Attempt to dispatch a plan with KG=1 and RAG=1.
Action: Evaluate gate.
Expected: Dispatch is rejected with reason, plan remains in approvable state pending evidence completion.
