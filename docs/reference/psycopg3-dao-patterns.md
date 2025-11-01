# psycopg3 Async DAO Patterns Reference

**Purpose**: Official psycopg3 async patterns for building type-safe DAOs with AsyncConnectionPool.

**Target Audience**: AI-1 (infrastructure), backend developers implementing DAOs

## 📚 Table of Contents

1. [AsyncConnectionPool Setup](#asyncconnectionpool-setup)
2. [Strongly-Typed Results with class_row](#strongly-typed-results-with-class_row)
3. [Async Context Managers](#async-context-managers)
4. [Transaction Management](#transaction-management)
5. [Type Safety Patterns](#type-safety-patterns)
6. [Error Handling](#error-handling)
7. [Performance Optimization](#performance-optimization)
8. [Testing Strategies](#testing-strategies)

---

## AsyncConnectionPool Setup

### Basic Pool Configuration

```python
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import AsyncDictRow

async def create_pool(dsn: str) -> AsyncConnectionPool[AsyncDictRow]:
    """Create async connection pool"""

    # ✅ Correct: Configure pool parameters
    pool: AsyncConnectionPool[AsyncDictRow] = AsyncConnectionPool(
        dsn,
        min_size=2,     # Minimum connections
        max_size=10,    # Maximum connections
        timeout=30,     # Connection timeout (seconds)
        open=True       # Open pool immediately
    )

    return pool
```

### Pool Parameters Explained

| Parameter | Description | Recommended Value |
|-----------|-------------|-------------------|
| `min_size` | Minimum pooled connections | 2 (avoids cold starts) |
| `max_size` | Maximum pooled connections | 10 (based on workload) |
| `timeout` | Connection acquisition timeout | 30 seconds |
| `open` | Open pool immediately | True (fail fast) |

### Factory Pattern for DAO

```python
from typing import AsyncConnectionPool
from psycopg.rows import AsyncDictRow

class AsyncConversationDAO:
    """Async DAO with connection pool"""

    def __init__(self, pool: AsyncConnectionPool[AsyncDictRow]) -> None:
        self._pool: AsyncConnectionPool[AsyncDictRow] = pool

    # ... DAO methods ...


async def create_async_conversation_dao(
    dsn: str,
    min_size: int = 2,
    max_size: int = 10
) -> AsyncConversationDAO:
    """Factory function for DAO creation"""

    pool: AsyncConnectionPool[AsyncDictRow] = AsyncConnectionPool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        open=True
    )

    return AsyncConversationDAO(pool)
```

---

## Strongly-Typed Results with class_row

### Define TypedDict for Row Results

```python
from typing import TypedDict, NotRequired
from datetime import datetime

class ConversationRow(TypedDict):
    """Strongly-typed conversation row"""
    # Required fields (no NotRequired)
    id: int
    user_id: str
    session_id: str
    start_time: datetime
    last_activity: datetime
    status: str

    # Optional fields (with NotRequired)
    rescue_id: NotRequired[str | None]
    intent_type: NotRequired[str | None]
    metadata: NotRequired[dict | None]
```

**Key Points**:
- Use `NotRequired[]` for nullable/optional columns
- Match field names exactly to SQL column names
- Use proper Python types (datetime, dict, list)

### Use class_row in Cursor

```python
from psycopg.rows import class_row

async def get_conversation_by_id(
    self,
    conversation_id: int
) -> ConversationRow | None:
    """Get conversation with strongly-typed result"""

    async with self._pool.connection() as conn:
        # ✅ Use class_row for type safety
        async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
            await cur.execute(
                "SELECT * FROM operational.ai_conversations WHERE id = %s",
                (conversation_id,)
            )

            # Return type is ConversationRow | None
            return await cur.fetchone()
```

### Why class_row?

**Without class_row** (dict rows):
```python
# ❌ Returns plain dict - no type safety
row = await cur.fetchone()  # dict[str, Any]
user_id = row["user_id"]  # No IDE autocomplete, no type checking
```

**With class_row** (TypedDict rows):
```python
# ✅ Returns TypedDict - full type safety
row = await cur.fetchone()  # ConversationRow | None
if row:
    user_id = row["user_id"]  # ✅ IDE autocomplete, mypy type checking
```

### Handling Nullable Fields

```python
class MessageRow(TypedDict):
    id: int
    conversation_id: int
    content: str
    intent_type: NotRequired[str | None]  # ✅ Nullable field
    slots: NotRequired[dict | None]       # ✅ Nullable JSON


async def get_message(self, message_id: int) -> MessageRow | None:
    async with self._pool.connection() as conn:
        async with conn.cursor(row_factory=class_row(MessageRow)) as cur:
            await cur.execute(
                "SELECT * FROM operational.ai_messages WHERE id = %s",
                (message_id,)
            )
            row = await cur.fetchone()

            if row:
                # ✅ Type-safe nullable field access
                intent: str | None = row.get("intent_type")
                slots: dict | None = row.get("slots")

            return row
```

---

## Async Context Managers

### Connection Context Manager

```python
async def my_dao_method(self) -> None:
    """Method using connection context manager"""

    # ✅ Correct: Use async with for automatic connection management
    async with self._pool.connection() as conn:
        # Connection acquired from pool
        # ... use connection ...
        pass
    # Connection automatically returned to pool
```

### Cursor Context Manager

```python
async def query_with_cursor(self) -> list[ConversationRow]:
    """Method using cursor context manager"""

    async with self._pool.connection() as conn:
        # ✅ Nested context managers for connection and cursor
        async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
            await cur.execute("SELECT * FROM operational.ai_conversations")
            return await cur.fetchall()
        # Cursor automatically closed
    # Connection automatically returned
```

### Transaction Context Manager

```python
async def create_conversation_with_message(
    self,
    user_id: str,
    session_id: str,
    message_content: str
) -> tuple[int, int]:
    """Atomic operation with transaction"""

    async with self._pool.connection() as conn:
        # ✅ Explicit transaction for multiple operations
        async with conn.transaction():
            # Create conversation
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_conversations (user_id, session_id)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (user_id, session_id)
                )
                result = await cur.fetchone()
                conversation_id = int(result[0])

            # Create message
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_messages (conversation_id, role, content)
                    VALUES (%s, 'user', %s)
                    RETURNING id
                    """,
                    (conversation_id, message_content)
                )
                result = await cur.fetchone()
                message_id = int(result[0])

            # ✅ Both operations committed together
            return (conversation_id, message_id)
        # Automatic commit on success, rollback on exception
```

---

## Transaction Management

### Auto-Commit (Default)

```python
async def simple_insert(self, user_id: str) -> int:
    """Single operation - auto-commit"""

    async with self._pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO operational.ai_conversations (user_id, session_id) VALUES (%s, %s) RETURNING id",
                (user_id, f"session-{user_id}")
            )
            result = await cur.fetchone()
            return int(result[0])
    # ✅ Auto-committed on context exit
```

### Explicit Transaction (Multiple Operations)

```python
async def batch_insert(self, items: list[dict]) -> list[int]:
    """Multiple operations - explicit transaction"""

    async with self._pool.connection() as conn:
        # ✅ Explicit transaction for atomicity
        async with conn.transaction():
            ids = []
            for item in items:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO operational.ai_messages (...) VALUES (...) RETURNING id",
                        (item["field1"], item["field2"])
                    )
                    result = await cur.fetchone()
                    ids.append(int(result[0]))
            return ids
        # ✅ All inserts committed together or all rolled back
```

### Manual Rollback

```python
async def conditional_transaction(self, data: dict) -> bool:
    """Transaction with conditional rollback"""

    async with self._pool.connection() as conn:
        async with conn.transaction() as tx:
            # Perform operations
            await conn.execute("INSERT INTO table1 ...")

            # Check condition
            if not validation_passes(data):
                # ✅ Manual rollback
                await tx.rollback()
                return False

            await conn.execute("INSERT INTO table2 ...")
            return True
        # Auto-commit if no rollback called
```

---

## Type Safety Patterns

### 100% Type Annotations

```python
from typing import Dict, Any

class AsyncConversationDAO:
    """Type-safe DAO with explicit annotations"""

    def __init__(self, pool: AsyncConnectionPool[AsyncDictRow]) -> None:
        self._pool: AsyncConnectionPool[AsyncDictRow] = pool

    async def create_conversation(
        self,
        user_id: str,
        session_id: str,
        rescue_id: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> ConversationRow:
        """Create conversation with full type annotations"""

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_conversations
                    (user_id, session_id, rescue_id, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (user_id, session_id, rescue_id, metadata)
                )

                row: ConversationRow | None = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Failed to create conversation")

                return row  # Type is ConversationRow
```

### Type Guards for Runtime Safety

```python
def is_valid_conversation_row(row: dict) -> bool:
    """Type guard for conversation row"""
    required_keys = {"id", "user_id", "session_id", "status"}
    return all(key in row for key in required_keys)


async def safe_get_conversation(
    self,
    conversation_id: int
) -> ConversationRow | None:
    """Type-safe get with runtime validation"""

    async with self._pool.connection() as conn:
        async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
            await cur.execute(
                "SELECT * FROM operational.ai_conversations WHERE id = %s",
                (conversation_id,)
            )

            row = await cur.fetchone()

            # ✅ Runtime type validation
            if row and not is_valid_conversation_row(row):
                raise ValueError(f"Invalid conversation row: {row}")

            return row
```

### Union Types for Nullable Returns

```python
async def get_message_by_id(
    self,
    message_id: int
) -> MessageRow | None:  # ✅ Explicit None in return type
    """Get message with nullable return"""

    async with self._pool.connection() as conn:
        async with conn.cursor(row_factory=class_row(MessageRow)) as cur:
            await cur.execute(
                "SELECT * FROM operational.ai_messages WHERE id = %s",
                (message_id,)
            )

            row: MessageRow | None = await cur.fetchone()
            return row  # Can be None if not found
```

---

## Error Handling

### Connection Errors

```python
import logging
from psycopg import OperationalError

logger = logging.getLogger(__name__)

async def get_with_retry(
    self,
    conversation_id: int,
    max_retries: int = 3
) -> ConversationRow | None:
    """Get conversation with retry on connection error"""

    for attempt in range(max_retries):
        try:
            async with self._pool.connection() as conn:
                async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
                    await cur.execute(
                        "SELECT * FROM operational.ai_conversations WHERE id = %s",
                        (conversation_id,)
                    )
                    return await cur.fetchone()

        except OperationalError as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise  # Re-raise on last attempt
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return None
```

### Transaction Rollback

```python
async def safe_batch_insert(self, items: list[dict]) -> bool:
    """Batch insert with automatic rollback on error"""

    try:
        async with self._pool.connection() as conn:
            async with conn.transaction():
                for item in items:
                    async with conn.cursor() as cur:
                        await cur.execute("INSERT INTO ...", (...))
                # ✅ All inserts succeed
                return True

    except Exception as e:
        # ✅ Automatic rollback on exception
        logger.error(f"Batch insert failed: {e}", exc_info=True)
        return False
```

### Constraint Violations

```python
from psycopg import IntegrityError

async def create_with_conflict_handling(
    self,
    session_id: str
) -> ConversationRow | None:
    """Handle unique constraint violations"""

    try:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.ai_conversations (session_id, user_id)
                    VALUES (%s, %s)
                    RETURNING *
                    """,
                    (session_id, "user")
                )
                return await cur.fetchone()

    except IntegrityError as e:
        # ✅ Handle unique constraint violation
        logger.warning(f"Session {session_id} already exists: {e}")
        return None  # Or fetch existing
```

---

## Performance Optimization

### Batch Operations

```python
async def batch_insert_messages(
    self,
    messages: list[dict]
) -> list[int]:
    """Efficient batch insert using executemany"""

    async with self._pool.connection() as conn:
        async with conn.cursor() as cur:
            # ✅ Use executemany for batch operations
            await cur.executemany(
                """
                INSERT INTO operational.ai_messages
                (conversation_id, role, content)
                VALUES (%s, %s, %s)
                """,
                [(m["conversation_id"], m["role"], m["content"]) for m in messages]
            )

            # Get IDs of inserted messages
            await cur.execute("SELECT lastval()")
            last_id = (await cur.fetchone())[0]
            return list(range(last_id - len(messages) + 1, last_id + 1))
```

### Prepared Statements (Implicit)

```python
async def get_messages_by_conversation(
    self,
    conversation_id: int,
    limit: int = 50
) -> list[MessageRow]:
    """Query with reusable prepared statement"""

    # ✅ psycopg3 automatically caches prepared statements
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
    # Query plan cached after first execution
```

### Connection Pooling Best Practices

```python
# ✅ Good: Use pool efficiently
async def high_traffic_endpoint():
    dao = get_dao()  # Reuse DAO with pool

    # Short-lived connection usage
    async with dao._pool.connection() as conn:
        # Do work
        pass
    # Return connection to pool immediately

# ❌ Bad: Holding connections too long
async def bad_endpoint():
    async with dao._pool.connection() as conn:
        # Don't do slow operations here
        await asyncio.sleep(60)  # Blocks pool!
```

---

## Testing Strategies

### Mock Pool for Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_pool():
    """Mock AsyncConnectionPool for unit tests"""
    pool = MagicMock()
    conn = AsyncMock()
    cursor = AsyncMock()

    pool.connection.return_value.__aenter__.return_value = conn
    conn.cursor.return_value.__aenter__.return_value = cursor

    return pool, cursor


@pytest.mark.asyncio
async def test_create_conversation(mock_pool):
    """Unit test with mocked pool"""
    pool, cursor = mock_pool

    # Mock cursor response
    cursor.fetchone.return_value = {
        "id": 1,
        "user_id": "test",
        "session_id": "sess-001"
    }

    dao = AsyncConversationDAO(pool)
    result = await dao.create_conversation("test", "sess-001")

    assert result["id"] == 1
    cursor.execute.assert_called_once()
```

### Integration Tests with Real Database

```python
@pytest.fixture
async def test_pool(postgres_dsn):
    """Real connection pool for integration tests"""
    pool = AsyncConnectionPool(postgres_dsn, min_size=1, max_size=2, open=True)
    yield pool
    await pool.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_conversation_integration(test_pool):
    """Integration test with real database"""
    dao = AsyncConversationDAO(test_pool)

    result = await dao.create_conversation("test-user", "test-session")

    assert result["id"] > 0
    assert result["user_id"] == "test-user"
    assert result["session_id"] == "test-session"
```

---

## 📚 Official References

1. **psycopg3 Official Documentation**
   - https://www.psycopg.org/psycopg3/docs/
   - AsyncConnectionPool API

2. **psycopg3 Async Patterns**
   - https://www.psycopg.org/psycopg3/docs/advanced/async.html
   - Connection pooling guide

3. **Python typing Module**
   - https://docs.python.org/3/library/typing.html
   - TypedDict and NotRequired

---

## ⚠️ Common Pitfalls

### Pitfall 1: Not Using Context Managers
```python
# ❌ Wrong
conn = await pool.connection()
# ... use conn ...
await conn.close()  # Manual cleanup

# ✅ Correct
async with pool.connection() as conn:
    # ... use conn ...
# Automatic cleanup
```

### Pitfall 2: Forgetting Async/Await
```python
# ❌ Wrong
result = cur.fetchone()  # Missing await!

# ✅ Correct
result = await cur.fetchone()
```

### Pitfall 3: Not Using class_row
```python
# ❌ Wrong
async with conn.cursor() as cur:
    row = await cur.fetchone()  # dict[str, Any]

# ✅ Correct
async with conn.cursor(row_factory=class_row(ConversationRow)) as cur:
    row = await cur.fetchone()  # ConversationRow | None
```

### Pitfall 4: Pool Exhaustion
```python
# ❌ Wrong
for i in range(100):
    async with pool.connection() as conn:
        await long_operation()  # Holds connection too long

# ✅ Correct
connections = []
for i in range(100):
    async with pool.connection() as conn:
        data = await quick_query()
        connections.append(data)
    # Release connection immediately
```

---

**Last Updated**: 2025-10-27
**Maintained By**: AI-1
**Based On**: psycopg3 Official Documentation v3.2.0
