from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
import importlib

try:
    importlib.import_module("langgraph.checkpoint.postgres.aio")
except ModuleNotFoundError:
    pytest.skip("langgraph checkpoint module unavailable", allow_module_level=True)

from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.graph.scout_tactical_app import build_scout_tactical_graph
from emergency_agents.intent.handlers.scout_task_generation import ScoutTaskGenerationHandler
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots


class _StubRiskRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.zones = [
            RiskZoneRecord(
                zone_id="zone-1",
                zone_name="化工园东侧",
                hazard_type="chemical_leak",
                severity=4,
                description="疑似有毒气体泄漏",
                geometry_geojson={"type": "Point", "coordinates": [120.0, 30.0]},
                properties={},
                valid_from=now - timedelta(hours=1),
                valid_until=now + timedelta(hours=2),
                created_at=now - timedelta(hours=1),
                updated_at=now,
            )
        ]

    async def list_active_zones(self) -> list[RiskZoneRecord]:
        return list(self.zones)


@pytest.mark.anyio
async def test_scout_handler_generates_plan() -> None:
    repository = _StubRiskRepository()
    graph = build_scout_tactical_graph(risk_repository=repository)  # type: ignore[arg-type]
    handler = ScoutTaskGenerationHandler(graph=graph)
    slots = ScoutTaskGenerationSlots(
        target_type="hazard",
        objective_summary="确认化工园泄漏范围",
    )
    state: Dict[str, Any] = {
        "user_id": "u1",
        "thread_id": "thread-1",
        "conversation_context": {"incident_id": "incident-1"},
    }
    result = await handler.handle(slots, state)
    plan = result["scout_plan"]
    assert plan["targets"], "需要侦察目标"
    assert plan["overview"]["riskSummary"]["total"] == 1
    ui_actions = result["ui_actions"]
    assert any(action["action"] == "show_risk_warning" for action in ui_actions)
