from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from psycopg.rows import DictRow, class_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversationRecord:
    """数据库 conversations 表的强类型映射。"""

    id: int
    user_id: str
    thread_id: str
    started_at: datetime
    last_message_at: datetime
    metadata: dict[str, Any]


@dataclass(slots=True)
class MessageRecord:
    """数据库 messages 表的强类型映射。"""

    id: int
    conversation_id: int
    role: str
    content: str
    intent_type: str | None
    event_time: datetime
    metadata: dict[str, Any]


class ConversationNotFoundError(RuntimeError):
    """线程对应的会话不存在。"""

    def __init__(self, thread_id: str) -> None:
        super().__init__(f"conversation for thread_id={thread_id!r} not found")
        self.thread_id = thread_id


class ConversationManager:
    """基于 PostgreSQL 的会话/消息管理器。"""

    def __init__(self, pool: AsyncConnectionPool[DictRow]) -> None:
        self._pool: AsyncConnectionPool[DictRow] = pool

    async def fetch_conversation(self, thread_id: str) -> ConversationRecord | None:
        """仅查询会话，不创建新记录。"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRecord)) as cur:
                await cur.execute(
                    """
                    SELECT id,
                           user_id,
                           thread_id,
                           started_at,
                           last_message_at,
                           metadata
                      FROM operational.conversations
                     WHERE thread_id = %(thread_id)s
                    """,
                    {"thread_id": thread_id},
                )
                return await cur.fetchone()

    async def create_or_get_conversation(
        self,
        user_id: str,
        thread_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> ConversationRecord:
        """创建或获取 thread_id 对应的会话。"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRecord)) as cur:
                await cur.execute(
                    """
                    SELECT id,
                           user_id,
                           thread_id,
                           started_at,
                           last_message_at,
                           metadata
                      FROM operational.conversations
                     WHERE thread_id = %(thread_id)s
                    """,
                    {"thread_id": thread_id},
                )
                existing = await cur.fetchone()

            if existing is not None:
                if existing.user_id != user_id:
                    raise ValueError(
                        f"thread_id={thread_id!r} owned by {existing.user_id}, requested by {user_id}"
                    )
                return existing

            payload = {
                "user_id": user_id,
                "thread_id": thread_id,
                "metadata": json.dumps(metadata or {}),
            }
            async with conn.cursor(row_factory=class_row(ConversationRecord)) as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.conversations (user_id, thread_id, metadata)
                    VALUES (%(user_id)s, %(thread_id)s, %(metadata)s::jsonb)
                    RETURNING id,
                              user_id,
                              thread_id,
                              started_at,
                              last_message_at,
                              metadata
                    """,
                    payload,
                )
                created = await cur.fetchone()
                if created is None:
                    raise RuntimeError("failed to create conversation record")
                return created

    async def save_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        intent_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        conversation_metadata: Mapping[str, Any] | None = None,
    ) -> MessageRecord:
        """写入消息记录。"""
        conversation = await self.create_or_get_conversation(
            user_id=user_id,
            thread_id=thread_id,
            metadata=conversation_metadata,
        )
        async with self._pool.connection() as conn:
            merged_metadata: dict[str, Any] = dict(conversation.metadata or {})
            if conversation_metadata:
                has_change = False
                for key, value in conversation_metadata.items():
                    if merged_metadata.get(key) != value:
                        merged_metadata[key] = value
                        has_change = True
                if has_change:
                    async with conn.cursor() as cur_meta:
                        await cur_meta.execute(
                            """
                            UPDATE operational.conversations
                               SET metadata = %(metadata)s::jsonb
                             WHERE id = %(conversation_id)s
                            """,
                            {
                                "metadata": json.dumps(merged_metadata),
                                "conversation_id": conversation.id,
                            },
                        )
                    conversation.metadata = merged_metadata
            async with conn.cursor(row_factory=class_row(MessageRecord)) as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.messages (conversation_id, role, content, intent_type, metadata)
                    VALUES (%(conversation_id)s, %(role)s, %(content)s, %(intent_type)s, %(metadata)s::jsonb)
                    RETURNING id,
                              conversation_id,
                              role,
                              content,
                              intent_type,
                              event_time,
                              metadata
                    """,
                    {
                        "conversation_id": conversation.id,
                        "role": role,
                        "content": content,
                        "intent_type": intent_type,
                        "metadata": json.dumps(metadata or {}),
                    },
                )
                inserted = await cur.fetchone()
                if inserted is None:
                    raise RuntimeError("failed to insert message")
            async with conn.cursor() as cur_update:
                await cur_update.execute(
                    """
                    UPDATE operational.conversations
                       SET last_message_at = now()
                     WHERE id = %(conversation_id)s
                    """,
                    {"conversation_id": conversation.id},
                )
                return inserted

    async def get_history(self, thread_id: str, limit: int = 20) -> list[MessageRecord]:
        """获取 thread_id 对应会话的最近若干条消息（按时间升序）。"""
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(ConversationRecord)) as cur_conv:
                await cur_conv.execute(
                    """
                    SELECT id,
                           user_id,
                           thread_id,
                           started_at,
                           last_message_at,
                           metadata
                      FROM operational.conversations
                     WHERE thread_id = %(thread_id)s
                    """,
                    {"thread_id": thread_id},
                )
                conv = await cur_conv.fetchone()
                if conv is None:
                    raise ConversationNotFoundError(thread_id)

            async with conn.cursor(row_factory=class_row(MessageRecord)) as cur_msg:
                await cur_msg.execute(
                    """
                    SELECT id,
                           conversation_id,
                           role,
                           content,
                           intent_type,
                           event_time,
                           metadata
                      FROM operational.messages
                     WHERE conversation_id = %(conversation_id)s
                     ORDER BY event_time ASC
                     LIMIT %(limit)s
                    """,
                    {"conversation_id": conv.id, "limit": limit},
                )
                rows: Sequence[MessageRecord] = await cur_msg.fetchall()
                return list(rows)
