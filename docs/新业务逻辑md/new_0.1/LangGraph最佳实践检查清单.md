# LangGraph 最佳实践检查清单

**创建日期**: 2025-11-02
**基于**: LangGraph 官方文档（2025-10-30 最新版本）
**适用版本**: langgraph >= 0.6.0
**状态**: ✅ 强制执行 - 所有后续开发必须遵循

---

## 📌 核心原则

> **所有后续开发必须以 LangGraph 官方推荐为主**

这意味着：
1. ✅ 新功能开发前，先查阅官方文档
2. ✅ 使用最新的 API（v0.6.0+）
3. ✅ 避免使用已废弃的 API
4. ✅ 遵循官方示例的代码模式

---

## 1️⃣ Durability Modes（持久化策略）

### 📚 官方推荐（v0.6.0+）

**使用 `durability` 参数**（替代旧的 `checkpoint_during`）：

```python
# ✅ 正确 - 新 API
graph.invoke(state, config={"durability": "sync"})
graph.stream(state, config={"durability": "async"})

# ❌ 错误 - 已废弃
graph.invoke(state, config={"checkpoint_during": True})
```

### 📖 三种 Durability 模式

| 模式 | 持久化时机 | 适用场景 | 性能 | 可靠性 |
|------|-----------|---------|------|--------|
| `"exit"` | 仅在完成时 | 短流程、无人工审核 | ⭐⭐⭐ | ⭐ |
| `"async"` | 异步持久化 | 中等流程、平衡需求 | ⭐⭐ | ⭐⭐ |
| `"sync"` | 每步同步持久化 | 长流程、人工审核、高可靠性 | ⭐ | ⭐⭐⭐ |

### ✅ 当前项目状态

**已正确使用**（基于代码验证）：

```python
# rescue_task_generation.py:877
result = await graph.invoke(
    tactical_state,
    config={"durability": "sync"},  # ✅ 长流程，同步保存
)

# scout_task_generation.py:95
result = await graph.invoke(
    tactical_state,
    config={"durability": "sync"},  # ✅ 长流程，同步保存
)

# intent_processor.py:337
graph_state: IntentOrchestratorState = await orchestrator_graph.ainvoke(
    initial_state,
    config={"durability": "async"},  # ✅ 中流程，异步保存
)
```

### 📝 后续开发规则

**选择 Durability 模式的决策树**：

```
是否有人工审核？
  ├─ 是 → durability="sync"（救援方案审批、任务生成等）
  └─ 否
      ├─ 流程耗时 > 10秒？
      │   ├─ 是 → durability="async"（意图编排、RAG 检索等）
      │   └─ 否 → durability="exit"（简单查询、状态查询等）
      └─ 需要 checkpoint 恢复？
          ├─ 是 → 至少使用 durability="async"
          └─ 否 → durability="exit"
```

**示例代码**：

```python
# 短流程（设备状态查询）
result = graph.invoke(state, config={"durability": "exit"})

# 中等流程（意图识别）
result = await graph.ainvoke(state, config={"durability": "async"})

# 长流程（救援任务生成，需要人工审批）
result = await graph.ainvoke(state, config={"durability": "sync"})
```

---

## 2️⃣ Human-in-the-Loop（人工审核）

### 📚 官方推荐（v0.6.0+）

**使用 `interrupt()` 函数**（替代 `interrupt_before` 参数）：

```python
# ✅ 正确 - 新 API
from langgraph.types import interrupt, Command

def review_node(state):
    # 暂停执行，等待人工审核
    human_feedback = interrupt({
        "data_to_review": state["plan"],
        "question": "请审批救援方案"
    })
    return {"approved_plan": human_feedback}

# 恢复执行
graph.invoke(
    Command(resume={"approved": True, "plan": updated_plan}),
    config=config
)
```

```python
# ❌ 错误 - 旧 API（已废弃）
builder.add_node("review", review_node)
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["review"]  # ❌ 不推荐
)
```

### ⚠️ 当前项目状态

**需要检查和改进**：

当前项目可能使用了 `interrupt_before` 模式（需要验证）。如果是，需要重构为 `interrupt()` 函数模式。

