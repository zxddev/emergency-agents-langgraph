# Phase 1: Infrastructure Setup Guide (AI-1)

**Assignee**: AI-1
**Duration**: 1-2 days
**Branch**: `master` (direct commits)
**Goal**: Implement infrastructure to support Handler-based architecture with AsyncPostgresSaver and AsyncConversationDAO

## 📋 Prerequisites

Before starting, ensure you have read:
- [ ] `openspec/changes/conversation-management-v1/proposal.md`
- [ ] `openspec/changes/conversation-management-v1/design.md`
- [ ] `openspec/changes/conversation-management-v1/tasks.md`
- [ ] `openspec/changes/conversation-management-v1/specs/conversation-tracking/spec.md`
- [ ] `docs/reference/langgraph-best-practices.md`
- [ ] `docs/reference/psycopg3-dao-patterns.md`

## 🎯 Phase 1 Objectives

1. Create business database tables (conversation tracking)
2. Implement AsyncConversationDAO with 100% type annotations
3. Create Handler framework (IntentHandler + HandlerRegistry)
4. Modify app.py to use AsyncPostgresSaver
5. Modify approval node to use interrupt()
6. Update configuration files
7. Write infrastructure tests

## 📂 File Structure

```
src/emergency_agents/
├── intent/
│   ├── handlers/
│   │   ├── __init__.py (create)
│   │   └── base.py (create)
│   └── registry.py (create)
├── dao/
│   ├── __init__.py (create)
│   └── conversation.py (create)
└── graph/
    └── app.py (modify)

sql/
└── operational.sql (create)

config/
└── dev.env (modify)

tests/
├── test_handler_framework.py (create)
└── test_conversation_dao.py (create)
```

## 🔨 Implementation Steps

### Step 1: Create Business Database Tables

**File**: `sql/operational.sql`

```sql
-- =====================================================
-- Conversation Management Tables
-- Purpose: Track AI conversation history and intent logs
-- Schema: operational
-- =====================================================

-- Conversation sessions
CREATE TABLE IF NOT EXISTS operational.ai_conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    rescue_id VARCHAR(100),
    start_time TIMESTAMP NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
    intent_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON operational.ai_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON operational.ai_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_rescue_id ON operational.ai_conversations(rescue_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON operational.ai_conversations(status);

-- Message history
CREATE TABLE IF NOT EXISTS operational.ai_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES operational.ai_conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent_type VARCHAR(100),
    slots JSONB,
    validation_status VARCHAR(50),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON operational.ai_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON operational.ai_messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_intent_type ON operational.ai_messages(intent_type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON operational.ai_messages(timestamp);

-- Intent detection logs
CREATE TABLE IF NOT EXISTS operational.ai_intent_logs (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES operational.ai_conversations(id) ON DELETE CASCADE,
    input_text TEXT NOT NULL,
    detected_intent VARCHAR(100) NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    slots JSONB,
    validation_result VARCHAR(50),
    llm_model VARCHAR(100),
    llm_latency_ms INT CHECK (llm_latency_ms >= 0),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_intent_logs_conversation_id ON operational.ai_intent_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_intent_logs_detected_intent ON operational.ai_intent_logs(detected_intent);
CREATE INDEX IF NOT EXISTS idx_intent_logs_timestamp ON operational.ai_intent_logs(timestamp);

-- Auto-update last_activity trigger
CREATE OR REPLACE FUNCTION update_conversation_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE operational.ai_conversations
    SET last_activity = NOW(),
        updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_conversation_activity ON operational.ai_messages;
CREATE TRIGGER trigger_update_conversation_activity
AFTER INSERT ON operational.ai_messages
FOR EACH ROW
EXECUTE FUNCTION update_conversation_activity();
```

**Execution**:
```bash
psql "$POSTGRES_DSN" -f sql/operational.sql
```

### Step 2: Implement AsyncConversationDAO

**File**: `src/emergency_agents/dao/conversation.py`

