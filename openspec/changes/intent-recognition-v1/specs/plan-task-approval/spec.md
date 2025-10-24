# Capability: Plan/Task Approval (HITL)

## ADDED Requirements
### Requirement: HITL approval/dispatch/recall with evidence gate and audit
The system MUST support human-in-the-loop approval, dispatch, and recall of plans and tasks, with versioning and diff summaries; dispatch MUST obey the Evidence Policy gate and be blocked with explanation when unmet; and audit trail MUST record approver, action, timestamp, and diffs, and be replayable.

#### Scenario: Approve and dispatch a plan
Input: "批准主方案并下发。"
Action: Validate evidence gate; if passed, change plan status; create dispatch records; persist version and diff.
Expected: Plan moves to dispatched state; audit trail recorded; rejection if evidence gate fails.
