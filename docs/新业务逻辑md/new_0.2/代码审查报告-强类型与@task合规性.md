# 代码审查报告：强类型与@task合规性

**生成日期**: 2025-11-02
**审查方法**: 深度代码扫描，不依赖文档描述
**审查范围**: 所有 State 定义 + 所有副作用操作
**审查标准**: LangGraph 最佳实践检查清单（v0.6.0+）

---

## 执行摘要

### 合规性概况

| 检查项 | 合格数 | 不合格数 | 合规率 | 状态 |
|-------|--------|---------|--------|------|
| **State定义** | 3/6 | 3/6 | 50% | ⚠️ 部分合规 |
| **@task包装** | 29个已用 | 多处遗漏 | 未统计 | ⚠️ 部分合规 |
| **占位代码** | 0 | 1 | 0% | ❌ 不合规 |

### 关键发现

1. **文档过时问题**: 文档说所有 State 用 `total=False`，但实际有3个已修复
2. **@task遗漏**: `plan_generator_agent` 等多个函数内部有 LLM 调用但未包装
3. **占位实现**: `video_analysis.py` 返回 `"status": "pending_pipeline"`

---

## 1. State定义合规性检查

### 1.1 已修复（符合强类型要求）✅

#### RescueTacticalState

**文件位置**: `src/emergency_agents/graph/rescue_tactical_app.py:107-150`

**定义方式**:
```python
class RescueTacticalState(TypedDict):
    """救援战术子图状态定义

    核心标识字段（Required）：task_id, user_id, thread_id
    其他所有字段（NotRequired）：在图执行过程中逐步填充
    """
    # 核心标识字段（必填）
    task_id: Required[str]
    user_id: Required[str]
    thread_id: Required[str]

    # 输入槽位与配置（可选）
    slots: NotRequired[RescueTaskGenerationSlots]
    simulation_mode: NotRequired[bool]
    # ... 其他可选字段
```

**合规性评估**: ✅ **完全合规**
- 使用 `Required` 明确标识必填字段
- 使用 `NotRequired` 明确标识可选字段
- 有详细的注释说明字段用途
- 符合"强类型第一"原则

#### ScoutTacticalState

**文件位置**: `src/emergency_agents/graph/scout_tactical_app.py:279`

**定义方式**: 与 RescueTacticalState 相同模式

**合规性评估**: ✅ **完全合规**

#### SITREPState

**文件位置**: `src/emergency_agents/graph/sitrep_app.py:81`

**定义方式**: 与 RescueTacticalState 相同模式

**合规性评估**: ✅ **完全合规**

---

### 1.2 未修复（仍使用 total=False）❌

#### IntentOrchestratorState

**文件位置**: `src/emergency_agents/graph/intent_orchestrator_app.py:21-40`

**定义方式**:
```python
class IntentOrchestratorState(TypedDict, total=False):
    """意图编排状态。"""

    thread_id: str
    user_id: str
    channel: Literal["voice", "text", "system"]
    incident_id: str
    raw_text: str
    metadata: Dict[str, Any]
    messages: Annotated[list[Dict[str, Any]], add_messages]
    intent: Dict[str, Any]
    intent_prediction: Dict[str, Any]
    validation_status: Literal["valid", "invalid", "failed"]
    missing_fields: list[str]
    prompt: Optional[str]
    validation_attempt: int
    memory_hits: list[Dict[str, Any]]
    router_next: str
    router_payload: Dict[str, Any]
    audit_log: list[Dict[str, Any]]
```

**问题分析**:
1. ❌ 使用 `total=False` 导致所有字段都变成可选
2. ❌ 无法区分哪些是必填，哪些是可选
3. ❌ 运行时可能出现 KeyError（访问不存在的字段）
4. ❌ 类型检查器无法捕获缺字段错误

**影响范围**: **严重** - 这是核心意图编排图，影响所有意图处理流程