```python
"""
AsyncConversationDAO - Async DAO for conversation tracking with 100% type annotations

Enforces mypy --strict compliance with explicit typing for all methods.
"""
from typing import Dict, Any, TypedDict, NotRequired
from datetime import datetime
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import AsyncDictRow, class_row
import logging

logger = logging.getLogger(__name__)


class ConversationRow(TypedDict):
    """Strongly-typed conversation row"""
    id: int
    user_id: str
    session_id: str
    rescue_id: NotRequired[str | None]
    start_time: datetime
    last_activity: datetime
    status: str
    intent_type: NotRequired[str | None]
    metadata: NotRequired[dict[str, Any] | None]
    created_at: datetime
    updated_at: datetime


class MessageRow(TypedDict):
    """Strongly-typed message row"""
    id: int
    conversation_id: int
    role: str
    content: str
    intent_type: NotRequired[str | None]
    slots: NotRequired[dict[str, Any] | None]
    validation_status: NotRequired[str | None]
    timestamp: datetime


class IntentLogRow(TypedDict):
    """Strongly-typed intent log row"""
    id: int
    conversation_id: int
    input_text: str
    detected_intent: str
    confidence: NotRequired[float | None]
    slots: NotRequired[dict[str, Any] | None]
    validation_result: NotRequired[str | None]
    llm_model: NotRequired[str | None]
    llm_latency_ms: NotRequired[int | None]
    timestamp: datetime


class AsyncConversationDAO:
    """Async DAO for conversation management with strong typing"""

    def __init__(self, pool: AsyncConnectionPool[AsyncDictRow]) -> None:
        self._pool: AsyncConnectionPool[AsyncDictRow] = pool

    async def create_conversation(
        self,
        user_id: str,
        session_id: str,
        rescue_id: str | None = None,
        intent_type: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> ConversationRow:
        """Create a new conversation"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_conversations
                    (user_id, session_id, rescue_id, intent_type, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (user_id, session_id, rescue_id, intent_type, metadata)
                )
                row: ConversationRow | None = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Failed to create conversation")
                return row

    async def get_conversation_by_id(self, conversation_id: int) -> ConversationRow | None:
        """Get conversation by ID"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
                await cur.execute(
                    "SELECT * FROM operational.ai_conversations WHERE id = %s",
                    (conversation_id,)
                )
                return await cur.fetchone()

    async def get_conversation_by_session(self, session_id: str) -> ConversationRow | None:
        """Get conversation by session ID"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
                await cur.execute(
                    "SELECT * FROM operational.ai_conversations WHERE session_id = %s",
                    (session_id,)
                )
                return await cur.fetchone()

    async def update_last_activity(self, conversation_id: int) -> None:
        """Update last activity timestamp"""
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE operational.ai_conversations
                    SET last_activity = NOW(), updated_at = NOW()
                    WHERE id = %s
                    """,
                    (conversation_id,)
                )

    async def archive_conversation(self, conversation_id: int) -> None:
        """Archive a conversation"""
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE operational.ai_conversations
                    SET status = 'archived', updated_at = NOW()
                    WHERE id = %s
                    """,
                    (conversation_id,)
                )

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        intent_type: str | None = None,
        slots: dict[str, Any] | None = None,
        validation_status: str | None = None
    ) -> int:
        """Add a message to conversation"""
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_messages
                    (conversation_id, role, content, intent_type, slots, validation_status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (conversation_id, role, content, intent_type, slots, validation_status)
                )
                result = await cur.fetchone()
                if result is None:
                    raise RuntimeError("Failed to add message")
                return int(result[0])

    async def get_messages(
        self,
        conversation_id: int,
        limit: int = 50
    ) -> list[MessageRow]:
        """Get messages for a conversation"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(MessageRow)) as cur:
                await cur.execute(
                    """
                    SELECT * FROM operational.ai_messages
                    WHERE conversation_id = %s
                    ORDER BY timestamp ASC
                    LIMIT %s
                    """,
                    (conversation_id, limit)
                )
                return await cur.fetchall()

    async def log_intent_detection(
        self,
        conversation_id: int,
        input_text: str,
        detected_intent: str,
        confidence: float | None = None,
        slots: dict[str, Any] | None = None,
        validation_result: str | None = None,
        llm_model: str | None = None,
        llm_latency_ms: int | None = None
    ) -> int:
        """Log an intent detection attempt"""
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_intent_logs
                    (conversation_id, input_text, detected_intent, confidence,
                     slots, validation_result, llm_model, llm_latency_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (conversation_id, input_text, detected_intent, confidence,
                     slots, validation_result, llm_model, llm_latency_ms)
                )
                result = await cur.fetchone()
                if result is None:
                    raise RuntimeError("Failed to log intent detection")
                return int(result[0])

    async def get_intent_logs(
        self,
        conversation_id: int
    ) -> list[IntentLogRow]:
        """Get intent logs for a conversation"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(IntentLogRow)) as cur:
                await cur.execute(
                    """
                    SELECT * FROM operational.ai_intent_logs
                    WHERE conversation_id = %s
                    ORDER BY timestamp ASC
                    """,
                    (conversation_id,)
                )
                return await cur.fetchall()


async def create_async_conversation_dao(
    dsn: str,
    min_size: int = 2,
    max_size: int = 10
) -> AsyncConversationDAO:
    """Factory function to create AsyncConversationDAO"""
    pool: AsyncConnectionPool[AsyncDictRow] = AsyncConnectionPool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        open=True
    )
    return AsyncConversationDAO(pool)
```

