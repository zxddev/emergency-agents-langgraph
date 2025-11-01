# 子图开发状态矩阵（规划vs实际代码）

**生成日期**: 2025-11-02
**对比基准**: `子图体系开发规划.md` vs 实际代码库
**分析方法**: 逐条核对规划文档中的子图，确认实现状态

---

## 1. Phase 0（共性基座）- 完成度分析

| 模块 | 规划要求 | 实际状态 | 代码位置 | 完成度 |
|------|---------|---------|---------|--------|
| **数据模型与DAO** | 统一强类型模型 | ✅ 已实现 | `db/models.py`<br>`db/dao.py` | 90% |
| **UI Action协议** | 统一JSON schema | ⚠️ 部分实现 | 各Handler零散返回 | 40% |
| **LLM客户端工厂** | 独立模型选择 | ⚠️ 未实现 | 规划提到但代码未见 | 0% |
| **日志与指标** | 统一structlog + Prometheus | ✅ 已实现 | `logging.py` (Phase0新增) | 100% |
| **模拟器与事件通道** | 复用Adapter Hub | ✅ 已实现 | `external/adapter_client.py` | 100% |

**Phase 0 总体完成度**: ~66%

**遗留问题**:
1. ❌ **UI Action协议未统一** - 各Handler自行定义ui_actions格式
2. ❌ **LLM客户端工厂未实现** - 规划提到`llm/factory.py`但代码库不存在
3. ⚠️ **DAO部分模型缺失** - 如`ScoutTask`模型未定义

---

## 2. 战术层子图 - 实现状态

### 2.1 战术救援子图（RescueTacticalGraph）

| 规划项 | 规划状态 | 实际状态 | 证据 |
|-------|---------|---------|------|
| **入口意图** | `RESCUE_TASK_GENERATION` | ✅ 已实现 | `intent/handlers/rescue_task_generation.py` |
| **关键节点** | | | |
| └ resolve_location | 高德逆地理 | ✅ 已实现 | `rescue_tactical_app.py:122-129` (@task包装) |
| └ kg_requirement_lookup | KGService查询 | ✅ 已实现 | `rescue_tactical_app.py` (调用KGService) |
| └ rag_case_retrieval | RagPipeline检索 | ✅ 已实现 | `rescue_tactical_app.py:193-210` (@task包装) |
| └ resource_matcher | 推荐队伍装备 | ✅ 已实现 | `rescue_tactical_app.py` |
| └ route_planning | 高德路径+风险避险 | ✅ 已实现 | `rescue_tactical_app.py:132-148` (@task包装) |
| **输出结构** | rescue_task + routes + ui_actions | ✅ 已实现 | Handler返回完整结构 |
| **外部依赖** | Orchestrator/Amap/KG/RAG | ✅ 已集成 | `external/` 目录 |
| **必备日志** | rescue_task_completed等 | ✅ 已实现 | structlog日志已添加 |
| **待办项** | | | |
| └ 实体落库接口 | 待实现 | ⚠️ 通过Snapshot间接实现 | `RescueDraftService.save_draft()` |
| └ 本地链路UI动作 | 待实现 | ⚠️ 部分实现 | 各Handler零散返回 |
| └ 任务确认REST | 待实现 | ✅ 已完成（文档未更新） | `api/rescue.py:69-93` |
| └ 风险提醒落地 | 待实现 | ✅ 已完成（后台运行） | `RiskPredictor` |

**战术救援完成度**: ~85%

**核心问题**:
- ❌ State使用`total=False`（违反强类型要求）
- ⚠️ UI Actions未统一返回
- ⚠️ 实体写库需要直接接口（目前通过Snapshot）

### 2.2 战术侦察子图（ScoutTacticalGraph）

