from __future__ import annotations

"""会话上下文服务：管理每个 thread 的最近设备选择等上下文。

设计约束：
- 强类型；所有外部交互（数据库）均可追踪日志；不做兜底或猜测。
- 接口最小化：仅提供 get()/set_last_device() 两个操作，便于在 Validator/Handler/Processor 处复用。
"""

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

import structlog
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger(__name__)


class SessionContextRecord(TypedDict, total=False):
    """会话上下文字典模型。"""

    thread_id: str
    last_device_id: Optional[str]
    last_device_name: Optional[str]
    last_device_type: Optional[str]
    last_intent_type: Optional[str]
    last_task_id: Optional[str]
    last_task_code: Optional[str]
    last_incident_id: Optional[str]


@dataclass(slots=True)
class ContextService:
    """会话上下文服务。"""

    pool: AsyncConnectionPool[DictRow]

    async def get(self, thread_id: str) -> SessionContextRecord | None:
        """读取会话上下文。

        Args:
            thread_id: 线程ID（LangGraph 的 thread_id）。

        Returns:
            若存在返回记录字典，否则返回 None。
        """
        if not thread_id:
            raise ValueError("thread_id 不能为空")
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT thread_id,
                           last_device_id,
                           last_device_name,
                           last_device_type,
                           last_intent_type,
                           last_task_id,
                           last_task_code,
                           last_incident_id
                      FROM operational.session_context
                     WHERE thread_id = %(thread_id)s
                    """,
                    {"thread_id": thread_id},
                )
                row = await cur.fetchone()
                if row is None:
                    logger.info("session_context_not_found", thread_id=thread_id)
                    return None
                result: SessionContextRecord = {
                    "thread_id": row[0],
                    "last_device_id": row[1],
                    "last_device_name": row[2],
                    "last_device_type": row[3],
                    "last_intent_type": row[4],
                    "last_task_id": row[5],
                    "last_task_code": row[6],
                    "last_incident_id": row[7],
                }
                logger.info("session_context_loaded", thread_id=thread_id, has_device=bool(result.get("last_device_id")))
                return result

    async def set_last_device(
        self,
        *,
        thread_id: str,
        device_id: Optional[str],
        device_name: Optional[str],
        device_type: Optional[str],
        intent_type: Optional[str],
        ) -> None:
        """写入/更新最近设备。

        严格原则：入参不合法直接抛错；不静默兜底。
        """
        if not thread_id:
            raise ValueError("thread_id 不能为空")
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.session_context (
                        thread_id, last_device_id, last_device_name, last_device_type, last_intent_type
                    ) VALUES (%(thread_id)s, %(device_id)s, %(device_name)s, %(device_type)s, %(intent_type)s)
                    ON CONFLICT (thread_id) DO UPDATE
                        SET last_device_id = EXCLUDED.last_device_id,
                            last_device_name = EXCLUDED.last_device_name,
                            last_device_type = EXCLUDED.last_device_type,
                            last_intent_type = EXCLUDED.last_intent_type,
                            updated_at = now()
                    """,
                    {
                        "thread_id": thread_id,
                        "device_id": device_id,
                        "device_name": device_name,
                        "device_type": device_type,
                        "intent_type": intent_type,
                    },
                )
        logger.info(
            "session_context_saved",
            thread_id=thread_id,
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            intent_type=intent_type,
        )

    async def set_last_task(
        self,
        *,
        thread_id: str,
        task_id: Optional[str],
        task_code: Optional[str],
        intent_type: Optional[str] = None,
    ) -> None:
        """仅更新最近任务字段，保留其余上下文。

        - 不会清空设备/事件字段。
        - intent_type 仅做审计用途，可选。
        """
        if not thread_id:
            raise ValueError("thread_id 不能为空")
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.session_context (
                        thread_id, last_task_id, last_task_code, last_intent_type
                    ) VALUES (%(thread_id)s, %(task_id)s, %(task_code)s, %(intent_type)s)
                    ON CONFLICT (thread_id) DO UPDATE
                        SET last_task_id = EXCLUDED.last_task_id,
                            last_task_code = EXCLUDED.last_task_code,
                            last_intent_type = EXCLUDED.last_intent_type,
                            updated_at = now()
                    """,
                    {
                        "thread_id": thread_id,
                        "task_id": task_id,
                        "task_code": task_code,
                        "intent_type": intent_type,
                    },
                )
        logger.info(
            "session_context_task_saved",
            thread_id=thread_id,
            task_id=task_id,
            task_code=task_code,
            intent_type=intent_type,
        )

    async def set_last_incident(
        self,
        *,
        thread_id: str,
        incident_id: Optional[str],
        intent_type: Optional[str] = None,
    ) -> None:
        """仅更新最近事件字段，保留其余上下文。"""
        if not thread_id:
            raise ValueError("thread_id 不能为空")
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.session_context (
                        thread_id, last_incident_id, last_intent_type
                    ) VALUES (%(thread_id)s, %(incident_id)s, %(intent_type)s)
                    ON CONFLICT (thread_id) DO UPDATE
                        SET last_incident_id = EXCLUDED.last_incident_id,
                            last_intent_type = EXCLUDED.last_intent_type,
                            updated_at = now()
                    """,
                    {
                        "thread_id": thread_id,
                        "incident_id": incident_id,
                        "intent_type": intent_type,
                    },
                )
        logger.info(
            "session_context_incident_saved",
            thread_id=thread_id,
            incident_id=incident_id,
            intent_type=intent_type,
        )

    async def set_last_intent(
        self,
        *,
        thread_id: str,
        intent_type: Optional[str],
    ) -> None:
        """仅更新最近意图类型，保持其它上下文字段不变。"""

        if not thread_id:
            raise ValueError("thread_id 不能为空")
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO operational.session_context (
                        thread_id, last_intent_type
                    ) VALUES (%(thread_id)s, %(intent_type)s)
                    ON CONFLICT (thread_id) DO UPDATE
                        SET last_intent_type = EXCLUDED.last_intent_type,
                            updated_at = now()
                    """,
                    {
                        "thread_id": thread_id,
                        "intent_type": intent_type,
                    },
                )
        logger.info(
            "session_context_intent_saved",
            thread_id=thread_id,
            intent_type=intent_type,
        )