**File**: `src/emergency_agents/dao/__init__.py`
```python
from emergency_agents.dao.conversation import (
    AsyncConversationDAO,
    create_async_conversation_dao,
    ConversationRow,
    MessageRow,
    IntentLogRow
)

__all__ = [
    "AsyncConversationDAO",
    "create_async_conversation_dao",
    "ConversationRow",
    "MessageRow",
    "IntentLogRow"
]
```

### Step 3: Create Handler Framework

**File**: `src/emergency_agents/intent/handlers/base.py`

```python
"""
IntentHandler Abstract Base Class

All intent handlers must inherit from this class and implement the required methods.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, TypedDict, NotRequired


class ActionResult(TypedDict):
    """Strongly-typed action result"""
    success: bool
    message: str
    device_id: str
    action_type: str
    details: NotRequired[dict[str, Any] | None]


class IntentHandler(ABC):
    """Abstract base class for all intent handlers"""

    @classmethod
    @abstractmethod
    def get_intent_type(cls) -> str:
        """Return the intent type this handler handles"""
        pass

    @abstractmethod
    def validate_slots(self, slots: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate intent slots (business-level validation)

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_fields)
        """
        pass

    @abstractmethod
    async def execute_action(
        self,
        slots: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ActionResult:
        """
        Execute the action for this intent

        Args:
            slots: Intent slots (device_id, action, parameters)
            context: Execution context (java_api_base, conversation_dao, config)

        Returns:
            ActionResult: Execution result
        """
        pass
```

**File**: `src/emergency_agents/intent/handlers/__init__.py`
```python
from emergency_agents.intent.handlers.base import IntentHandler, ActionResult

__all__ = ["IntentHandler", "ActionResult"]
```

**File**: `src/emergency_agents/intent/registry.py`