| 规划项 | 规划状态 | 实际状态 | 证据 |
|-------|---------|---------|------|
| **入口意图** | `SCOUT_TASK_GENERATION` | ✅ 已实现 | `intent/handlers/scout_task_generation.py` |
| **关键节点** | | | |
| └ device_selection | 筛选可用设备 | ❌ 未实现 | 规划提到但代码缺失 |
| └ recon_route_planning | 生成巡航Waypoints | ❌ 未实现 | 规划提到但代码缺失 |
| └ sensor_payload_assignment | 分配传感器任务 | ❌ 未实现 | 规划提到但代码缺失 |
| └ intel_requirement_builder | 汇总情报需求 | ✅ 基础实现 | `scout_tactical_app.py:125-145` |
| └ risk_overlay | 引用风险区域 | ✅ 已实现 | `scout_tactical_app.py:79-96` |
| **输出结构** | scout_plan + ui_actions | ✅ 基础实现 | `scout_tactical_app.py:33-39` |
| **外部依赖** | 设备资产表/高德/风险缓存 | ⚠️ 部分依赖 | 风险缓存已有，设备资产表未用 |
| **现状评价** | 基础骨架 | ✅ 符合描述 | "基于风险区域生成目标" |
| **待办项** | | | |
| └ ScoutTask模型 | 待定义 | ❌ 未实现 | 代码中未见 |
| └ 设备状态同步 | 待实现 | ❌ 未实现 | 代码中未见 |
| └ 前端侦察面板 | 待实现 | ⚠️ 前端任务 | AI项目范围外 |

**战术侦察完成度**: ~30%

**待开发节点**:
1. ❌ `device_selection` - 筛选可用无人机/机器人
2. ❌ `recon_route_planning` - 巡航航线生成
3. ❌ `sensor_payload_assignment` - 传感器任务分配

---

## 3. 控制层子图 - 实现状态

### 3.1 语音设备控制处理器（VoiceControlHandler）

| 规划项 | 规划要求 | 实际状态 | 证据 |
|-------|---------|---------|------|
| **实现方式** | Handler/Agent，无需LangGraph | ✅ 符合 | `intent/handlers/device_control.py` |
| **入口意图** | `DEVICE_CONTROL_VOICE` | ✅ 已实现 | DeviceControlHandler |
| **核心功能** | | | |
| └ 解析Slot | 校验设备/权限 | ✅ 已实现 | `device_control.py:26-51` |
| └ 下发指令 | Adapter Hub | ✅ 已实现 | `device_control.py:87-114` |
| └ 同步等待Ack | 返回control_events | ✅ 已实现 | `device_control.py:115-135` |
| └ 失败直接抛错 | 禁止兜底 | ✅ 符合 | 无降级逻辑 |
| **输出结构** | control_events + ui_actions | ✅ 已实现 | Handler返回完整结构 |
| **专用控制** | 机器狗专用Handler | ✅ 已实现 | `RobotDogControlHandler` |
| **必备日志** | device_control_issued等 | ✅ 已实现 | `device_control.py:88-125` |

**语音设备控制完成度**: ~95%

**超出规划的实现**:
- ✅ 通用设备控制 + 机器狗专用（规划只提机器狗）
- ✅ 完整的错误处理和日志

---

## 4. 战略层子图 - 实现状态

### 4.1 战略侦察规划（StrategicReconGraph）

| 规划项 | 规划状态 | 实际状态 |
|-------|---------|---------|
| **触发方式** | REST调用/调度 | ❌ 未实现 |
| **输入** | Incident快照/战术结果 | ❌ 未实现 |
| **输出** | strategic_recon_plan | ❌ 未实现 |
| **依赖** | Snapshot DAO/RAG/KG | ⚠️ 基础设施已有 |

**完成度**: 0%

### 4.2 战略救援规划（StrategicRescueGraph）

| 规划项 | 规划状态 | 实际状态 | 备注 |
|-------|---------|---------|------|
| **触发方式** | REST/调度 | ⚠️ 可能已有替代 | `/ai/plan/recommend` API |
| **输入** | 任务进度/资源占用 | ⚠️ 可能已有替代 | `/ai/plan/*` 系统 |
| **输出** | strategic_rescue_plan | ⚠️ 可能已有替代 | `PlanRecommendResponse` |

**完成度**: ~50%（如果复用`/ai/plan/*`）

**关键问题**:
- ⚠️ 文档规划的"战略救援规划"与实际的`/ai/plan/*` API功能重叠
- 需要确认：是否需要新开发，还是复用现有系统？

### 4.3 态势上报（SITREPGraph）

| 规划项 | 规划状态 | 实际状态 |
|-------|---------|---------|
| **触发方式** | 定时任务/手动 | ❌ 未实现 |
| **输入** | 快照/事件/进度 | ❌ 未实现 |
| **输出** | sitrep_report | ❌ 未实现 |

**完成度**: 0%

### 4.4 行动评估（PostActionAssessmentGraph）

| 规划项 | 规划状态 | 实际状态 |
|-------|---------|---------|
| **触发方式** | 手动请求 | ❌ 未实现 |
| **输入** | 任务完成情况 | ❌ 未实现 |
| **输出** | 评估报告 | ❌ 未实现 |

