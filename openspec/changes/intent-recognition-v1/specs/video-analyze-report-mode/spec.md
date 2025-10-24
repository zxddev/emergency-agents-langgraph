# Capability: Video Analyze (Report-First Mode)

## ADDED Requirements
### Requirement: Report-first candidate annotations without realtime video dependency
The system MUST prefer report-driven analysis; realtime WebRTC is optional for demo and not required; it MUST accept expert-reported findings (voice/text) and create candidate annotations as PENDING for human sign.

#### Scenario: Expert reports trapped individuals
Input: "某处发现两名被困群众。"
Action: Create PENDING candidate annotation or trapped_report entity.
Expected: Requires human sign; after SIGNED, render on map.
