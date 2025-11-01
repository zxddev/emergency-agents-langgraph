from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from emergency_agents.db.dao import TaskDAO, serialize_dataclass, serialize_iter
from emergency_agents.db.models import TaskLogEntry, TaskRoutePlan, TaskSummary
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import TaskProgressQuerySlots

logger = logging.getLogger(__name__)


@dataclass
class TaskProgressQueryHandler(IntentHandler[TaskProgressQuerySlots]):
    task_dao: TaskDAO

    async def handle(self, slots: TaskProgressQuerySlots, state: dict[str, object]) -> dict[str, object]:
        logger.info(
            "intent_request",
            extra={
                "intent": "task-progress-query",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "target": slots.task_id or slots.task_code,
                "status": "processing",
            },
        )

        task = await self._fetch_task(slots)
        if task is None:
            message = "未找到匹配的任务，请确认任务编号或ID。"
            return {
                "response_text": message,
                "task_progress": None,
            }

        logs = await self._fetch_latest_log(task.id)
        routes = await self._fetch_routes(task.id) if slots.need_route else []

        message_parts = [
            f"任务 {task.code or task.id} 当前状态：{task.status}，完成度 {task.progress if task.progress is not None else 0}%",
            f"最近更新时间：{task.updated_at:%Y-%m-%d %H:%M:%S}",
        ]
        if logs is not None and logs.description:
            ts = logs.timestamp.strftime("%Y-%m-%d %H:%M") if logs.timestamp else "未知时间"
            message_parts.append(f"最新日志({ts}，{logs.recorder_name or '系统'}): {logs.description}")
        if routes:
            message_parts.append(
                "路线规划：" + "; ".join(
                    f"策略{route.strategy or '-'} 距离{route.distance_meters or 0:.0f}米 预计{route.duration_seconds or 0}秒"
                    for route in routes
                )
            )

        message = "\n".join(message_parts)
        payload: dict[str, Any] = {
            "task": serialize_dataclass(task),
            "latest_log": self._serialize_log(logs),
            "routes": serialize_iter(routes),
        }
        return {
            "response_text": message,
            "task_progress": payload,
        }

    async def _fetch_task(self, slots: TaskProgressQuerySlots) -> TaskSummary | None:
        params: dict[str, Any] = {}
        if slots.task_id:
            params["task_id"] = slots.task_id
        if slots.task_code:
            params["task_code"] = slots.task_code
        if not params:
            raise ValueError("task_id or task_code required")
        return await self.task_dao.fetch_task(params)

    async def _fetch_latest_log(self, task_id: str) -> TaskLogEntry | None:
        return await self.task_dao.fetch_latest_log(str(task_id))

    async def _fetch_routes(self, task_id: str) -> list[TaskRoutePlan]:
        return await self.task_dao.fetch_routes(str(task_id))

    @staticmethod
    def _serialize_log(log: TaskLogEntry | None) -> dict[str, Any] | None:
        if log is None:
            return None
        data = serialize_dataclass(log)
        if log.timestamp is not None:
            data["timestamp"] = log.timestamp.isoformat()
        return data
