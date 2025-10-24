# Capability: Report Intake (Trapped & Hazard)

## ADDED Requirements
### Requirement: Report‑driven intake for trapped and hazard with geocoding prompt
The system MUST support report-driven intake without video: `trapped_report` and `hazard_report`; MUST extract required slots (trapped: lat/lng or location_text, count, time_reported, description; hazard: event_type, lat/lng or location_text, severity, time_reported, description, parent_event_id?); and when coordinates are missing, it SHOULD prompt to confirm geocoding from location_text.

#### Scenario: Trapped report with coordinates
Input: "在水磨镇坐标31.68,103.85发现被困群众十人。"
Action: Extract lat,lng=31.68,103.85, count=10; create entity PENDING; map on 3D.
Expected: Entity ready for rescue planning; response readback confirms details.

#### Scenario: Hazard report with missing coords
Input: "XX乡发生山体滑坡。"
Action: Extract event_type=landslide; missing coords; prompt "是否采用XX乡解析为(…, …)?".
Expected: After confirmation, create event ACTIVE and map it.
