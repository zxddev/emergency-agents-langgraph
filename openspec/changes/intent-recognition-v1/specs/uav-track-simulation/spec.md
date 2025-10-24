# Capability: UAV Track Simulation

## ADDED Requirements
### Requirement: LineString generation with defaults and timeline event
The system MUST generate a LineString track from current fleet position to the target (point/route/area centroid) with default steps=20 and alt_m=80 unless overridden; and it MUST record a timeline event `uav_track_generated` including metadata {track_id, alt_m, steps, generated_at}.

#### Scenario: Generate line to area centroid
Input: "对该区域进行扫图。"
Action: Compute centroid; create LineString; set properties {alt_m:80, steps:20}.
Expected: Track rendered; timeline updated.