```python
"""
HandlerRegistry - Auto-discovery and management of IntentHandlers

Uses pkgutil.iter_modules() to automatically discover all IntentHandler
implementations in the handlers package.
"""
from typing import Dict, Type, Iterator, Any, Callable
from types import ModuleType
import pkgutil
import importlib
import logging

from emergency_agents.intent.handlers.base import IntentHandler

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """Registry for auto-discovered intent handlers"""

    def __init__(self) -> None:
        self._handlers: Dict[str, Type[IntentHandler]] = {}
        self._node_mapping: Dict[str, str] = {}
        self._discover_handlers()

    def _discover_handlers(self) -> None:
        """Auto-discover all IntentHandler implementations"""
        import emergency_agents.intent.handlers as handlers_package

        module_iter: Iterator[tuple[Any, str, bool]] = pkgutil.iter_modules(
            handlers_package.__path__
        )

        for module_finder, module_name, is_pkg in module_iter:
            if module_name == "base":
                continue

            full_module_name: str = f"emergency_agents.intent.handlers.{module_name}"
            module: ModuleType = importlib.import_module(full_module_name)

            for attr_name in dir(module):
                attr: Any = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, IntentHandler) and
                    attr is not IntentHandler):
                    handler_class: Type[IntentHandler] = attr
                    intent_type: str = handler_class.get_intent_type()
                    node_name: str = f"{intent_type}_node"

                    self._handlers[intent_type] = handler_class
                    self._node_mapping[intent_type] = node_name

                    logger.info(
                        "[REGISTRY][DISCOVER] intent_type=%s | handler=%s | node=%s",
                        intent_type,
                        handler_class.__name__,
                        node_name
                    )

    def get_handler(self, intent_type: str) -> Type[IntentHandler] | None:
        """Get handler class by intent type"""
        return self._handlers.get(intent_type)

    def get_node_name(self, intent_type: str) -> str | None:
        """Get LangGraph node name for intent type"""
        return self._node_mapping.get(intent_type)

    def get_all_handlers(self) -> Dict[str, Type[IntentHandler]]:
        """Get all registered handlers"""
        return self._handlers.copy()

    def is_registered(self, intent_type: str) -> bool:
        """Check if intent type is registered"""
        return intent_type in self._handlers


# Singleton instance
_registry: HandlerRegistry | None = None


def get_handler_registry() -> HandlerRegistry:
    """Get singleton HandlerRegistry instance"""
    global _registry
    if _registry is None:
        _registry = HandlerRegistry()
    return _registry


def create_handler_node(
    handler_class: Type[IntentHandler],
    context: Dict[str, Any]
) -> Callable:
    """
    Factory function to create a LangGraph node from handler class

    Args:
        handler_class: IntentHandler subclass
        context: Execution context (java_api_base, conversation_dao, config)

    Returns:
        Callable node function for LangGraph
    """
    async def handler_node(state: Dict[str, Any]) -> Dict[str, Any]:
        handler = handler_class()
        slots: Dict[str, Any] = state.get("slots", {})

        # Validate slots
        is_valid, missing = handler.validate_slots(slots)
        if not is_valid:
            return state | {
                "validation_error": f"Missing required slots: {missing}"
            }

        # Execute action
        result = await handler.execute_action(slots, context)
        return state | {"action_result": result}

    return handler_node
```

### Step 4: Modify app.py for AsyncPostgresSaver

**File**: `src/emergency_agents/graph/app.py` (modifications)

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph, END
from emergency_agents.intent.registry import get_handler_registry, create_handler_node
from emergency_agents.dao import create_async_conversation_dao

# ... existing imports ...

async def build_emergency_graph(cfg: AppConfig) -> CompiledGraph:
    """Build LangGraph application with AsyncPostgresSaver"""

    # Use AsyncPostgresSaver (not PostgresSaver)
    async with AsyncPostgresSaver.from_conn_string(cfg.postgres_dsn) as checkpointer:
        await checkpointer.setup()  # Auto-create checkpoint tables

        # Create AsyncConversationDAO
        conversation_dao = await create_async_conversation_dao(
            cfg.postgres_dsn,
            min_size=cfg.postgres_pool_min_size,
            max_size=cfg.postgres_pool_max_size
        )

        # Handler context
        handler_context: Dict[str, Any] = {
            "java_api_base": cfg.java_api_base_url,
            "conversation_dao": conversation_dao,
            "config": cfg
        }

        builder = StateGraph(EmergencyState)

        # ... existing nodes ...

        # Auto-register all handlers
        registry = get_handler_registry()
        for intent_type, handler_class in registry.get_all_handlers().items():
            node_name = registry.get_node_name(intent_type)
            node_function = create_handler_node(handler_class, handler_context)
            builder.add_node(node_name, node_function)
            builder.add_edge(node_name, END)

        # ... existing edges ...

        return builder.compile(checkpointer=checkpointer)
