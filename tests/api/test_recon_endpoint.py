"""侦察接口单元测试。"""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from emergency_agents.api.recon import router as recon_router
from emergency_agents.external.recon_gateway import ReconPlanDraft
from emergency_agents.planner.recon_models import (
    GeoPoint,
    ReconConstraint,
    ReconJustification,
    ReconPlan,
    ReconPlanMeta,
    ReconSector,
    ReconTask,
    TaskPlanPayload,
)


def _sample_plan() -> ReconPlan:
    """构造固定的侦察方案，便于测试。"""

    task = ReconTask(
        task_id="task-001",
        title="空中巡检",
        objective="确认泄漏范围",
        target_points=[GeoPoint(lon=103.8, lat=31.6)],
        recommended_devices=["drone-v-1"],
    )
    return ReconPlan(
        objectives=["精准识别危化泄漏"],
        sectors=[
            ReconSector(
                sector_id="sec-1",
                name="北区",
                area=[GeoPoint(lon=103.8, lat=31.6)],
                tasks=[task.task_id],
            )
        ],
        tasks=[task],
        assets=[],
        constraints=[ReconConstraint(name="no_fly", detail="高压线旁限制飞行")],
        justification=ReconJustification(
            summary="根据危化关键词触发无人机侦察",
            evidence=[],
            reasoning_chain=[],
            risk_warnings=[],
        ),
        meta=ReconPlanMeta(),
    )


class DummyGraph:
    """替身 LangGraph，模拟完整流程。"""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def invoke(self, state: dict[str, str]) -> dict[str, object]:
        command = state.get("command_text", "")
        self.calls.append(command)
        plan = _sample_plan()
        payload = TaskPlanPayload(
            scheme_id="11111111-1111-1111-1111-111111111111",
            task_id=plan.tasks[0].task_id,
            objective=plan.tasks[0].objective,
            target_points=plan.tasks[0].target_points,
            recommended_devices=plan.tasks[0].recommended_devices,
        )
        return {
            "plan": plan,
            "draft": ReconPlanDraft(
                summary="测试草稿",
                plan_payload=plan.model_dump(mode="json"),
                tasks_payload=[payload],
            ),
        }


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(recon_router)
    return app


def test_create_recon_plan_success():
    app = _build_app()
    graph = DummyGraph()
    app.state.recon_graph = graph

    client = TestClient(app)
    response = client.post(
        "/recon/plans",
        json={
            "event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "command_text": "北侧危化泄漏请立即侦察",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["objectives"][0] == "精准识别危化泄漏"
    assert data["plan_summary"] == "测试草稿"
    assert data["plan_payload"]["objectives"][0] == "精准识别危化泄漏"
    assert data["tasks"][0]["scheme_id"] == "11111111-1111-1111-1111-111111111111"
    assert graph.calls == ["北侧危化泄漏请立即侦察"]


def test_create_recon_plan_missing_graph():
    app = _build_app()
    app.state.recon_graph = None
    client = TestClient(app)

    response = client.post(
        "/recon/plans",
        json={
            "event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "command_text": "北侧危化泄漏请立即侦察",
        },
    )

    assert response.status_code == 503