**检查清单**：
- [ ] 搜索代码中所有 `interrupt_before` 的使用
- [ ] 替换为 `interrupt()` 函数调用
- [ ] 更新 `Command(resume=...)` 恢复逻辑

### 📝 后续开发规则

**人工审核的标准实现**：

```python
from langgraph.types import interrupt, Command

def generate_rescue_plan(state):
    # 1. 生成救援方案
    plan = create_plan(state)

    # 2. 暂停执行，等待人工审批
    approval_data = interrupt({
        "plan": plan,
        "question": "请审批救援方案",
        "task_id": state["task_id"]
    })

    # 3. 处理审批结果
    if approval_data.get("approved"):
        return {"plan": approval_data.get("plan", plan), "status": "approved"}
    else:
        return {"status": "rejected", "reason": approval_data.get("reason")}
```

**恢复执行**：

```python
# 人工审批通过
graph.invoke(
    Command(resume={"approved": True, "plan": modified_plan}),
    config={"configurable": {"thread_id": thread_id}}
)

# 人工审批拒绝
graph.invoke(
    Command(resume={"approved": False, "reason": "方案不可行"}),
    config={"configurable": {"thread_id": thread_id}}
)
```

---

## 3️⃣ Command Object（多智能体通信）

### 📚 官方推荐（v0.6.0+）

**使用 `Command` 对象同时控制路由和状态更新**：

```python
from langgraph.types import Command

def agent_node(state):
    # 决策下一步
    next_agent = decide_next_agent(state)

    # 使用 Command 同时路由和更新状态
    return Command(
        goto=next_agent,  # 路由到下一个节点
        update={          # 更新状态
            "current_agent": next_agent,
            "step_count": state["step_count"] + 1
        }
    )
```

**多图通信**（子图跳转到父图节点）：

```python
def subgraph_node(state):
    # 子图节点跳转到父图的另一个节点
    return Command(
        goto="parent_node_name",
        update={"data": "from_subgraph"},
        graph=Command.PARENT  # 指定跳转到父图
    )
```

### ✅ 当前项目状态

**需要验证**：当前项目是否使用了 `Command` 对象？

**检查清单**：
- [ ] 搜索代码中 `Command` 的使用
- [ ] 确认是否用于多智能体通信
- [ ] 检查是否有手动路由逻辑可以用 `Command` 简化

### 📝 后续开发规则

**何时使用 Command**：

1. **动态路由**（LLM 决定下一步）：
```python
def llm_router(state):
    response = llm.invoke(state["messages"])
    next_node = extract_next_node(response)

    return Command(
        goto=next_node,
        update={"messages": [response]}
    )
```

2. **多智能体协作**（Agent A 调用 Agent B）：
```python
def agent_a(state):
    # Agent A 完成任务后，将控制权交给 Agent B
    return Command(
        goto="agent_b",
        update={
            "current_agent": "agent_b",
            "handoff_data": state["result"]
        }
    )
```

3. **子图通信**（子图节点跳转到父图）：
```python
def tactical_node_in_subgraph(state):
    # 战术图节点完成后，跳转到父图的审批节点
    return Command(
        goto="approval_node",
        update={"tactical_result": state["plan"]},
        graph=Command.PARENT
    )
```

---

## 4️⃣ Task Decorator（副作用操作）

### 📚 官方推荐

**使用 `@task` 装饰器包装所有副作用操作**：

```python
from langgraph.func import task
import requests

@task
def call_external_api(url: str) -> dict:
    """副作用操作：HTTP 请求"""
    response = requests.get(url)
    return response.json()

def my_node(state):
    # 调用 task（返回 Future 对象）
    future = call_external_api(state["url"])

    # 获取结果
    result = future.result()

    return {"api_result": result}
```

### ⚠️ 副作用操作清单

**必须用 `@task` 包装的操作**：

1. **外部 API 调用**：
   - HTTP 请求（requests, httpx, aiohttp）
   - LLM API 调用（OpenAI, Anthropic）
   - 数据库查询（PostgreSQL, Neo4j, Qdrant）

2. **文件系统操作**：
   - 文件读写（`open()`, `write()`）
   - 目录创建/删除

3. **非确定性操作**：
   - 随机数生成（`random.random()`）
   - 当前时间获取（`time.time()`, `datetime.now()`）

