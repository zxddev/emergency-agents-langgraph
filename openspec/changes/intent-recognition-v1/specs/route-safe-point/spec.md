# Capability: Route & Safe Points

## ADDED Requirements
### Requirement: Routing (best/fastest/safest) and nearest safe points with difference readback
The system MUST support querying best/fastest/safest route to a destination and nearest safe points; and SHOULD provide a difference explanation in readback (e.g., safer avoids N risk segments, +time%).

#### Scenario: Query safest route
Input: "规划到31.68,103.85的最安全路线。"
Action: Generate demo candidates; readback differences; map user selection.
Expected: Route rendered as GeoJSON LineString; properties include policy and cost breakdown.
