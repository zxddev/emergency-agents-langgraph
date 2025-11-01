from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator, List, Mapping, Sequence, cast

import pytest

pytest.importorskip("psycopg")

from emergency_agents.memory.conversation_manager import (
    ConversationManager,
    ConversationNotFoundError,
    ConversationRecord,
    MessageRecord,
)


class _ScriptedCursor:
    def __init__(self, responses: Sequence[Any]) -> None:
        self._responses: List[Any] = list(responses)
        self.executed_sql: list[str] = []
        self.executed_params: list[dict[str, Any] | None] = []

    async def __aenter__(self) -> "_ScriptedCursor":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)

    async def fetchone(self) -> Any:
        return self._responses.pop(0) if self._responses else None

    async def fetchall(self) -> Sequence[Any]:
        if not self._responses:
            return []
        value = self._responses.pop(0)
        if isinstance(value, Sequence):
            return value
        return [value]


class _ScriptedConnection:
    def __init__(self, cursor_scripts: Sequence[Sequence[Any]]) -> None:
        self._iter: Iterator[Sequence[Any]] = iter(cursor_scripts)

    async def __aenter__(self) -> "_ScriptedConnection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def cursor(self, *args: Any, **kwargs: Any) -> _ScriptedCursor:
        try:
            script = next(self._iter)
        except StopIteration as exc:  # pragma: no cover - defensive
            raise RuntimeError("no cursor script available") from exc
        return _ScriptedCursor(script)


class _ScriptedPool:
    def __init__(self, scripts: Sequence[Sequence[Sequence[Any]]]) -> None:
        self._scripts: Iterator[Sequence[Sequence[Any]]] = iter(scripts)

    def connection(self) -> _ScriptedConnection:
        try:
            script = next(self._scripts)
        except StopIteration as exc:  # pragma: no cover - defensive
            raise RuntimeError("no connection script available") from exc
        return _ScriptedConnection(script)


def _conversation() -> ConversationRecord:
    now = datetime.now(timezone.utc)
    return ConversationRecord(
        id=1,
        user_id="user-1",
        thread_id="thread-1",
        started_at=now,
        last_message_at=now,
        metadata={},
    )


def _message(conversation_id: int = 1) -> MessageRecord:
    now = datetime.now(timezone.utc)
    return MessageRecord(
        id=10,
        conversation_id=conversation_id,
        role="assistant",
        content="ok",
        intent_type=None,
        event_time=now,
        metadata={},
    )


@pytest.mark.asyncio
async def test_create_or_get_creates_when_missing() -> None:
    conv = _conversation()
    pool = _ScriptedPool(
        scripts=(
            (
                [None],  # 初次查询返回空
                [conv],  # 插入后返回新会话
            ),
        )
    )
    manager = ConversationManager(cast(Any, pool))
    result = await manager.create_or_get_conversation("user-1", "thread-1")
    assert result == conv


@pytest.mark.asyncio
async def test_create_or_get_existing_mismatched_user() -> None:
    conv = _conversation()
    pool = _ScriptedPool(
        scripts=(
            (
                [conv],
            ),
        )
    )
    manager = ConversationManager(cast(Any, pool))
    with pytest.raises(ValueError):
        await manager.create_or_get_conversation("user-2", "thread-1")


@pytest.mark.asyncio
async def test_get_history_returns_messages() -> None:
    conv = _conversation()
    msg = _message(conversation_id=conv.id)
    pool = _ScriptedPool(
        scripts=(
            (
                [conv],
                [[msg]],
            ),
        )
    )
    manager = ConversationManager(cast(Any, pool))
    history = await manager.get_history("thread-1", limit=5)
    assert history == [msg]


@pytest.mark.asyncio
async def test_get_history_missing_conversation() -> None:
    pool = _ScriptedPool(
        scripts=(
            (
                [None],
            ),
        )
    )
    manager = ConversationManager(cast(Any, pool))
    with pytest.raises(ConversationNotFoundError):
        await manager.get_history("thread-1")


@pytest.mark.asyncio
async def test_save_message_inserts_record(monkeypatch: pytest.MonkeyPatch) -> None:
    conv = _conversation()
    msg = _message(conversation_id=conv.id)
    pool = _ScriptedPool(
        scripts=(
            (
                [msg],
                [],
            ),
        )
    )
    manager = ConversationManager(cast(Any, pool))

    async def _fake_create(user_id: str, thread_id: str, metadata: Mapping[str, Any] | None = None) -> ConversationRecord:
        assert user_id == conv.user_id
        assert thread_id == conv.thread_id
        return conv

    monkeypatch.setattr(manager, "create_or_get_conversation", _fake_create)  # type: ignore[arg-type]
    result = await manager.save_message(
        user_id="user-1",
        thread_id="thread-1",
        role="assistant",
        content="ok",
        conversation_metadata={},
    )
    assert result == msg
