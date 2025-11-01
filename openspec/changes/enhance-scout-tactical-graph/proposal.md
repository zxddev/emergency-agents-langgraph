# Proposal: 开发战术侦察子图

## Why

当前 `ScoutTacticalGraph` 仅实现了基础的目标生成和情报需求汇总，缺失关键的设备调度、航线规划、传感器分配等核心节点，无法支撑完整的侦察任务流程。需要重构为完整的 LangGraph StateGraph 工作流，实现从意图识别到前端可视化的完整业务闭环，满足峰会演示要求。

## What Changes

- 重构 `ScoutTacticalState` 为 `Required`/`NotRequired` 强类型定义
- 将 `ScoutTacticalGraph` 从 `@dataclass` 重构为 LangGraph StateGraph 模式（8个节点）
- 新增 `device_selection` 节点（设备筛选和评分）
- 新增 `recon_route_planning` 节点（圆形/网格航点生成）
- 新增 `sensor_payload_assignment` 节点（传感器任务分配）
- 新增 `risk_overlay` 节点（航点风险检测）
- 新增 `persist_task` 节点（保存 ScoutTask 到数据库）
- 新增 `prepare_response` 节点（生成 UI Actions）
- 新增 `ws_notify` 节点（推送到 Java 后台）
- 扩展 `OrchestratorClient` 添加 `publish_scout_scenario` 方法
- 定义 `ScoutTask` 数据模型和 `scout_task` 数据库表

## Impact

- Affected specs: `device-selection`, `route-planning`, `sensor-payload`, `entity-persistence`, `ui-actions` (全部新增)
- Affected code: `src/emergency_agents/graph/scout_tactical_app.py` (完全重构), `src/emergency_agents/db/models.py` (新增 ScoutTask), `src/emergency_agents/db/dao.py` (新增 ScoutTaskRepository), `src/emergency_agents/external/orchestrator_client.py` (扩展方法)
- 数据库变更: 新增 `scout_task` 表
- 外部依赖: 需要对接资产管理系统（AssetManagementClient）获取设备状态

---

**创建时间**: 2025-11-02
**状态**: DRAFT
