from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from emergency_agents.api.rescue import router as rescue_router
from emergency_agents.services.rescue_draft_service import RescueDraftRecord


class _StubRescueDraftService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.record = RescueDraftRecord(
            draft_id="draft-1",
            incident_id="incident-1",
            entity_id="entity-1",
            plan={
                "plan": {
                    "overview": {"situationSummary": "演练"},
                    "lines": [],
                    "resources": [],
                    "risks": [],
                    "evidenceTrace": [],
                },
            },
            risk_summary={"count": 0},
            ui_actions=[],
            created_at=now,
            created_by="tester",
        )
        self.confirm_calls: list[Any] = []

    async def load_draft(self, draft_id: str) -> RescueDraftRecord:
        if draft_id != self.record.draft_id:
            raise ValueError(f"未找到草稿: {draft_id}")
        return self.record

    async def confirm_draft(
        self,
        draft_id: str,
        *,
        commander_id: str,
        priority: int,
        description: str | None,
        deadline: datetime | None,
        task_code: str | None,
    ) -> SimpleNamespace:
        if draft_id != self.record.draft_id:
            raise ValueError(f"未找到草稿: {draft_id}")
        self.confirm_calls.append((commander_id, priority, description, deadline, task_code))
        return SimpleNamespace(
            id="task-1",
            event_id=self.record.incident_id,
            status="pending",
            priority=priority,
            description=description or "生成救援方案",
        )


@pytest.fixture()
def draft_service() -> _StubRescueDraftService:
    return _StubRescueDraftService()


@pytest.fixture()
def test_app(draft_service: _StubRescueDraftService) -> TestClient:
    app = FastAPI()
    app.include_router(rescue_router)
    app.state.rescue_draft_service = draft_service
    return TestClient(app)


def test_get_rescue_draft_success(test_app: TestClient) -> None:
    response = test_app.get("/rescue/drafts/draft-1")
    assert response.status_code == 200
    body = response.json()
    assert body["draft_id"] == "draft-1"
    assert body["plan"]["plan"]["overview"]["situationSummary"] == "演练"


def test_get_rescue_draft_not_found(test_app: TestClient) -> None:
    response = test_app.get("/rescue/drafts/unknown")
    assert response.status_code == 404
    assert response.json()["detail"].startswith("未找到草稿")


def test_confirm_rescue_draft_success(test_app: TestClient, draft_service: _StubRescueDraftService) -> None:
    response = test_app.post(
        "/rescue/drafts/draft-1/confirm",
        json={"commander_id": "cmd", "priority": 60, "description": "",
              "deadline": None, "task_code": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-1"
    assert draft_service.confirm_calls, "confirm_draft 应被调用"


def test_confirm_rescue_draft_not_found(test_app: TestClient) -> None:
    response = test_app.post(
        "/rescue/drafts/missing/confirm",
        json={"commander_id": "cmd", "priority": 50, "description": None},
    )
    assert response.status_code == 404
    assert response.json()["detail"].startswith("未找到草稿")


def test_service_not_initialized() -> None:
    app = FastAPI()
    app.include_router(rescue_router)
    client = TestClient(app)
    response = client.get("/rescue/drafts/any")
    assert response.status_code == 503
