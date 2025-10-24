# Capability: Robotdog Control

## ADDED Requirements
### Requirement: Confirmed control for move/turn/goto and immediate e_stop
The system MUST support actions: `move`, `turn`, `head`, `goto`, `stop`, `e_stop`; actions `move|turn|goto` MUST require explicit human confirmation before execution; `e_stop` MUST be accepted immediately without confirmation; parameters MUST be validated (distance/angle/range) and out-of-range inputs MUST trigger readback corrections.

#### Scenario: Move and turn require confirmation
Input: "前进三米，向右转九十度。"
Action: Parse actions; set need_confirm=true; produce readback asking for confirmation.
Expected: No execution before confirmation; after confirm, command is dispatched (Java API is TODO-only in this phase).

#### Scenario: Emergency stop
Input: "急停！"
Action: Accept immediately.
Expected: Immediate acceptance and readback "已下发急停指令。"