4. **消息队列操作**：
   - Kafka 生产/消费
   - RabbitMQ 发送/接收

### ⚠️ 当前项目状态

**需要全面检查**：

**检查清单**：
- [ ] 搜索所有 `requests.get/post/put/delete`
- [ ] 搜索所有 `llm.invoke/ainvoke`
- [ ] 搜索所有数据库查询操作
- [ ] 搜索所有文件操作 `open()`
- [ ] 搜索所有 `random.random()` 或 `datetime.now()`
- [ ] 确认这些操作是否都用 `@task` 包装

### 📝 后续开发规则

**标准实现模式**：

```python
from langgraph.func import task
import requests
from datetime import datetime

# ❌ 错误 - 直接在 node 中调用副作用操作
def bad_node(state):
    result = requests.get(state["url"])  # ❌ 副作用未包装
    timestamp = datetime.now()           # ❌ 非确定性
    return {"result": result.json(), "timestamp": timestamp}

# ✅ 正确 - 使用 @task 包装
@task
def fetch_data(url: str):
    return requests.get(url).json()

@task
def get_timestamp():
    return datetime.now().isoformat()

def good_node(state):
    data_future = fetch_data(state["url"])
    time_future = get_timestamp()

    # 并行等待
    data = data_future.result()
    timestamp = time_future.result()

    return {"result": data, "timestamp": timestamp}
```

**批量操作优化**：

```python
@task
def call_llm(messages: list):
    """单次 LLM 调用"""
    return llm.invoke(messages)

def node_with_multiple_llm_calls(state):
    # ✅ 并行调用多个 LLM
    futures = [
        call_llm(state["query_1"]),
        call_llm(state["query_2"]),
        call_llm(state["query_3"])
    ]

    # 等待所有结果
    results = [f.result() for f in futures]

    return {"llm_results": results}
```

---

## 5️⃣ State Management（状态管理）

### 📚 官方推荐

**使用 TypedDict + Annotated + Reducer**：

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class MyState(TypedDict):
    messages: Annotated[list, add_messages]  # 使用 reducer
    user_id: str                              # 简单字段
    count: int                                # 简单字段
```

### ✅ 当前项目状态

**已正确使用**（基于代码验证）：

```python
# RescueTacticalState（rescue_tactical_app.py）
class RescueTacticalState(TypedDict):
    task_id: str
    user_id: str
    thread_id: str
    slots: RescueTaskGenerationSlots
    # ... 其他字段

# ScoutTacticalState（scout_tactical_app.py）
class ScoutTacticalState(TypedDict):
    incident_id: str
    user_id: str
    thread_id: str
    slots: ScoutTaskGenerationSlots
    # ... 其他字段
```

### 📝 后续开发规则

**State 设计原则**：

1. **使用 TypedDict**（不是普通 dict）：
```python
# ✅ 正确
class MyState(TypedDict):
    field_a: str
    field_b: int

# ❌ 错误
MyState = {"field_a": str, "field_b": int}
```

2. **可选字段使用 NotRequired**：
```python
from typing import NotRequired

class MyState(TypedDict):
    required_field: str                    # 必填
    optional_field: NotRequired[str]       # 可选
```

3. **列表字段使用 Annotated + Reducer**：
```python
from typing import Annotated
from langgraph.graph.message import add_messages

class MyState(TypedDict):
    messages: Annotated[list, add_messages]  # 自动合并
    logs: Annotated[list, lambda x, y: x + y]  # 自定义 reducer
```

4. **多智能体共享状态**：
```python
# 父图状态（共享）
class ParentState(TypedDict):
    messages: Annotated[list, add_messages]
    shared_data: str

# 子图状态（私有 + 共享）
class ChildState(TypedDict):
    messages: Annotated[list, add_messages]  # 与父图共享
    private_data: str                        # 子图私有
```

---

## 6️⃣ Checkpointer（持久化存储）

### 📚 官方推荐

**生产环境使用持久化 Checkpointer**：

```python
# ✅ 生产环境 - PostgreSQL
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string("postgresql://...") as saver:
    graph = builder.compile(checkpointer=saver)

# ✅ 开发环境 - SQLite
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
    graph = builder.compile(checkpointer=saver)