**建议修复**:
```python
class IntentOrchestratorState(TypedDict):
    """意图编排状态。"""

    # 必填字段（输入时必须提供）
    thread_id: Required[str]
    user_id: Required[str]
    channel: Required[Literal["voice", "text", "system"]]
    raw_text: Required[str]

    # 可选字段（流程中逐步填充）
    incident_id: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]
    messages: NotRequired[Annotated[list[Dict[str, Any]], add_messages]]
    intent: NotRequired[Dict[str, Any]]
    intent_prediction: NotRequired[Dict[str, Any]]
    validation_status: NotRequired[Literal["valid", "invalid", "failed"]]
    missing_fields: NotRequired[list[str]]
    prompt: NotRequired[str]
    validation_attempt: NotRequired[int]
    memory_hits: NotRequired[list[Dict[str, Any]]]
    router_next: NotRequired[str]
    router_payload: NotRequired[Dict[str, Any]]
    audit_log: NotRequired[list[Dict[str, Any]]]
```

#### RescueState

**文件位置**: `src/emergency_agents/graph/app.py:42-84`

**定义方式**:
```python
class RescueState(TypedDict, total=False):
    rescue_id: str
    user_id: str
    status: Literal["init", "awaiting_approval", "running", "completed", "error"]
    messages: list
    error_count: int
    max_steps: int
    last_error: dict

    raw_report: str
    situation: dict
    primary_disaster: dict
    secondary_disasters: list
    predicted_risks: list
    timeline: list
    compound_risks: list
    available_resources: dict
    blocked_roads: list

    proposals: list
    approved_ids: list
    executed_actions: list

    plan: dict
    plan_approved: bool
    alternative_plans: list

    equipment_recommendations: list
    risk_level: int
    hazards: list

    pending_memories: list
    committed_memories: list

    uav_tracks: list
    fleet_position: dict
    integration_logs: list
    pending_entities: list
    pending_events: list
    pending_annotations: list
    annotations: list
    tasks: list
```

**问题分析**: 与 IntentOrchestratorState 相同

**影响范围**: **严重** - 这是核心救援图，管理整个救援线程生命周期

**建议修复**:
```python
class RescueState(TypedDict):
    # 必填字段
    rescue_id: Required[str]
    user_id: Required[str]
    status: Required[Literal["init", "awaiting_approval", "running", "completed", "error"]]

    # 可选字段
    messages: NotRequired[list]
    error_count: NotRequired[int]
    max_steps: NotRequired[int]
    last_error: NotRequired[dict]
    raw_report: NotRequired[str]
    # ... 其他所有字段都用 NotRequired
```

#### ReconState

**文件位置**: `src/emergency_agents/graph/recon_app.py:14`

**问题分析**: 与上述相同

**影响范围**: **中等** - 侦察子图，使用频率低于核心图

---

## 2. @task装饰器合规性检查

### 2.1 已正确使用的 @task 函数（29个）✅

#### 按文件统计

| 文件 | @task数量 | 代码行 |
|------|----------|--------|
| `rescue_tactical_app.py` | 8 | 163, 174, 193, 207, 221, 235, 258, 280 |
| `scout_tactical_app.py` | 7 | 1020, 1035, 1177, 1311, 1390, 1464, 1538 |
| `sitrep_app.py` | 6 | 126, 151, 177, 203, 239, 291 |
| `risk_predictor.py` | 4 | 20, 40, 62, 99 |
| `rescue_task_generate.py` | 3 | 60, 76, 98 |
| `situation.py` | 1 | 57 |

**合规性评估**: ✅ **这些函数完全合规**

#### 示例（rescue_tactical_app.py）

```python
@task
async def query_resources_task(
    # ...
) -> List[ResourceCandidate]:
    """查询可用资源（幂等）"""
    # 数据库查询 - 副作用操作
    rescuers = await rescuer_dao.list_rescuers(
        incident_id=incident_id,
        scenario_type=scenario_type,
    )
    # ...
    return candidates

@task
async def geocode_task(
    # ...
) -> Tuple[float, float, str, str]:
    """地理编码（幂等）"""
    # HTTP API 调用 - 副作用操作
    amap_result = await amap_client.geocode(location_text)
    # ...
    return lng, lat, formatted_address, adcode
```