**完成度**: 0%

---

## 5. 风险与安全子图 - 实现状态

### 5.1 风险预测子图（RiskPredictionGraph）

| 规划项 | 规划状态 | 实际状态 | 证据 |
|-------|---------|---------|------|
| **触发方式** | 定时5分钟/事件驱动 | ✅ 已实现（后台服务） | `main.py:407-413` |
| **流程** | 数据采集→评分→写入 | ✅ 已实现 | `RiskPredictor.run_periodic()` |
| **输出** | 写入risk_zones | ✅ 已实现 | `RiskCacheManager` |
| **必备日志** | risk_assessment_* | ✅ 已实现 | 后台服务日志 |

**完成度**: ~90%（后台服务替代子图）

**实现方式差异**:
- 规划：独立LangGraph子图
- 实际：`RiskPredictor`后台服务 + `RiskCacheManager`缓存
- **评价**: 实际实现更高效（无需LangGraph开销）

### 5.2 路线风险提醒子图（RouteRiskGuard）

| 规划项 | 规划状态 | 实际状态 | 证据 |
|-------|---------|---------|------|
| **触发方式** | 路径规划调用 | ⚠️ 嵌入式实现 | rescue_tactical_app中有风险逻辑 |
| **功能** | 对比路线与风险区域 | ⚠️ 部分实现 | 需要确认代码细节 |
| **输出** | route_warnings | ⚠️ 部分实现 | Handler中有warnings字段 |

**完成度**: ~50%（嵌入式实现，非独立子图）

**实现方式差异**:
- 规划：独立子图
- 实际：在`rescue_tactical_app`的`route_planning`节点内处理
- **评价**: 嵌入式实现可能更合理（避免过度拆分）

### 5.3 位置监控子图（TeamMonitorGraph）

| 规划项 | 规划状态 | 实际状态 |
|-------|---------|---------|
| **触发方式** | WebSocket监听 | ❌ 未实现 |
| **功能** | 位置监控+预警 | ❌ 未实现 |
| **输出** | ui_actions | ❌ 未实现 |

**完成度**: 0%

---

## 6. 群众安置与补给子图 - 实现状态

### 6.1 安置点推荐（ShelterRecommendationGraph）

| 规划项 | 规划状态 | 实际状态 |
|-------|---------|---------|
| **输入** | 风险区域/避难所 | ❌ 未实现 |
| **输出** | shelter_plan | ❌ 未实现 |

**完成度**: 0%

### 6.2 补给任务规划（SupplyMissionGraph）

| 规划项 | 规划状态 | 实际状态 |
|-------|---------|---------|
| **输入** | 库存/需求/风险 | ❌ 未实现 |
| **输出** | supply_missions | ❌ 未实现 |

**完成度**: 0%

---

## 7. 总体完成度统计

### 7.1 按阶段统计

| 阶段 | 子图/模块数 | 已完成 | 部分完成 | 未开始 | 完成度 |
|------|-----------|--------|---------|--------|--------|
| **Phase 0（基座）** | 5 | 3 | 2 | 0 | 66% |
| **Phase 1A（战术救援）** | 1 | 0 | 1 | 0 | 85% |
| **Phase 1B（战术侦察）** | 1 | 0 | 1 | 0 | 30% |
| **控制层** | 1 | 1 | 0 | 0 | 95% |
| **Phase 2（战略层）** | 4 | 0 | 1 | 3 | 12% |
| **风险与安全** | 3 | 1 | 1 | 1 | 47% |
| **群众安置与补给** | 2 | 0 | 0 | 2 | 0% |
| **总计** | 17 | 5 | 6 | 6 | **45%** |

### 7.2 按优先级统计

| 优先级 | 功能数 | 已完成 | 待开发 |
|-------|--------|--------|--------|
| **P0（关键）** | 7 | 4 | 3 |
| **P1（重要）** | 6 | 2 | 4 |
| **P2（可选）** | 4 | 0 | 4 |

---

## 8. 真实待开发清单（按优先级）

### P0（立即开始）- 规划明确要求的核心功能

#### 1. 战术侦察子图完善 ⭐⭐⭐
**代码位置**: `graph/scout_tactical_app.py`