# ⚠️ 测试环境 - 内存（不持久化）
from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(checkpointer=InMemorySaver())
```

### ✅ 当前项目状态

**已正确配置**：

```python
# 生产环境使用 PostgreSQL
POSTGRES_DSN = "postgresql://postgres:postgres123@192.168.31.40:5432/emergency_agent"

# 开发环境可选 SQLite
CHECKPOINT_SQLITE_PATH = "./temp/checkpoints.sqlite3"
```

### 📝 后续开发规则

**Checkpointer 选择**：

| 环境 | Checkpointer | 理由 |
|------|-------------|------|
| 生产 | PostgresSaver | 高可用、支持分布式 |
| 开发 | SqliteSaver | 轻量、本地持久化 |
| 测试 | InMemorySaver | 快速、无副作用 |
| CI/CD | InMemorySaver | 隔离、可重复 |

**Thread ID 命名规范**：

```python
# ✅ 正确 - 语义化命名
thread_id = f"rescue-{incident_id}-{task_id}"
thread_id = f"scout-{incident_id}-{timestamp}"
thread_id = f"user-{user_id}-session-{session_id}"

# ❌ 错误 - UUID 无语义
thread_id = str(uuid.uuid4())  # 难以调试
```

---

## 7️⃣ Multi-Agent Patterns（多智能体模式）

### 📚 官方推荐的 4 种模式

1. **Network（网络型）** - Agent 之间可以任意通信
2. **Supervisor（监督型）** - 一个 Supervisor 管理多个 Agents
3. **Hierarchical（层级型）** - 多层 Supervisor
4. **Custom Workflow（自定义流程）** - 预定义路由

### ✅ 当前项目状态

**当前使用**: Custom Workflow（预定义流程）

**架构**：
```
IntentOrchestrator（意图编排器）
    ├─ RescueTacticalGraph（救援战术图）
    ├─ ScoutTacticalGraph（侦察战术图）
    └─ VoiceControlGraph（语音控制图）
```

### 📝 后续开发规则

**选择多智能体模式**：

| 场景 | 推荐模式 | 理由 |
|------|---------|------|
| 固定流程 | Custom Workflow | 确定性高、易调试 |
| 动态协作 | Network | 灵活性高、适合复杂场景 |
| 集中调度 | Supervisor | 易管理、适合并行任务 |
| 大规模系统 | Hierarchical | 分层管理、可扩展 |

**当前项目适合的扩展**：

如果需要添加更多智能体（如装备推荐、风险评估），建议：
1. 保持 Custom Workflow 模式（确定性路由）
2. 在 IntentOrchestrator 层添加新的路由逻辑
3. 每个智能体仍然是独立的 StateGraph

---

## 8️⃣ Testing（测试策略）

### 📚 官方推荐

**三层测试策略**：

1. **单元测试**（Node 级别）：
```python
def test_node_function():
    state = {"input": "test"}
    result = my_node(state)
    assert result["output"] == "expected"
```

2. **集成测试**（Graph 级别）：
```python
def test_graph_execution():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test"}}
    result = graph.invoke({"input": "test"}, config)
    assert result["status"] == "success"
```

3. **持久化测试**（Checkpoint 恢复）：
```python
def test_checkpoint_resume():
    # 第一次执行
    graph.invoke(state, config={"configurable": {"thread_id": "test"}})

    # 获取 checkpoint
    snapshot = graph.get_state(config)

    # 恢复执行
    result = graph.invoke(None, config={"configurable": {"thread_id": "test"}})
    assert result["resumed"] == True
```

### ⚠️ 当前项目状态

**测试覆盖率较低**（需要改进）

**检查清单**：
- [ ] 为每个 Node 编写单元测试
- [ ] 为每个 Graph 编写集成测试
- [ ] 为 interrupt/resume 流程编写测试
- [ ] 使用 InMemorySaver 加速测试

### 📝 后续开发规则

**新功能开发流程**：

1. **先写测试**（TDD）：
```python
# test_new_feature.py
def test_new_node():
    state = {"input": "test"}
    result = new_node(state)
    assert result["output"] == "expected"
```

2. **再写实现**：
```python
# new_feature.py
def new_node(state):
    # 实现逻辑
    return {"output": process(state["input"])}
```

3. **集成测试**：
```python
def test_new_graph():
    graph = build_new_graph()
    result = graph.invoke({"input": "test"})
    assert result["status"] == "success"
