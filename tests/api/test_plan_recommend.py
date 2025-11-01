from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient

from emergency_agents.api.plan import router as plan_router


def _req_payload(units_count: int = 3) -> Dict[str, Any]:
    units: List[Dict[str, Any]] = []
    for i in range(units_count):
        units.append(
            {
                "id": f"team-{i+1}",
                "name": f"救援队-{i+1}",
                "kind": "rescue_team",
                "capabilities": ["collapse", "water_rescue"][0:1],
                "speed_kmh": 60,
                "location": {"lon": 103.5 + 0.02 * i, "lat": 31.5 + 0.02 * i},
                "available": True,
            }
        )
    return {
        "incident": {
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "rescue",
            "coords": {"lon": 103.55, "lat": 31.52},
            "severity": 60,
            "hazards": ["collapse"],
            "victims_estimate": 10,
        },
        "units": units,
        "constraints": {"weather": "light_rain", "aftershock_risk": True},
        "max_teams": 2,
    }


def test_plan_recommend_basic() -> None:
    app = FastAPI()
    app.include_router(plan_router)
    client = TestClient(app)

    resp = client.post("/ai/plan/recommend", json=_req_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommend"] == "A"
    assert "A" in body["coas"]
    assert "B" in body["coas"]
    assert "C" in body["coas"]
    a = body["coas"]["A"]
    assert len(a["teams"]) == 2
    assert len(a["assignments"]) == 2
    factors = body["justification"]["factors"]
    assert factors
    assert any(item.get("coa") == "A" for item in factors)
    assert any(item.get("coa") == "B" for item in factors)


def test_plan_recommend_validation() -> None:
    app = FastAPI()
    app.include_router(plan_router)
    client = TestClient(app)

    bad = _req_payload()
    bad["units"] = []
    resp = client.post("/ai/plan/recommend", json=bad)
    assert resp.status_code == 200
    body = resp.json()
    assert body["explain_mode"] == "fallback"
    assert body["justification"]["summary"].startswith("未检测到可用救援单元")
    assert body["coas"]["A"]["teams"] == []