**待开发节点**:
```python
# 需要新增的3个节点
1. device_selection(state: ScoutTacticalState) -> Dict[str, Any]:
   """筛选可用无人机/机器人"""
   # - 查询设备资产表（Adapter Hub）
   # - 结合设备状态、能力标签
   # - 返回: selected_devices: List[DeviceInfo]

2. recon_route_planning(state: ScoutTacticalState) -> Dict[str, Any]:
   """生成巡航Waypoints"""
   # - 基于目标周边生成航线
   # - 沿道路/河道/楼层
   # - 返回: waypoints: List[Coordinate]

3. sensor_payload_assignment(state: ScoutTacticalState) -> Dict[str, Any]:
   """分配传感器任务"""
   # - 相机/红外/气体检测
   # - 返回: payload_assignments: List[SensorTask]
```

**State定义修复** (必须同步):
```python
# ❌ 当前错误
class ScoutTacticalState(TypedDict, total=False):
    incident_id: str
    # ...

# ✅ 正确模式
class ScoutTacticalState(TypedDict):
    incident_id: str  # 必填
    user_id: str      # 必填
    thread_id: str    # 必填
    slots: NotRequired[ScoutTaskGenerationSlots]  # 可选
    selected_devices: NotRequired[List[Dict[str, Any]]]  # 可选
    waypoints: NotRequired[List[Dict[str, Any]]]  # 可选
```

**@task包装要求**:
```python
@task
async def query_device_directory_task(
    filters: Dict[str, Any],
    device_dao: DeviceDAO
) -> List[DeviceRecord]:
    """查询设备目录（幂等）"""
    # ...

@task
async def plan_recon_route_task(
    origin: Coordinate,
    targets: List[Coordinate],
    amap_client: AmapClient
) -> List[Waypoint]:
    """规划侦察航线（幂等）"""
    # ...
```

**日志要求**:
```python
logger.info("scout_device_allocated",
            device_id=device.id,
            device_type=device.type,
            capabilities=device.capabilities)
logger.info("scout_route_generated",
            waypoint_count=len(waypoints),
            total_distance_km=distance)
```

#### 2. UI Action协议统一 ⭐⭐⭐
**新增文件**: `src/emergency_agents/ui/actions.py`

**需要实现**:
```python
from typing import Literal, TypedDict, NotRequired, List
from typing_extensions import TypedDict

# 定义所有UI Action类型
UIActionType = Literal[
    "fly_to",
    "open_plan_panel",
    "open_scout_panel",
    "show_risk_warning",
    "show_toast",
    "update_device_status",
    "highlight_route_segment",
    "device_control_ack"
]

# 强类型UI Action定义
class FlyToAction(TypedDict):
    action: Literal["fly_to"]
    payload: dict  # {lng: float, lat: float, zoom: int}

class OpenPlanPanelAction(TypedDict):
    action: Literal["open_plan_panel"]
    payload: dict  # {plan: Dict[str, Any]}

class ShowRiskWarningAction(TypedDict):
    action: Literal["show_risk_warning"]
    payload: dict  # {zone_id: str, message: str, severity: int}

# 联合类型
UIAction = FlyToAction | OpenPlanPanelAction | ShowRiskWarningAction | ...

# 构建器函数
def build_fly_to_action(lng: float, lat: float, zoom: int = 14) -> FlyToAction:
    """构建视角跳转动作"""
    return {
        "action": "fly_to",
        "payload": {"lng": lng, "lat": lat, "zoom": zoom}
    }

def build_open_plan_panel_action(plan: Dict[str, Any]) -> OpenPlanPanelAction:
    """构建打开方案面板动作"""
    return {
        "action": "open_plan_panel",
        "payload": {"plan": plan}
    }

# ... 其他构建器
```

**所有Handler需要统一返回**:
```python
from emergency_agents.ui.actions import build_fly_to_action, UIAction

def handle(...) -> dict[str, object]:
    # ...
    ui_actions: List[UIAction] = []
    ui_actions.append(build_fly_to_action(lng, lat))
    ui_actions.append(build_open_plan_panel_action(plan))

    return {
        "response_text": message,
        "rescue_task": task_data,
        "ui_actions": ui_actions  # ✅ 统一格式
    }
```

#### 3. LLM客户端工厂 ⭐⭐
**新增文件**: `src/emergency_agents/llm/factory.py`

