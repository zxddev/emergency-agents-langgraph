# Capability: Map Layers

## ADDED Requirements
### Requirement: WGS84+GeoJSON layers with ≤2s render after sign/confirm
The system MUST follow WGS84 + GeoJSON across layers; layers MUST include annotations, uav_tracks, routes, safe_points, events, tasks with prescribed properties; and rendering MUST occur within ≤2s after SIGNED or confirmed report (demo KPI).

#### Scenario: Render signed annotation
Input: An annotation transitions to SIGNED.
Action: Push to map renderer.
Expected: Appears within ≤2s with correct properties.
