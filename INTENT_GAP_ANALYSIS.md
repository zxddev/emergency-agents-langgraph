# 意图实现缺口分析报告

**分析时间**: 2025-11-02
**分析对象**: emergency-agents-langgraph 意图系统
**数据来源**: `src/emergency_agents/intent/schemas.py` vs `src/emergency_agents/intent/registry.py`

---

## 概览

- **已定义Schema**: 22个独立意图类型
- **已实现Handler**: 10个意图类型
- **实现率**: 45% (10/22)
- **缺失Handler**: 12个意图类型

---

## 已实现的意图 (10个) ✅

| # | 意图类型 | 槽位Schema | Handler | 状态 |
|---|----------|-----------|---------|------|
| 1 | **rescue-task-generate** | RescueTaskGenerationSlots | RescueTaskGenerationHandler | ✅ 完整 |
| 2 | **rescue-simulation** | RescueTaskGenerationSlots | RescueSimulationHandler | ✅ 完整 |
| 3 | **scout-task-generate** | ScoutTaskGenerationSlots | ScoutTaskGenerationHandler | ✅ 新增 |
| 4 | **task-progress-query** | TaskProgressQuerySlots | TaskProgressQueryHandler | ✅ 完整 |
| 5 | **location-positioning** | LocationPositioningSlots | LocationPositioningHandler | ✅ 完整 |
| 6 | **device-control** | DeviceControlSlots | DeviceControlHandler | ✅ 完整 |
| 7 | **device-control-robotdog** | DeviceControlRobotdogSlots | DeviceControlHandler | ✅ 特殊 |
| 8 | **video-analysis** | VideoAnalysisSlots | VideoAnalysisHandler | ✅ 完整 |
| 9 | **ui-camera-flyto** | UICameraFlytoSlots | UIControlHandler | ✅ 完整 |
| 10 | **ui-toggle-layer** | UIToggleLayerSlots | UIControlHandler | ✅ 完整 |

---

## 缺失的意图 (12个) ❌

### 高优先级（核心业务功能）- 5个

| # | 意图类型 | 槽位Schema | 业务价值 | 推荐优先级 |
|---|----------|-----------|---------|----------|
| 1 | **trapped_report** | TrappedReportSlots | 被困人员报告（核心救援场景） | 🔴 P0 |
| 2 | **hazard_report** | HazardReportSlots | 灾情报告（态势感知基础） | 🔴 P0 |
| 3 | **event_update** | EventUpdateSlots | 事件更新（状态同步） | 🟠 P1 |
| 4 | **plan_task_approval** | PlanTaskApprovalSlots | 方案审批（人工介入） | 🟠 P1 |
| 5 | **rfa_request** | RfaRequestSlots | 资源/增援请求（调度核心） | 🟡 P2 |

**说明**:
- **trapped_report**: 用户报告被困人员位置和数量，是救援的起点
- **hazard_report**: 灾情上报，态势感知的数据来源
- **event_update**: 更新事件状态，保持系统信息同步
- **plan_task_approval**: 支持人工审批救援方案，符合LangGraph中断点设计
- **rfa_request**: 请求额外资源或增援，调度系统的输入

### 中优先级（辅助功能）- 4个

| # | 意图类型 | 槽位Schema | 业务价值 | 推荐优先级 |
|---|----------|-----------|---------|----------|
| 6 | **device_status_query** | DeviceStatusQuerySlots | 设备状态查询 | 🟡 P2 |
| 7 | **route_safe_point_query** | RouteSafePointQuerySlots | 路线规划查询 | 🟡 P2 |
| 8 | **geo_annotate** | GeoAnnotateSlots | 地图标注 | 🟢 P3 |
| 9 | **video_analyze** | VideoAnalyzeSlots | 视频报告分析（与video-analysis不同） | 🟢 P3 |

**说明**:
- **device_status_query**: 查询设备电量、状态等
- **route_safe_point_query**: 查询到达某地的最佳路线和安全点
- **geo_annotate**: 在地图上标注重要位置
- **video_analyze**: 基于报告文本的视频分析（区别于实时流分析）

### 低优先级（边缘功能）- 3个

| # | 意图类型 | 槽位Schema | 业务价值 | 推荐优先级 |
|---|----------|-----------|---------|----------|
| 10 | **recon_minimal** | ReconMinimalSlots | 最小化侦察（简化版） | 🟢 P3 |
| 11 | **annotation_sign** | AnnotationSignSlots | 标注签收 | 🟢 P3 |
| 12 | **evidence_bookmark_playback** | EvidenceBookmarkPlaybackSlots | 证据回放 | 🟢 P3 |
| 13 | **conversation_control** | ConversationControlSlots | 对话管控 | 🟢 P3 |

**说明**:
- **recon_minimal**: 简化版侦察（scout-task-generate更完整）
- **annotation_sign**: 标注确认/签收流程
- **evidence_bookmark_playback**: 视频证据管理
- **conversation_control**: 对话流程控制（清空、重置等）

---

## Schema定义但未使用的意图

以下意图在`INTENT_SCHEMAS`中定义，但在任何路由或Handler中都未使用：

```python
# schemas.py:345-371
INTENT_SCHEMAS = {
    "recon_minimal": ...,              # ❌ 未使用
    "device_control_robotdog": ...,    # ✅ 已使用（device-control-robotdog）
    "trapped_report": ...,             # ❌ 未使用
    "hazard_report": ...,              # ❌ 未使用
    "route_safe_point_query": ...,     # ❌ 未使用
    "device_status_query": ...,        # ❌ 未使用
    "geo_annotate": ...,               # ❌ 未使用
    "annotation_sign": ...,            # ❌ 未使用
    "plan_task_approval": ...,         # ❌ 未使用
    "rfa_request": ...,                # ❌ 未使用
    "event_update": ...,               # ❌ 未使用
    "video_analyze": ...,              # ❌ 未使用
    "evidence_bookmark_playback": ..., # ❌ 未使用
    "conversation_control": ...,       # ❌ 未使用
}
```