**需要实现**:
```python
from typing import Protocol, Dict, Any
from emergency_agents.config import AppConfig

class LLMClient(Protocol):
    """LLM客户端协议"""
    def chat_completion(self, messages: list, **kwargs) -> Any: ...

class LLMClientFactory:
    """LLM客户端工厂"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._clients: Dict[str, LLMClient] = {}

    def get_client(self, key: str = "default") -> LLMClient:
        """获取LLM客户端

        Args:
            key: 客户端标识
                - "default": 默认模型
                - "intent": 意图识别专用
                - "rescue": 救援规划专用
                - "scout": 侦察规划专用
        """
        if key not in self._clients:
            self._clients[key] = self._create_client(key)
        return self._clients[key]

    def _create_client(self, key: str) -> LLMClient:
        """创建LLM客户端"""
        # 根据key选择不同配置
        if key == "intent":
            return self._build_openai_client(
                model=self._config.intent_llm_model
            )
        elif key == "rescue":
            return self._build_openai_client(
                model=self._config.llm_model
            )
        # ... 其他配置
```

### P1（本周完成）- 规划要求的重要功能

#### 4. 战术救援UI Actions统一返回
**修改文件**: `intent/handlers/rescue_task_generation.py`

**需要补充**:
```python
from emergency_agents.ui.actions import (
    build_fly_to_action,
    build_open_plan_panel_action,
    build_show_risk_warning_action,
    UIAction
)

async def handle(...) -> dict[str, object]:
    # ... 现有逻辑

    # ✅ 新增：构建UI动作
    ui_actions: List[UIAction] = []

    # 视角跳转
    if resolved_location:
        ui_actions.append(build_fly_to_action(
            lng=resolved_location["lng"],
            lat=resolved_location["lat"]
        ))

    # 打开方案面板
    ui_actions.append(build_open_plan_panel_action(plan=rescue_task))

    # 风险提醒
    for warning in route_warnings:
        ui_actions.append(build_show_risk_warning_action(
            zone_id=warning["zone_id"],
            message=warning["message"],
            severity=warning["severity"]
        ))

    return {
        "response_text": response_text,
        "rescue_task": rescue_task,
        "routes": routes,
        "ui_actions": ui_actions  # ✅ 统一返回
    }
```

#### 5. 实体直接写库接口
**新增文件**: `db/entity_repository.py`

**需要实现**:
```python
from dataclasses import dataclass
from typing import Optional
from emergency_agents.db.dao import BaseDAO

@dataclass(slots=True)
class EntityCreateInput:
    """实体创建输入"""
    incident_id: str
    layer_code: str
    entity_type: str
    display_name: str
    geometry_geojson: dict
    properties: dict
    source: str  # "auto" | "manual" | "voice"
    created_by: str

class EntityRepository(BaseDAO):
    """实体仓储"""

    async def create_entity(self, input: EntityCreateInput) -> EntityRecord:
        """直接创建实体"""
        # INSERT INTO incident_entities ...
        # 返回完整EntityRecord

    async def link_to_incident(self, incident_id: str, entity_id: str) -> None:
        """关联实体到事件"""
        # INSERT INTO incident_entity_links ...
```

#### 6. 战术救援State定义修复
**修改文件**: `graph/rescue_tactical_app.py`

**需要重构**:
```python
# ❌ 删除所有 total=False 的State定义
class RescueTacticalState(TypedDict, total=False):  # 删除这个
    # ...

# ✅ 替换为正确模式
from typing_extensions import Required, NotRequired

class RescueTacticalState(TypedDict):
    # 必填字段（绝对需要）
    task_id: Required[str]
    user_id: Required[str]
    thread_id: Required[str]

    # 可选字段（显式声明）
    slots: NotRequired[RescueTaskGenerationSlots]
    simulation_mode: NotRequired[bool]
    status: NotRequired[str]
    error: NotRequired[str]
    resolved_location: NotRequired[Dict[str, Any]]
    resources: NotRequired[List[ResourceCandidate]]
    # ... 其他可选字段

# 同样修复所有辅助TypedDict
class ResourceCandidate(TypedDict):
    resource_id: Required[str]
    name: Required[str]
    rescuer_type: Required[str]
    lng: NotRequired[float]
    lat: NotRequired[float]
    # ...
```

### P2（下周开始）- 战略层功能

#### 7. 战略侦察规划（StrategicReconGraph）
**新增文件**: `graph/strategic_recon_app.py`

**需要实现**（待确认需求后开发）

#### 8. 态势上报（SITREPGraph）
**新增文件**: `graph/sitrep_app.py`

**需要实现**（待确认需求后开发）