```

---

## 9️⃣ Error Handling（错误处理）

### 📚 官方推荐

**使用 Retry Policy**（任务级重试）：

```python
from langgraph.func import task
from langgraph.types import RetryPolicy

@task(
    retry=RetryPolicy(
        max_attempts=3,
        retry_on=(ConnectionError, TimeoutError),
        backoff_factor=2.0
    )
)
def call_unreliable_api(url: str):
    return requests.get(url, timeout=5).json()
```

**Graph 级错误处理**：

```python
def error_handler_node(state):
    if state.get("error"):
        logger.error("Graph failed", error=state["error"])
        return {"status": "failed", "retry": False}
    return state

builder.add_node("error_handler", error_handler_node)
```

### ⚠️ 当前项目状态

**需要补充**：

**检查清单**：
- [ ] 为所有外部 API 调用添加 RetryPolicy
- [ ] 为 LLM 调用添加超时和重试
- [ ] 添加 Graph 级错误处理节点
- [ ] 记录所有错误到审计日志

### 📝 后续开发规则

**标准错误处理模式**：

```python
from langgraph.func import task
from langgraph.types import RetryPolicy
import structlog

logger = structlog.get_logger(__name__)

# 1. Task 级重试（自动重试）
@task(
    retry=RetryPolicy(
        max_attempts=3,
        retry_on=(ConnectionError, TimeoutError),
        backoff_factor=2.0
    )
)
def resilient_api_call(url: str):
    try:
        return requests.get(url, timeout=10).json()
    except Exception as e:
        logger.error("api_call_failed", url=url, error=str(e))
        raise

# 2. Node 级错误处理（业务逻辑）
def node_with_error_handling(state):
    try:
        result = process_data(state)
        return {"result": result, "status": "success"}
    except ValueError as e:
        logger.warning("validation_failed", error=str(e))
        return {"status": "validation_failed", "error": str(e)}
    except Exception as e:
        logger.error("unexpected_error", error=str(e))
        return {"status": "error", "error": str(e)}

# 3. Graph 级错误路由
def error_router(state):
    if state.get("status") == "error":
        return "error_handler"
    return "next_node"

builder.add_conditional_edges("node", error_router, {
    "error_handler": "error_handler",
    "next_node": "next_node"
})
```

---

## 🔟 Observability（可观测性）

### 📚 官方推荐

**使用 LangSmith 追踪**：

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your_api_key"
os.environ["LANGCHAIN_PROJECT"] = "emergency-rescue-system"

# LangSmith 会自动追踪所有 Graph 执行
```

**结构化日志**：

```python
import structlog

logger = structlog.get_logger(__name__)

def my_node(state):
    logger.info(
        "node_start",
        node="my_node",
        thread_id=state["thread_id"],
        input_keys=list(state.keys())
    )

    result = process(state)

    logger.info(
        "node_complete",
        node="my_node",
        status="success",
        output_keys=list(result.keys())
    )

    return result
```

### ✅ 当前项目状态

**已使用 structlog**（✅ 正确）

**检查清单**：
- [ ] 确认 LangSmith 是否已配置
- [ ] 检查关键节点是否都有日志
- [ ] 确认日志包含 thread_id、task_id 等追踪信息

### 📝 后续开发规则

**日志规范**：

```python
import structlog

logger = structlog.get_logger(__name__)

# ✅ 正确 - 结构化日志
logger.info(
    "rescue_plan_generated",
    thread_id=state["thread_id"],
    task_id=state["task_id"],
    plan_tasks_count=len(plan["tasks"]),
    duration_ms=elapsed_time
)

# ❌ 错误 - 字符串拼接
logger.info(f"Rescue plan generated for {state['task_id']}")
```

**Prometheus 指标**：

```python
from prometheus_client import Counter, Histogram

# 定义指标
graph_executions = Counter(
    "graph_executions_total",
    "Total graph executions",
    ["graph_name", "status"]
)

graph_duration = Histogram(
    "graph_duration_seconds",
    "Graph execution duration",
    ["graph_name"]
)

# 使用指标
def my_graph_wrapper(state, config):
    with graph_duration.labels("rescue").time():
        try:
            result = graph.invoke(state, config)
            graph_executions.labels("rescue", "success").inc()
            return result
        except Exception as e:
            graph_executions.labels("rescue", "error").inc()
            raise
```

