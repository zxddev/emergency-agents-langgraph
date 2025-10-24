# Capability: Java API Contract (TODO-only)

## ADDED Requirements
### Requirement: Documented request/response contracts without implementation
The system MUST provide request/response examples for Java APIs without implementing them at this stage. Endpoints include: POST /events, POST /annotations, POST /annotations/{id}/sign, POST /plans, POST /tasks/bulk, GET /routes, GET /safe-points, GET /devices/status, POST /control/robotdog/command, POST /rfa, POST /evidence/bookmark, GET /evidence/playback.

#### Scenario: Create an event (example)
Input: Event JSON {event_type, title, lat, lng, severity, description, parent_event_id}.
Action: Provide example request/response payloads.
Expected: Contract is documented for integration, but not executed in demo.