```

### Step 5: Modify Approval Node for interrupt()

**File**: `src/emergency_agents/graph/nodes.py` (modify plan_approval_node)

```python
from langgraph.types import interrupt, Command

class ApprovalRequest(TypedDict):
    """Approval request payload"""
    plan_id: str
    plan_summary: str
    risk_level: str

class ApprovalResponse(TypedDict):
    """Approval response payload"""
    approved: bool
    approved_ids: NotRequired[list[str] | None]
    rejection_reason: NotRequired[str | None]

async def plan_approval_node(state: Dict[str, Any]) -> Command:
    """Human-in-the-loop approval node using interrupt()"""
    plan_details: dict[str, Any] = state.get("plan", {})

    request: ApprovalRequest = {
        "plan_id": plan_details.get("id", "unknown"),
        "plan_summary": plan_details.get("summary", ""),
        "risk_level": plan_details.get("risk_level", "medium")
    }

    # Dynamic interruption (correct approach)
    response: ApprovalResponse = interrupt(request)

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

### Step 6: Update Configuration

**File**: `config/dev.env` (add these lines)

```bash
# PostgreSQL Configuration
POSTGRES_DSN=postgresql://rescue:rescue_password@8.147.130.215:19532/rescue_system
POSTGRES_POOL_MIN_SIZE=2
POSTGRES_POOL_MAX_SIZE=10

# Java API Configuration
JAVA_API_BASE_URL=http://localhost:8080/api

# Conversation Tracking
ENABLE_CONVERSATION_TRACKING=true
```

### Step 7: Write Infrastructure Tests

**File**: `tests/test_handler_framework.py`

```python
"""Tests for Handler framework and Registry"""
import pytest
from emergency_agents.intent.handlers.base import IntentHandler, ActionResult
from emergency_agents.intent.registry import get_handler_registry, create_handler_node


class TestHandlerFramework:
    """Test Handler framework"""

    def test_handler_registry_singleton(self):
        """Registry should be singleton"""
        registry1 = get_handler_registry()
        registry2 = get_handler_registry()
        assert registry1 is registry2

    def test_handler_registry_discovers_handlers(self):
        """Registry should auto-discover handlers"""
        registry = get_handler_registry()
        handlers = registry.get_all_handlers()
        # At this point (Phase 1), no handlers should be registered yet
        assert isinstance(handlers, dict)

    def test_create_handler_node_type(self):
        """create_handler_node should return callable"""
        # Mock handler class
        class MockHandler(IntentHandler):
            @classmethod
            def get_intent_type(cls) -> str:
                return "test_intent"

            def validate_slots(self, slots):
                return (True, [])

            async def execute_action(self, slots, context):
                return ActionResult(
                    success=True,
                    message="test",
                    device_id="test-001",
                    action_type="test",
                    details=None
                )

        context = {"java_api_base": "http://test"}
        node = create_handler_node(MockHandler, context)
        assert callable(node)


@pytest.mark.asyncio
class TestHandlerNode:
    """Test handler node execution"""

    async def test_handler_node_execution(self):
        """Handler node should execute successfully"""
        # Mock handler
        class MockHandler(IntentHandler):
            @classmethod
            def get_intent_type(cls) -> str:
                return "test"

            def validate_slots(self, slots):
                return (True, [])

            async def execute_action(self, slots, context):
                return ActionResult(
                    success=True,
                    message="success",
                    device_id="test-001",
                    action_type="test",
                    details={}
                )

        context = {}
        node = create_handler_node(MockHandler, context)

        state = {"slots": {"device_id": "test-001"}}
        result = await node(state)

        assert "action_result" in result
        assert result["action_result"]["success"] is True
```

**File**: `tests/test_conversation_dao.py`