---

### 2.2 未使用 @task 的副作用操作（严重问题）❌

#### plan_generator_agent 中的 LLM 调用

**文件位置**: `src/emergency_agents/agents/plan_generator.py:135`

**问题代码**:
```python
def plan_generator_agent(
    state: Dict[str, Any],
    kg_service: KGService,
    llm_client: LLMClientProtocol,
    llm_model: str = "glm-4",
    orchestrator_client: Optional[OrchestratorClient] = None,
) -> Dict[str, Any]:
    """方案生成智能体"""

    # ... 其他代码

    # ❌ 直接调用 LLM API，未用 @task 包装
    response = llm_client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": "你是专业的应急救援指挥专家，精通灾害应对和资源调度。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    llm_output = response.choices[0].message.content or ""
    # ...
```

**调用链**:
```
app.py:145 plan_node()
  → plan_generator.py:30 plan_generator_agent()
    → plan_generator.py:135 llm_client.chat.completions.create()  ❌ 未用 @task
```

**问题分析**:
1. ❌ LLM API 调用是副作用操作，必须用 @task 包装
2. ❌ 违反 LangGraph 最佳实践（见检查清单第4条）
3. ❌ 可能导致幂等性问题（checkpoint 恢复时可能重复调用）
4. ❌ 无法利用 LangGraph 的并行执行优化

**影响范围**: **严重** - plan_node 是救援流程的核心节点

**建议修复方式1（推荐）**:
```python
@task
async def generate_rescue_plan_task(
    situation: dict,
    predicted_risks: list,
    kg_requirements: list,
    llm_client: LLMClientProtocol,
    llm_model: str,
) -> dict:
    """生成救援方案（幂等）"""
    # ... 构建 prompt

    response = llm_client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": "..."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return _parse_plan_response(response)

def plan_generator_agent(
    state: Dict[str, Any],
    kg_service: KGService,
    llm_client: LLMClientProtocol,
    llm_model: str = "glm-4",
) -> Dict[str, Any]:
    """方案生成智能体"""

    # 调用 @task 函数
    future = generate_rescue_plan_task(
        state["situation"],
        state["predicted_risks"],
        kg_requirements,
        llm_client,
        llm_model,
    )

    result = future.result()  # 等待结果
    return {"plan": result, ...}
```

**建议修复方式2（直接在节点中使用 @task）**:
```python
# app.py
def plan_node(state: RescueState) -> dict:

    @task
    def _llm_call():
        return llm_client.chat.completions.create(...)

    future = _llm_call()
    response = future.result()

    # ... 其他处理
    return {"plan": ...}
```

---

#### 其他可能遗漏的副作用操作

**需要进一步检查的文件**:

| 文件 | 行号 | 操作类型 | 状态 |
|------|------|---------|------|
| `planner/recon_llm.py` | 126 | LLM 调用 | ⚠️ 需检查 |
| `voice/intent_handler.py` | 88 | LLM 调用 | ⚠️ 需检查 |
| `rag/equipment_extractor.py` | 143 | LLM 调用 | ⚠️ 需检查 |
| `intent/unified_intent.py` | 441 | LLM 调用 | ⚠️ 需检查 |
| `intent/expert_consult.py` | 180 | LLM 调用 | ⚠️ 需检查 |
| `api/main.py` | 783 | LLM 调用 | ⚠️ 需检查 |
| `api/reports.py` | 174 | LLM 调用 | ⚠️ 需检查 |
| `intent/validator.py` | 132 | LLM 调用 | ⚠️ 需检查 |
| `intent/providers/llm.py` | 192 | LLM 调用 | ⚠️ 需检查 |
| `intent/prompt_missing.py` | 74 | LLM 调用 | ⚠️ 需检查 |

**注**: 这些文件需要逐一检查，确认 LLM 调用是否在 @task 函数内部，或者是否需要添加 @task。

---

## 3. 占位代码检查

