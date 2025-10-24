# Capability: Device Status Query

## ADDED Requirements
### Requirement: Device status queries with unified readback and clarification
The system MUST support natural-language device status queries for `uav` and `robotdog`; MUST support metrics: `battery`, `position`, `link`, `temperature`, `presence`; when `device_id` is missing and multiple devices exist, it MUST prompt clarification; and readback MUST follow a unified format (e.g., "uav#A 电量78%，位置(103.85,31.68)，链路良好").

#### Scenario: Query UAV battery and position
Input: "无人机电量和位置？"
Action: Classify to device-status; metrics=battery,position; device_type=uav; prompt if multiple IDs; readback unified.
Expected: A single sentence includes battery% and coordinates; if multiple devices, a clarification question precedes the final readback.
