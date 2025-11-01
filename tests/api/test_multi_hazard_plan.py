from __future__ import annotations

from typing import Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient

from emergency_agents.api.plan import router as plan_router


def _candidate_payload() -> List[Dict[str, object]]:
    return [
        {
            "resource_id": "team_a",
            "name": "成都特勤",
            "kind": "rescue_team",
            "capabilities": ["collapse", "rope", "hazmat"],
            "equipment": ["rope", "cutters"],
            "location": {"lon": 103.81, "lat": 31.62},
            "availability": True,
        },
        {
            "resource_id": "uav_1",
            "name": "无人机1号",
            "kind": "uav",
            "capabilities": ["uav_operation", "thermal_imaging"],
            "equipment": ["thermal_camera"],
            "location": {"lon": 103.79, "lat": 31.60},
            "availability": True,
        },
    ]


def test_multi_hazard_plan_endpoint() -> None:
    app = FastAPI()
    app.include_router(plan_router)
    client = TestClient(app)

    payload = {
        "incident_id": "22222222-2222-2222-2222-222222222222",
        "hazard_type": "bridge_collapse",
        "severity_score": 75.0,
        "incident_point": {"lon": 103.80, "lat": 31.61},
        "candidates": _candidate_payload(),
        "metadata": {"requested_by": "pytest"},
    }

    resp = client.post("/ai/plan/multi-hazard", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    plan = body["plan"]
    assert plan["incident_id"] == payload["incident_id"]
    assert plan["hazard_type"] == "bridge_collapse"
    assert plan["tasks"], "任务列表不可为空"
    assert len(plan["tasks"]) >= 4
    assert "resource_matches" in plan
    assert isinstance(body["unmatched_tasks"], list)
