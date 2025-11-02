from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from emergency_agents.db.models import (
    IncidentSnapshotCreateInput,
    IncidentSnapshotRecord,
)
from emergency_agents.services.rescue_draft_service import RescueDraftService, RescueDraftRecord


class _DummyIncidentRepository:
    """空壳实现，占位满足构造函数依赖。"""


class _DummyTaskRepository:
    """空壳实现，测试过程中不会触发写任务。"""

    async def create_task(self, payload: Any) -> None:
        raise AssertionError("不会在草稿保存阶段写任务")


class _DummySnapshotRepository:
    """用于捕获传入的快照数据，验证序列化行为。"""

    def __init__(self) -> None:
        self.last_input: Optional[IncidentSnapshotCreateInput] = None

    async def create_snapshot(self, payload: IncidentSnapshotCreateInput) -> IncidentSnapshotRecord:
        self.last_input = payload
        return IncidentSnapshotRecord(
            snapshot_id="snapshot-1",
            incident_id=payload.incident_id,
            snapshot_type=payload.snapshot_type,
            payload=payload.payload,
            generated_at=payload.generated_at,
            created_by=payload.created_by,
            created_at=payload.generated_at,
        )


@pytest.mark.asyncio
async def test_save_draft_serializes_complex_types() -> None:
    """验证草稿保存时能正确序列化 datetime 等复杂类型。"""

    snapshot_repo = _DummySnapshotRepository()
    service = RescueDraftService(
        incident_repository=_DummyIncidentRepository(),
        snapshot_repository=snapshot_repo,
        task_repository=_DummyTaskRepository(),
    )

    plan_payload = {
        "plan": {"overview": {"generated_at": datetime(2025, 1, 1, 8, 30)}},
        "persisted_task": {
            "id": "task-1",
            "created_at": datetime(2025, 1, 1, 8, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, 9, 0),
        },
    }
    risk_summary = {"generated_at": datetime(2025, 1, 1, 8, 45)}
    ui_actions = [{"action": "show_toast", "timestamp": datetime(2025, 1, 1, 8, 30)}]

    record = await service.save_draft(
        incident_id="00000000-0000-0000-0000-000000000001",
        entity=None,
        plan=plan_payload,
        risk_summary=risk_summary,
        ui_actions=ui_actions,
        created_by="tester",
    )

    assert snapshot_repo.last_input is not None, "快照写入未被调用"
    stored_payload = snapshot_repo.last_input.payload

    persisted_task = stored_payload["plan"]["persisted_task"]
    assert isinstance(persisted_task["created_at"], str)
    assert persisted_task["created_at"].endswith("Z")
    assert isinstance(persisted_task["updated_at"], str)

    stored_action = stored_payload["ui_actions"][0]
    assert isinstance(stored_action["timestamp"], str)
    assert stored_action["timestamp"].endswith("Z")

    assert isinstance(record, RescueDraftRecord)
    assert isinstance(record.plan["persisted_task"]["created_at"], str)
    assert record.plan["persisted_task"]["created_at"].endswith("Z")