```python
"""Tests for AsyncConversationDAO"""
import pytest
from emergency_agents.dao import create_async_conversation_dao


@pytest.mark.asyncio
@pytest.mark.integration
class TestAsyncConversationDAO:
    """Integration tests for AsyncConversationDAO"""

    async def test_create_conversation(self, postgres_dsn):
        """Should create conversation successfully"""
        dao = await create_async_conversation_dao(postgres_dsn)

        conv = await dao.create_conversation(
            user_id="test-user",
            session_id="test-session-001"
        )

        assert conv["id"] > 0
        assert conv["user_id"] == "test-user"
        assert conv["session_id"] == "test-session-001"
        assert conv["status"] == "active"

    async def test_add_message(self, postgres_dsn):
        """Should add message successfully"""
        dao = await create_async_conversation_dao(postgres_dsn)

        conv = await dao.create_conversation(
            user_id="test-user",
            session_id="test-session-002"
        )

        message_id = await dao.add_message(
            conversation_id=conv["id"],
            role="user",
            content="Test message"
        )

        assert message_id > 0

        messages = await dao.get_messages(conv["id"])
        assert len(messages) == 1
        assert messages[0]["content"] == "Test message"
```

## ✅ Testing and Validation

### Run Tests
```bash
# Unit tests (no external dependencies)
pytest tests/test_handler_framework.py -v

# Integration tests (requires PostgreSQL)
pytest tests/test_conversation_dao.py -m integration -v

# Type checking
mypy src/emergency_agents/dao/ --strict
mypy src/emergency_agents/intent/ --strict
```

### Manual Validation
```bash
# 1. Create tables
psql "$POSTGRES_DSN" -f sql/operational.sql

# 2. Test DAO
python -c "
import asyncio
from emergency_agents.dao import create_async_conversation_dao
import os

async def test():
    dao = await create_async_conversation_dao(os.getenv('POSTGRES_DSN'))
    conv = await dao.create_conversation('user-1', 'sess-1')
    print(f'Created conversation: {conv}')

asyncio.run(test())
"

# 3. Test Registry
python -c "
from emergency_agents.intent.registry import get_handler_registry

registry = get_handler_registry()
print(f'Registered handlers: {registry.get_all_handlers()}')
"
```

## 📊 Success Criteria

- [ ] SQL tables created successfully
- [ ] AsyncConversationDAO passes all tests
- [ ] mypy --strict passes for DAO and intent modules
- [ ] HandlerRegistry initializes without errors
- [ ] Graph compiles with AsyncPostgresSaver
- [ ] Approval node uses interrupt() correctly
- [ ] Configuration files updated
- [ ] All infrastructure tests pass

## 🚨 Common Issues and Solutions

### Issue 1: PostgreSQL Connection Fails
**Solution**: Check POSTGRES_DSN format and network connectivity
```bash
psql "$POSTGRES_DSN" -c "SELECT 1"
```

### Issue 2: Type Errors with mypy --strict
**Solution**: Ensure all methods have explicit return types and parameter types

### Issue 3: Registry Doesn't Discover Handlers
**Solution**: Verify `__init__.py` exists in handlers package

### Issue 4: AsyncPostgresSaver Import Error
**Solution**: Install langgraph-checkpoint-postgres
```bash
pip install langgraph-checkpoint-postgres>=2.0.0
```

## 📚 References

- LangGraph AsyncPostgresSaver: `docs/reference/langgraph-best-practices.md`
- psycopg3 Async Patterns: `docs/reference/psycopg3-dao-patterns.md`
- Handler Registry API: `docs/reference/handler-registry-api.md`

## ⏭️ Next Steps

After Phase 1 completion:
1. Commit all changes to `master`
2. Tag release: `git tag phase1-complete`
3. Notify AI-2/3/4 to begin Phase 2 parallel development
4. Monitor Phase 2 progress and answer questions

---

**Duration Estimate**: 1-2 days
**Complexity**: Medium
**Critical Path**: Yes (blocks Phase 2)
