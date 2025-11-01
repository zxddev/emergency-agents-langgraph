from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pytest

pytest.importorskip("psycopg")

from emergency_agents.db.models import TaskLogEntry, TaskRoutePlan, TaskSummary
from emergency_agents.intent.handlers.task_progress import (
    TaskProgressQueryHandler,
)
from emergency_agents.intent.schemas import TaskProgressQuerySlots


class _FakeTaskDAO:
    def __init__(
        self,
        task: Optional[TaskSummary],
        log: Optional[TaskLogEntry],
        routes: list[TaskRoutePlan],
    ) -> None:
        self._task = task
        self._log = log
        self._routes = routes

    async def fetch_task(self, params: dict[str, Any]) -> TaskSummary | None:
        return self._task

    async def fetch_latest_log(self, task_id: str) -> TaskLogEntry | None:
        return self._log

    async def fetch_routes(self, task_id: str) -> list[TaskRoutePlan]:
        return self._routes


@pytest.mark.asyncio
async def test_task_progress_handler_returns_intent() -> None:
    dao = _FakeTaskDAO(
        task=TaskSummary(
            id="id-1",
            code="RESCUE-001",
            description="任务描述",
            status="in_progress",
            progress=50,
            updated_at=datetime(2025, 10, 27, 10, 0, 0),
        ),
        log=TaskLogEntry(
            description="已抵达现场",
            timestamp=datetime(2025, 10, 27, 9, 30),
            recorder_name="调度台",
        ),
        routes=[TaskRoutePlan(strategy="FASTEST", distance_meters=1200.0, duration_seconds=600)],
    )
    handler = TaskProgressQueryHandler(task_dao=dao)
    slots = TaskProgressQuerySlots(task_code="RESCUE-001")

    result = await handler.handle(slots, {"thread_id": "t", "user_id": "u"})
    assert "任务 RESCUE-001" in result["response_text"]
    assert result["task_progress"]["task"]["code"] == "RESCUE-001"
