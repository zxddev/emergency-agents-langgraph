# Capability: Recon Minimal (Plan/Point/Route Unified)

## ADDED Requirements
### Requirement: Unified recon with simulated UAV track and timeline
The system MUST support a unified recon intent covering area (plan), point, and route forms; UAV execution MUST be simulated as a GeoJSON LineString track (no real flight control) with properties {alt_m, steps}; and timeline MUST include an event `uav_track_generated` with metadata {track_id, alt_m, steps, generated_at}.

#### Scenario: Point observation
Input: "到A点定点观察，高五十米。"
Action: Generate a LineString from fleet position to the target point, with alt_m=50 (default override) and steps=20.
Expected: Track appears on map; timeline event recorded.
