# Capability: Event Update

## ADDED Requirements
### Requirement: New and secondary events with mapping and tree linkage
The system MUST support creating new events with optional parent_event_id to model sub/secondary disasters; events MUST be mapped on 3D with geometry Point or Polygon and properties {type,severity,title,description,parent_event_id,status}.

#### Scenario: Create a secondary event
Input: "在主事件下新增道路阻断，坐标31.70,103.90。"
Action: Create event with parent_event_id; set status=active.
Expected: Event appears on map and is linked to the parent in event tree.
