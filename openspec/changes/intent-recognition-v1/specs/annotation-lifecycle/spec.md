# Capability: Annotation Lifecycle

## ADDED Requirements
### Requirement: Annotation PENDING→SIGNED/REJECTED with ≤2s render
The system MUST support geo_annotate to create PENDING annotations (Point/LineString/Polygon + label + evidence + confidence); MUST support annotation_sign to transition PENDING → SIGNED or REJECTED; and AFTER SIGNED it MUST render on the map within ≤2s (demo KPI).

#### Scenario: Create and sign an annotation
Input: "把桥头标注为道路阻断。"
Action: Create PENDING annotation at provided geometry; readback confirmation.
Expected: After "签收标注X" the status changes to SIGNED and is rendered on map within ≤2s.