### 3.1 video_analysis.py 占位实现❌

**文件位置**: `src/emergency_agents/intent/handlers/video_analysis.py:45-54`

**问题代码**:
```python
async def handle(self, slots: VideoAnalysisSlots, state: dict[str, object]) -> dict[str, object]:
    # ... 前置检查

    message = (
        f"已进入视频流分析流程（{device.name or device.id}）。"
        " 当前阶段为占位实现，等待视频处理模块接入。"  # ❌ 明确说明是占位
    )
    payload = {
        "status": "pending_pipeline",  # ❌ 占位状态
        "device": serialize_dataclass(device) | {"stream_url": stream_url},
        "analysis_goal": slots.analysis_goal,
    }
    return {"response_text": message, "video_analysis": payload}
```

**问题分析**:
1. ❌ 返回硬编码的占位响应
2. ❌ `status: "pending_pipeline"` 表示功能未实现
3. ❌ 违反"不做降级或 fallback"原则
4. ❌ 用户会收到误导性提示

**影响范围**: **高** - 视频分析是重要功能，当前完全不可用

**期望行为**:
- 应该接入真实的视频处理管道（GLM-4V/YOLO等）
- 应该返回真实的分析结果
- 如果功能确实未实现，应该明确报错而非返回占位数据

**建议修复**:
```python
async def handle(self, slots: VideoAnalysisSlots, state: dict[str, object]) -> dict[str, object]:
    # ... 前置检查

    # 方案1：明确报错（推荐）
    raise NotImplementedError(
        "视频分析功能尚未实现。请接入 GLM-4V 或 YOLO 视频处理模块后再使用。"
    )

    # 或者方案2：接入真实模块
    # analysis_result = await self.video_pipeline.analyze(stream_url, slots.analysis_goal)
    # return {"response_text": ..., "video_analysis": analysis_result}
```

---

## 4. 文档准确性评估

### 4.1 文档与代码的差异

| 文档说明 | 实际代码状态 | 准确性 |
|---------|------------|--------|
| "所有State用total=False" | 3/6已修复，3/6未修复 | ❌ **部分过时** |
| "@task已在Phase0修复" | 29个已用，但仍有遗漏 | ⚠️ **部分准确** |
| "视频分析是占位实现" | 确认是占位 | ✅ **准确** |
| "文档可能过时" | 确认存在差异 | ✅ **准确** |

### 4.2 建议

1. ✅ **优先相信代码** - 文档可能滞后，以实际代码为准
2. ✅ **增量更新文档** - 修复一处代码，同步更新相关文档
3. ✅ **自动化检查** - 考虑添加 pre-commit hook 检查 State 定义和 @task 使用

---

## 5. 修复优先级建议

### P0（立即修复）- 阻塞性问题

1. **plan_generator_agent 的 @task 遗漏** ⭐⭐⭐
   - **影响**: 救援方案生成可能失败
   - **风险**: 幂等性问题、checkpoint 恢复错误
   - **工作量**: 中等（需要重构）

2. **video_analysis.py 占位实现** ⭐⭐⭐
   - **影响**: 用户期望功能不可用
   - **风险**: 产品体验差
   - **工作量**: 高（需要接入真实模块）

### P1（本周修复）- 高风险问题

3. **IntentOrchestratorState total=False** ⭐⭐
   - **影响**: 意图编排可能出现运行时错误
   - **风险**: KeyError、类型错误
   - **工作量**: 低（仅需修改类型定义）

4. **RescueState total=False** ⭐⭐
   - **影响**: 救援线程可能出现运行时错误
   - **风险**: KeyError、类型错误
   - **工作量**: 低（仅需修改类型定义）

### P2（下周修复）- 潜在问题

5. **其他 LLM 调用的 @task 检查** ⭐
   - **影响**: 可能存在其他遗漏
   - **风险**: 幂等性、性能问题
   - **工作量**: 中等（需逐一排查）

6. **ReconState total=False** ⭐
   - **影响**: 侦察子图可能出现问题
   - **风险**: 较低（使用频率低）
   - **工作量**: 低