#### 9. 行动评估（PostActionAssessmentGraph）
**新增文件**: `graph/post_action_assessment_app.py`

**需要实现**（待确认需求后开发）

#### 10. 位置监控（TeamMonitorGraph）
**新增文件**: `graph/team_monitor_app.py`

**需要实现**（待确认需求后开发）

---

## 9. 开发顺序建议

基于规划文档与实际代码状态，建议按以下顺序开发：

### Week 1（本周）
**Day 1-2: Phase 0补齐**
1. ✅ 创建 `ui/actions.py` - UI Action协议
2. ✅ 创建 `llm/factory.py` - LLM客户端工厂
3. ✅ 创建 `db/entity_repository.py` - 实体直接写库

**Day 3-4: 战术侦察子图**
4. ✅ 实现 `device_selection` 节点
5. ✅ 实现 `recon_route_planning` 节点
6. ✅ 实现 `sensor_payload_assignment` 节点
7. ✅ 修复 `ScoutTacticalState` 定义（Required/NotRequired）

**Day 5: 战术救援完善**
8. ✅ 统一 `rescue_task_generation` Handler的ui_actions返回
9. ✅ 修复 `RescueTacticalState` 定义（Required/NotRequired）

### Week 2（下周）
**Day 1-2: 集成测试与文档**
10. ✅ 编写集成测试（侦察全流程）
11. ✅ 更新文档（子图开发规划）

**Day 3-5: 战略层规划（如需要）**
12. ⚠️ 评估是否复用 `/ai/plan/*` API
13. ⚠️ 如需独立开发，实现 `StrategicReconGraph`

---

## 10. 关键决策点（需要用户确认）

### 决策点1: 战略救援规划实现方式
**问题**: 规划文档要求开发`StrategicRescueGraph`，但实际已有`/ai/plan/recommend` API

**选项**:
- A. 复用现有 `/ai/plan/*` API（推荐）
- B. 新开发独立的 `StrategicRescueGraph` 子图
- C. 将 `/ai/plan/*` 重构为LangGraph子图

**建议**: 选择A（复用），避免重复开发

### 决策点2: 路线风险提醒实现方式
**问题**: 规划要求独立`RouteRiskGuard`子图，但实际已嵌入`rescue_tactical_app`

**选项**:
- A. 保持嵌入式实现（推荐）
- B. 提取为独立子图

**建议**: 选择A（嵌入式更高效）

### 决策点3: 风险预测实现方式
**问题**: 规划要求`RiskPredictionGraph`子图，但实际是`RiskPredictor`后台服务

**选项**:
- A. 保持后台服务方式（推荐）
- B. 重构为LangGraph子图

**建议**: 选择A（后台服务更适合定时任务）

### 决策点4: Phase 2/Phase 3优先级
**问题**: 战略层（Phase 2）和群众安置（Phase 3）哪个优先？

**建议**:
- 如果是演示，Phase 2战略层更重要（体现AI规划能力）
- 如果是实际应用，Phase 3群众安置更实用

---

## 11. 附录：完整待办清单

### Phase 0补齐
- [ ] 创建 `ui/actions.py` - UI Action协议
- [ ] 创建 `llm/factory.py` - LLM客户端工厂
- [ ] 创建 `db/entity_repository.py` - 实体仓储

### Phase 1A（战术救援）
- [ ] 修复 `RescueTacticalState` 定义
- [ ] 修复所有辅助TypedDict定义
- [ ] 统一ui_actions返回
- [ ] 集成entity_repository

### Phase 1B（战术侦察）
- [ ] 修复 `ScoutTacticalState` 定义
- [ ] 实现 `device_selection` 节点（@task包装）
- [ ] 实现 `recon_route_planning` 节点（@task包装）
- [ ] 实现 `sensor_payload_assignment` 节点（@task包装）
- [ ] 补充必备日志

### Phase 2（战略层）- 待确认
- [ ] 评估是否复用 `/ai/plan/*` API
- [ ] 如需要，实现 `StrategicReconGraph`
- [ ] 如需要，实现 `SITREPGraph`
- [ ] 如需要，实现 `PostActionAssessmentGraph`

### Phase 3（群众安置）- 待确认
- [ ] 实现 `ShelterRecommendationGraph`
- [ ] 实现 `SupplyMissionGraph`
- [ ] 实现 `TeamMonitorGraph`

---

**报告结束**

**下一步**: 请确认上述决策点，然后我开始从P0开始逐项开发。