---

## 📋 完整检查清单（后续开发必查）

### 开发前检查

- [ ] 确认 LangGraph 版本 >= 0.6.0
- [ ] 阅读相关官方文档
- [ ] 确定 Durability 模式（exit/async/sync）
- [ ] 确定是否需要人工审核（interrupt）
- [ ] 设计 State TypedDict

### 开发中检查

- [ ] 所有副作用操作用 `@task` 包装
- [ ] 使用 `durability` 参数（不是 `checkpoint_during`）
- [ ] 人工审核使用 `interrupt()` 函数（不是 `interrupt_before`）
- [ ] 多智能体通信使用 `Command` 对象
- [ ] 添加结构化日志（structlog）
- [ ] 添加错误处理（try-except + RetryPolicy）

### 开发后检查

- [ ] 编写单元测试（每个 Node）
- [ ] 编写集成测试（整个 Graph）
- [ ] 测试 checkpoint 恢复流程
- [ ] 测试人工审核流程（如果有）
- [ ] 验证日志和指标正常记录
- [ ] 代码 Review 确认符合最佳实践

---

## 🚨 常见错误（必须避免）

### ❌ 错误 1: 使用已废弃的 API

```python
# ❌ 错误
graph.invoke(state, config={"checkpoint_during": True})

# ✅ 正确
graph.invoke(state, config={"durability": "sync"})
```

### ❌ 错误 2: 副作用操作未包装

```python
# ❌ 错误
def node(state):
    result = requests.get(state["url"])  # 直接调用
    return {"result": result.json()}

# ✅ 正确
@task
def fetch_data(url: str):
    return requests.get(url).json()

def node(state):
    future = fetch_data(state["url"])
    return {"result": future.result()}
```

### ❌ 错误 3: 非确定性操作

```python
# ❌ 错误
def node(state):
    timestamp = datetime.now()  # 每次执行结果不同
    return {"timestamp": timestamp}

# ✅ 正确
@task
def get_timestamp():
    return datetime.now().isoformat()

def node(state):
    timestamp_future = get_timestamp()
    return {"timestamp": timestamp_future.result()}
```

### ❌ 错误 4: 错误的 interrupt 使用

```python
# ❌ 错误（旧 API）
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["review"]
)

# ✅ 正确（新 API）
def review_node(state):
    feedback = interrupt({"data": state["plan"]})
    return {"feedback": feedback}

graph = builder.compile(checkpointer=checkpointer)
```

---

## 📚 参考文档

### 官方文档（必读）

1. **核心概念**: `/home/msq/gitCode/skill/Skill_Seekers/output/langgraph/references/concepts.md`
2. **Workflows**: `/home/msq/gitCode/skill/Skill_Seekers/output/langgraph/references/workflows.md`
3. **State Management**: `/home/msq/gitCode/skill/Skill_Seekers/output/langgraph/references/state_management.md`
4. **Agents**: `/home/msq/gitCode/skill/Skill_Seekers/output/langgraph/references/agents.md`

### 本地文档

1. **LangGraph 最佳实践**: `/docs/新业务逻辑md/langgraph资料最佳实践/`
2. **项目启动指导**: `/docs/新业务逻辑md/new_0.1/项目启动指导.md`
3. **前端集成提案**: `/docs/新业务逻辑md/new_0.1/前端集成OpenSpec提案-战术救援侦察UI Actions协议.md`

---

## 🎯 总结

**核心原则**：
1. ✅ 使用最新 API（v0.6.0+）
2. ✅ 所有副作用操作用 `@task` 包装
3. ✅ 选择合适的 `durability` 模式
4. ✅ 人工审核使用 `interrupt()` 函数
5. ✅ 多智能体通信使用 `Command` 对象
6. ✅ 编写完整的测试（单元 + 集成）
7. ✅ 使用结构化日志和指标

**违反最佳实践 = 代码 Review 不通过！**

---

**文档版本**: v1.0
**创建日期**: 2025-11-02
**维护者**: Claude Code（基于 LangGraph 官方文档）
**状态**: ✅ 强制执行