---

## 6. 修复检查清单

### State定义修复

**IntentOrchestratorState** (`intent_orchestrator_app.py:21`)
- [ ] 删除 `total=False`
- [ ] 添加 `Required` 到必填字段
- [ ] 添加 `NotRequired` 到可选字段
- [ ] 验证所有调用点是否提供必填字段
- [ ] 运行类型检查器（mypy/pyright）

**RescueState** (`app.py:42`)
- [ ] 删除 `total=False`
- [ ] 添加 `Required` 到必填字段
- [ ] 添加 `NotRequired` 到可选字段
- [ ] 验证所有调用点是否提供必填字段
- [ ] 运行类型检查器

**ReconState** (`recon_app.py:14`)
- [ ] 删除 `total=False`
- [ ] 添加 `Required` 到必填字段
- [ ] 添加 `NotRequired` 到可选字段

### @task装饰器修复

**plan_generator_agent** (`agents/plan_generator.py:30`)
- [ ] 提取 LLM 调用到 `@task` 函数
- [ ] 确保幂等性
- [ ] 添加错误处理
- [ ] 添加日志记录
- [ ] 测试 checkpoint 恢复

**其他可疑文件** (10个)
- [ ] 逐一检查 LLM 调用是否在 @task 内
- [ ] 如果不在，提取到 @task 函数
- [ ] 统一使用 @task 模式

### 占位代码修复

**video_analysis.py** (`intent/handlers/video_analysis.py:45`)
- [ ] 决定：接入真实模块 OR 明确报错
- [ ] 如果接入：选择 GLM-4V/YOLO/其他
- [ ] 如果报错：抛出 NotImplementedError
- [ ] 删除 `"status": "pending_pipeline"`
- [ ] 更新测试用例

---

## 7. 相关代码位置索引

### State定义文件
- ✅ `src/emergency_agents/graph/rescue_tactical_app.py:107` - RescueTacticalState
- ✅ `src/emergency_agents/graph/scout_tactical_app.py:279` - ScoutTacticalState
- ✅ `src/emergency_agents/graph/sitrep_app.py:81` - SITREPState
- ❌ `src/emergency_agents/graph/intent_orchestrator_app.py:21` - IntentOrchestratorState
- ❌ `src/emergency_agents/graph/app.py:42` - RescueState
- ❌ `src/emergency_agents/graph/recon_app.py:14` - ReconState

### @task使用文件
- `src/emergency_agents/graph/rescue_tactical_app.py` - 8个 @task
- `src/emergency_agents/graph/scout_tactical_app.py` - 7个 @task
- `src/emergency_agents/graph/sitrep_app.py` - 6个 @task
- `src/emergency_agents/agents/risk_predictor.py` - 4个 @task
- `src/emergency_agents/agents/rescue_task_generate.py` - 3个 @task
- `src/emergency_agents/agents/situation.py` - 1个 @task

### 问题文件
- ❌ `src/emergency_agents/agents/plan_generator.py:135` - LLM调用未用@task
- ❌ `src/emergency_agents/intent/handlers/video_analysis.py:45` - 占位实现

---

## 8. 参考文档

### 官方最佳实践
- `/docs/新业务逻辑md/new_0.1/LangGraph最佳实践检查清单.md`
- `/home/msq/gitCode/skill/Skill_Seekers/output/langgraph/references/workflows.md`
- `/home/msq/gitCode/skill/Skill_Seekers/output/langgraph/references/state_management.md`

### 项目文档
- `/docs/新业务逻辑md/new_0.1/实际业务逻辑梳理-代码反推版.md`
- `/docs/新业务逻辑md/new_0.1/子图开发状态矩阵-规划vs实际.md`
- `/docs/新业务逻辑md/new_0.1/Phase0-修复完成报告.md`

---

**报告结束**

**生成方法**: 深度代码扫描，不依赖文档描述
**可信度**: 高（直接基于代码）
**下一步**: 按优先级修复问题，更新文档