---

## 实现建议

### Phase 1: 核心业务意图 (P0-P1, 建议2周)

**目标**: 支持完整的灾情上报→救援响应流程

1. **trapped_report** (3天)
   - Handler: 解析被困信息 → 创建救援任务 → 推送到前端
   - 集成: 可触发rescue-task-generate

2. **hazard_report** (3天)
   - Handler: 解析灾情 → 更新态势感知 → 风险评估
   - 集成: 写入Neo4j知识图谱，触发风险预测

3. **event_update** (2天)
   - Handler: 更新事件状态 → 同步数据库 → 通知订阅者
   - 集成: 更新PostgreSQL事件表

4. **plan_task_approval** (3天)
   - Handler: 解析审批决策 → 更新方案状态 → 继续/拒绝执行
   - 集成: 与LangGraph interrupt点配合

5. **rfa_request** (2天)
   - Handler: 解析资源需求 → 资源匹配 → 调度分配
   - 集成: 调用orchestrator_client

### Phase 2: 辅助功能意图 (P2-P3, 建议1周)

6. **device_status_query** (1天)
   - Handler: 查询设备DAO → 返回状态信息

7. **route_safe_point_query** (2天)
   - Handler: 调用AmapClient → 返回路线和安全点

8. **geo_annotate** (1天)
   - Handler: 保存标注到数据库 → 推送到前端

9. **video_analyze** (2天)
   - Handler: 基于报告文本分析视频片段

### Phase 3: 边缘功能 (P3, 可选)

10-13. recon_minimal, annotation_sign, evidence_bookmark_playback, conversation_control

---

## 技术债务分析

### 1. 命名不一致问题

**问题**: schemas.py使用下划线，orchestrator/registry使用短横线

```python
# schemas.py
"trapped_report"
"hazard_report"

# 实际路由应该是
"trapped-report"
"hazard-report"
```

**影响**: 路由匹配失败，需要归一化处理
**建议**: 统一使用短横线命名，schemas.py同步更新

### 2. Schema定义冗余

**问题**: INTENT_SCHEMAS和INTENT_SLOT_TYPES重复定义

```python
# schemas.py:345-371
INTENT_SCHEMAS = {...}  # 26个schema

# schemas.py:381-407
INTENT_SLOT_TYPES = {...}  # 23个类型映射
```

**建议**: 合并或明确职责分工

### 3. 高风险意图未完全对接

```python
# schemas.py:374-378
HIGH_RISK_INTENTS = {
    "device_control_robotdog",  # ✅ 已实现
    "plan_task_approval",       # ❌ 未实现
    "rescue_task_generate",     # ✅ 已实现
}
```

**风险**: plan_task_approval未实现，但被标记为高风险意图

---

## 快速实施指南

### 实现新意图的标准流程

#### 1. 定义Handler (src/emergency_agents/intent/handlers/xxx.py)
```python
@dataclass
class TrappedReportHandler(IntentHandler[TrappedReportSlots]):
    dao: SomeDAO

    async def handle(self, slots: TrappedReportSlots, state: Dict) -> Dict:
        # 业务逻辑
        return {"result": ...}
```

#### 2. 注册到Registry (src/emergency_agents/intent/registry.py)
```python
handlers = {
    "trapped-report": TrappedReportHandler(dao),
}
```

#### 3. 添加路由 (src/emergency_agents/graph/intent_orchestrator_app.py)
```python
route_map = {
    "trapped-report": "trapped-report",
}
```

#### 4. 编写测试 (tests/intent/test_xxx_handler.py)
```python
@pytest.mark.integration
async def test_trapped_report_handler():
    handler = TrappedReportHandler(...)
    result = await handler.handle(slots, state)
    assert result["status"] == "success"
```

#### 5. 更新文档
- 更新本文档的"已实现"列表
- 在业务文档中记录新功能

---

## 统计数据

### 按优先级分布
- **P0 (紧急)**: 2个 (trapped_report, hazard_report)
- **P1 (高)**: 2个 (event_update, plan_task_approval)
- **P2 (中)**: 3个 (rfa_request, device_status_query, route_safe_point_query)
- **P3 (低)**: 5个 (geo_annotate, video_analyze, recon_minimal, annotation_sign, evidence_bookmark_playback, conversation_control)

### 实现进度
```
已实现:  ████████████████████░░░░░░░░░░░░░░░░░░░░  45% (10/22)
P0未实现: ░░                                      2个
P1未实现: ░░                                      2个
P2未实现: ░░░                                     3个
P3未实现: ░░░░░                                   5个
```

### 业务覆盖率
- **救援流程**: 60% (rescue-task-generate ✅, rescue-simulation ✅, trapped_report ❌)
- **侦察流程**: 50% (scout-task-generate ✅, recon_minimal ❌)
- **设备控制**: 100% (device-control ✅, video-analysis ✅)
- **任务管理**: 50% (task-progress-query ✅, plan_task_approval ❌)
- **态势感知**: 0% (hazard_report ❌, event_update ❌)

---

## 参考资料

- **Schema定义**: `src/emergency_agents/intent/schemas.py`
- **Handler实现**: `src/emergency_agents/intent/handlers/`
- **路由配置**: `src/emergency_agents/graph/intent_orchestrator_app.py`
- **Registry注册**: `src/emergency_agents/intent/registry.py`

---

**报告生成时间**: 2025-11-02
**分析人**: Claude Code
**下次更新**: 实现新意图后及时更新本文档
