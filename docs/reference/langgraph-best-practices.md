# LangGraph Best Practices Reference

**Purpose**: Official LangGraph best practices for async execution, checkpointing, and human-in-the-loop workflows.

**Target Audience**: AI-1 (infrastructure), all developers working with LangGraph

## 📚 Table of Contents

1. [AsyncPostgresSaver vs PostgresSaver](#asyncpostgressaver-vs-postgressaver)
2. [interrupt() for Human-in-the-Loop](#interrupt-for-human-in-the-loop)
3. [Checkpoint Management](#checkpoint-management)
4. [Dynamic Routing with Command](#dynamic-routing-with-command)
5. [Multi-Tenant Isolation](#multi-tenant-isolation)
6. [State Management](#state-management)
7. [Error Handling](#error-handling)
8. [Performance Optimization](#performance-optimization)

---

## AsyncPostgresSaver vs PostgresSaver

### ✅ Use AsyncPostgresSaver When

- Your application uses **async** frameworks (FastAPI, Starlette, aiohttp)
- You call LangGraph with **`.ainvoke()`** or **`.astream()`**
- You need non-blocking I/O operations

### ❌ Don't Use PostgresSaver When

- Your application is async (use AsyncPostgresSaver instead)
- You're calling `.ainvoke()` (mismatch between sync saver and async invoke)

### Example: Correct Async Usage

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph

async def build_graph(postgres_dsn: str):
    """Build LangGraph with AsyncPostgresSaver"""

    # ✅ Correct: Use AsyncPostgresSaver for async applications
    async with AsyncPostgresSaver.from_conn_string(postgres_dsn) as checkpointer:
        # Auto-create checkpoint tables
        await checkpointer.setup()

        builder = StateGraph(MyState)
        # ... add nodes and edges ...

        # Compile with async checkpointer
        graph = builder.compile(checkpointer=checkpointer)

        return graph


# ✅ Correct: Use ainvoke with AsyncPostgresSaver
result = await graph.ainvoke(
    {"input": "data"},
    config={"configurable": {"thread_id": "thread-001"}}
)
```

### Example: Incorrect Sync/Async Mismatch

```python
from langgraph.checkpoint.postgres import PostgresSaver  # ❌ Wrong for async

# ❌ Wrong: Sync saver with async invoke
checkpointer = PostgresSaver.from_conn_string(postgres_dsn)
graph = builder.compile(checkpointer=checkpointer)

# ❌ This will cause issues
result = await graph.ainvoke(...)  # Mismatch!
```

### Official Documentation Reference

**Source**: LangGraph Checkpointer Documentation

> "For running your graph asynchronously, use **AsyncPostgresSaver**. For synchronous execution, use PostgresSaver."

**Key Insight**: Match your saver type to your execution model (async ↔ AsyncPostgresSaver, sync ↔ PostgresSaver).

---

## interrupt() for Human-in-the-Loop

### ✅ Use interrupt() For

- **Human approval workflows** (e.g., approve rescue plan)
- **Passing data to clients** (e.g., approval request payload)
- **Resuming with user input** (e.g., approved_ids)
- **Production workflows** requiring dynamic interruption

### ❌ Don't Use interrupt_before For

- Production human-in-the-loop workflows
- Passing data to clients
- Dynamic interruption

### Why interrupt_before is Wrong

**Official Documentation**:

> "`interrupt_before` is **primarily for debugging and testing purposes**. It is not recommended for production human-in-the-loop workflows."

**Limitations**:
- Static configuration (set at compile time)
- Cannot pass data to clients
- Cannot receive input from clients
- Forces manual state injection

### Correct Pattern: interrupt()

```python
from langgraph.types import interrupt, Command
from typing import TypedDict

class ApprovalRequest(TypedDict):
    """Payload sent to client"""
    plan_id: str
    plan_summary: str
    risk_level: str

class ApprovalResponse(TypedDict):
    """Response from client"""
    approved: bool
    approved_ids: list[str] | None
    rejection_reason: str | None

async def plan_approval_node(state: dict) -> Command:
    """Human approval node using interrupt()"""

    # Prepare approval request
    request: ApprovalRequest = {
        "plan_id": state["plan"]["id"],
        "plan_summary": state["plan"]["summary"],
        "risk_level": state["plan"]["risk_level"]
    }

    # ✅ Dynamic interruption - passes data to client
    response: ApprovalResponse = interrupt(request)

    # ✅ Route based on user response
    if response["approved"]:
        return Command(
            goto="execute_plan",
            update={"approved_plan_ids": response["approved_ids"]}
        )
    else:
        return Command(
            goto="revise_plan",
            update={"rejection_reason": response["rejection_reason"]}
        )
```

### Incorrect Pattern: interrupt_before

```python
# ❌ Wrong: Using interrupt_before for HIL workflow
builder = StateGraph(MyState)
builder.add_node("await_approval", lambda s: s)  # Dummy node

# ❌ This is for debugging/testing only
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["await_approval"]
)

# ❌ Client cannot receive approval request data
# ❌ Client must manually inject state to resume
```

### Resume After interrupt()

**Client-side code**:
```python
from langgraph.types import Command

# Initial invocation - will interrupt at approval node
result = await graph.ainvoke(
    {"input": "start rescue"},
    config={"configurable": {"thread_id": "thread-001"}}
)

# User reviews approval request and responds
approved_ids = ["plan-item-1", "plan-item-2"]

# Resume with user input
result = await graph.ainvoke(
    Command(resume=approved_ids),  # ✅ Pass user input
    config={"configurable": {"thread_id": "thread-001"}}
)
```

---

## Checkpoint Management

### Automatic Table Creation

**Do NOT manually create checkpoint tables**. Use `setup()` method.

```python
# ✅ Correct: Let setup() create tables
async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
    await checkpointer.setup()  # Auto-creates 3 tables
    # - checkpoints
    # - checkpoint_blobs
    # - checkpoint_writes
```

**Official Documentation**:

> "`setup()` creates the necessary tables for checkpointing: **checkpoints**, **checkpoint_blobs**, and **checkpoint_writes**."

### Manual Business Tables Only

```sql
-- ✅ Correct: Manually create business tables
CREATE TABLE operational.ai_conversations (...);
CREATE TABLE operational.ai_messages (...);

-- ❌ Wrong: Don't manually create checkpoint tables
-- CREATE TABLE checkpoints (...);  -- Let setup() handle this
```

### Checkpoint Configuration

```python
config = {
    "configurable": {
        "thread_id": f"rescue-{rescue_id}",  # Required
        "checkpoint_ns": f"tenant-{user_id}",  # Optional: Multi-tenant isolation
        "checkpoint_id": "specific-checkpoint"  # Optional: Resume from specific checkpoint
    }
}

result = await graph.ainvoke(state, config=config)
```

---

## Dynamic Routing with Command

### Command Object

```python
from langgraph.types import Command

# Route to specific node
return Command(goto="target_node")

# Route with state update
return Command(
    goto="target_node",
    update={"key": "value"}
)

# Resume after interruption
return Command(resume=user_input_data)
```

### Use Cases

**1. Conditional Routing**:
```python
def router_node(state: dict) -> Command:
    if state["intent_type"] == "device_control_uav":
        return Command(goto="device_control_uav_node")
    elif state["intent_type"] == "query":
        return Command(goto="rag_retrieval_node")
    else:
        return Command(goto="fallback_node")
```

**2. Dynamic Node Selection**:
```python
from emergency_agents.intent.registry import get_handler_registry

def intent_router(state: dict) -> Command:
    intent_type = state["intent_type"]
    registry = get_handler_registry()

    # ✅ Dynamic node lookup
    node_name = registry.get_node_name(intent_type)
    if node_name:
        return Command(goto=node_name)
    else:
        return Command(goto="fallback_node")
```

**3. State Update During Route**:
```python
def validation_node(state: dict) -> Command:
    is_valid, missing_slots = validate_slots(state["slots"])

    if is_valid:
        return Command(
            goto="execute_action",
            update={"validated": True}
        )
    else:
        return Command(
            goto="prompt_missing_slots",
            update={"missing_slots": missing_slots}
        )
```

---

## Multi-Tenant Isolation

### Checkpoint Namespace

Use `checkpoint_ns` for tenant isolation:

```python
def get_tenant_config(user_id: str, thread_id: str) -> dict:
    """Generate tenant-isolated checkpoint config"""
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": f"tenant-{user_id}"  # ✅ Tenant isolation
        }
    }

# Different tenants, same thread_id → isolated checkpoints
config_tenant_a = get_tenant_config("user-123", "thread-001")
config_tenant_b = get_tenant_config("user-456", "thread-001")

# These will NOT interfere with each other
result_a = await graph.ainvoke(state, config=config_tenant_a)
result_b = await graph.ainvoke(state, config=config_tenant_b)
```

### Database-Level Isolation

For stronger isolation, use separate database schemas:

```python
# Tenant A: Use schema "tenant_a"
dsn_a = "postgresql://user:pass@host/db?options=-c search_path=tenant_a"

# Tenant B: Use schema "tenant_b"
dsn_b = "postgresql://user:pass@host/db?options=-c search_path=tenant_b"
```

---

## State Management

### State Schema with TypedDict

```python
from typing import TypedDict, NotRequired

class EmergencyState(TypedDict):
    """Strongly-typed state schema"""
    # Required fields
    user_input: str
    intent_type: str

    # Optional fields
    slots: NotRequired[dict]
    validated: NotRequired[bool]
    action_result: NotRequired[dict]
    error: NotRequired[str | None]
```

### Immutable State Updates

```python
def my_node(state: EmergencyState) -> EmergencyState:
    """Node function with immutable state update"""

    # ✅ Correct: Return new state dict (merge semantics)
    return state | {
        "new_field": "value",
        "updated_field": state["existing_field"] + 1
    }

    # ❌ Wrong: Don't mutate state in place
    # state["new_field"] = "value"  # Mutation!
    # return state
```

### State Validation

```python
def validate_state(state: dict) -> tuple[bool, str | None]:
    """Validate state before critical operations"""
    if "intent_type" not in state:
        return (False, "Missing intent_type")

    if "slots" in state and not isinstance(state["slots"], dict):
        return (False, "slots must be dict")

    return (True, None)
```

---

## Error Handling

### Node-Level Error Handling

```python
import logging

logger = logging.getLogger(__name__)

async def safe_node(state: dict) -> dict:
    """Node with error handling"""
    try:
        # Risky operation
        result = await call_external_api(state)
        return state | {"result": result}

    except Exception as e:
        logger.error(f"[NODE][ERROR] {e}", exc_info=True)
        return state | {"error": str(e), "success": False}
```

### Graph-Level Error Handling

```python
async def invoke_with_retry(graph, state, config, max_retries=3):
    """Invoke graph with retry logic"""
    for attempt in range(max_retries):
        try:
            result = await graph.ainvoke(state, config=config)
            return result

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise  # Re-raise on last attempt
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## Performance Optimization

### Connection Pooling

```python
# ✅ Use connection pooling for AsyncPostgresSaver
async with AsyncPostgresSaver.from_conn_string(
    dsn,
    pool_config={
        "min_size": 2,
        "max_size": 10,
        "timeout": 30
    }
) as checkpointer:
    await checkpointer.setup()
    graph = builder.compile(checkpointer=checkpointer)
```

### Checkpoint Pruning

```python
# Periodically clean old checkpoints
async def prune_old_checkpoints(checkpointer, days=30):
    """Remove checkpoints older than N days"""
    cutoff_date = datetime.now() - timedelta(days=days)

    async with checkpointer.conn.cursor() as cur:
        await cur.execute(
            """
            DELETE FROM checkpoints
            WHERE created_at < %s
            """,
            (cutoff_date,)
        )
```

### Lazy Node Loading

```python
def create_lazy_node(node_function):
    """Wrap node for lazy loading"""
    @functools.wraps(node_function)
    async def wrapper(state):
        # Skip execution if result already in state (idempotency)
        if "result_key" in state and state["result_key"]:
            return state
        return await node_function(state)
    return wrapper
```

---

## 📚 Official References

1. **LangGraph Checkpointer Documentation**
   - https://langchain-ai.github.io/langgraph/reference/checkpoints/
   - AsyncPostgresSaver API reference

2. **LangGraph Human-in-the-Loop Guide**
   - interrupt() vs interrupt_before comparison
   - Dynamic interruption patterns

3. **LangGraph State Management**
   - State schema best practices
   - Immutable state updates

4. **PostgreSQL Connection Pooling**
   - psycopg3 AsyncConnectionPool
   - Performance tuning

---

## ⚠️ Common Pitfalls

### Pitfall 1: Sync/Async Mismatch
```python
# ❌ Wrong
checkpointer = PostgresSaver.from_conn_string(dsn)
result = await graph.ainvoke(...)  # Mismatch!

# ✅ Correct
async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
    result = await graph.ainvoke(...)
```

### Pitfall 2: Using interrupt_before for HIL
```python
# ❌ Wrong (for production HIL)
graph = builder.compile(interrupt_before=["approval"])

# ✅ Correct
response = interrupt(request_data)
```

### Pitfall 3: Manual Checkpoint Table Creation
```python
# ❌ Wrong
CREATE TABLE checkpoints (...);

# ✅ Correct
await checkpointer.setup()  # Auto-creates tables
```

### Pitfall 4: Mutating State
```python
# ❌ Wrong
state["key"] = "value"
return state

# ✅ Correct
return state | {"key": "value"}
```

---

**Last Updated**: 2025-10-27
**Maintained By**: AI-1
**Based On**: LangGraph Official Documentation v2.0
