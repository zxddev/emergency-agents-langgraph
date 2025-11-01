from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from emergency_agents.services.rescue_draft_service import RescueDraftService


class _StubIncidentRepository:
    async def create_entity_with_link(self, *_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
        raise NotImplementedError


class _StubSnapshotRepository:
    def __init__(self) -> None:
        self.storage: Dict[str, SimpleNamespace] = {}
        self.created_order: list[str] = []

    async def create_snapshot(self, payload: Any) -> SimpleNamespace:
        snapshot_id = f"draft-{len(self.storage) + 1}"
        record = SimpleNamespace(
            snapshot_id=snapshot_id,
            incident_id=payload.incident_id,
            snapshot_type=payload.snapshot_type,
            payload=payload.payload,
            generated_at=payload.generated_at,
            created_by=payload.created_by,
            created_at=payload.generated_at,
        )
        self.storage[snapshot_id] = record
        self.created_order.append(snapshot_id)
        return record

    async def get_snapshot(self, snapshot_id: str) -> Optional[SimpleNamespace]:
        return self.storage.get(snapshot_id)

    async def delete_snapshot(self, snapshot_id: str) -> None:
        self.storage.pop(snapshot_id, None)


class _StubTaskRepository:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def create_task(self, payload: Any) -> SimpleNamespace:
        self.calls.append(payload)
        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            id="task-1",
            task_type=payload.task_type,
            status=payload.status,
            priority=payload.priority,
            description=payload.description,
            deadline=payload.deadline,
            progress=0,
            event_id=payload.event_id,
            code=payload.code,
            created_at=now,
            updated_at=now,
        )


@pytest.fixture()
def draft_service_components() -> tuple[RescueDraftService, _StubSnapshotRepository, _StubTaskRepository]:
    snapshot_repo = _StubSnapshotRepository()
    task_repo = _StubTaskRepository()
    service = RescueDraftService(
        incident_repository=_StubIncidentRepository(),
        snapshot_repository=snapshot_repo,
        task_repository=task_repo,
    )
    return service, snapshot_repo, task_repo


@pytest.mark.anyio
async def test_save_and_load_roundtrip(draft_service_components: tuple[RescueDraftService, _StubSnapshotRepository, _StubTaskRepository]) -> None:
    service, snapshot_repo, _ = draft_service_components
    plan_payload: Dict[str, Any] = {
        "response_text": "推荐调派 A 队救援",
        "analysis_summary": {"matched_count": 2},
        "plan": {
            "overview": {
                "situationSummary": "受灾建筑倒塌",
                "analysis": {"matched_count": 2},
            },
            "lines": [],
            "resources": [],
            "risks": [],
            "evidenceTrace": [],
        },
    }
    record = await service.save_draft(
        incident_id="incident-1",
        entity=None,
        plan=plan_payload,
        risk_summary={"count": 1},
        ui_actions=[{"action": "open_panel", "payload": {}}],
        created_by="tester",
    )
    assert record.draft_id in snapshot_repo.storage
    loaded = await service.load_draft(record.draft_id)
    assert loaded.plan["plan"]["overview"]["situationSummary"] == "受灾建筑倒塌"
    assert loaded.risk_summary["count"] == 1
    assert loaded.ui_actions[0]["action"] == "open_panel"


@pytest.mark.anyio
async def test_confirm_draft_generates_description(draft_service_components: tuple[RescueDraftService, _StubSnapshotRepository, _StubTaskRepository]) -> None:
    service, snapshot_repo, task_repo = draft_service_components
    plan_payload: Dict[str, Any] = {
        "response_text": "  ",
        "analysis_summary": {"matched_count": 3},
        "plan": {
            "overview": {
                "situationSummary": "坍塌救援",
                "analysis": {"matched_count": 3},
            },
            "lines": [],
            "resources": [],
            "risks": [],
            "evidenceTrace": [],
        },
    }
    record = await service.save_draft(
        incident_id="incident-2",
        entity=None,
        plan=plan_payload,
        risk_summary={},
        ui_actions=[],
        created_by="tester",
    )
    task = await service.confirm_draft(
        record.draft_id,
        commander_id="commander-1",
        priority=80,
        description=None,
        deadline=None,
        task_code=None,
    )
    assert task.description == "生成救援方案，匹配 3 支力量"
    assert record.draft_id not in snapshot_repo.storage
    assert task_repo.calls, "任务写入应当被调用"


@pytest.mark.anyio
async def test_load_missing_draft_raises(draft_service_components: tuple[RescueDraftService, _StubSnapshotRepository, _StubTaskRepository]) -> None:
    service, _, _ = draft_service_components
    with pytest.raises(ValueError):
        await service.load_draft("missing-draft")
