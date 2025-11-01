from __future__ import annotations

from emergency_agents.planner.models import (
    EquipmentNeed,
    GeoPoint,
    MissionPhase,
    PlannedTask,
    ResourceCandidate,
)
from emergency_agents.planner.resource_matcher import ResourceMatcher


def test_matcher_assigns_best_resource() -> None:
    task = PlannedTask(
        task_id="rescue_primary",
        phase=MissionPhase.RESCUE,
        task_type="ground_rescue",
        required_capabilities=["collapse", "rope"],
        recommended_equipment=[EquipmentNeed(name="rope", quantity=2)],
        duration_minutes=30,
        dependencies=[],
        parallel_allowed=False,
    )
    candidates = [
        ResourceCandidate(
            resource_id="team_a",
            name="山地救援队A",
            kind="rescue_team",
            capabilities=["collapse", "rope"],
            equipment=["rope", "jack"],
            location=GeoPoint(lon=103.8, lat=31.6),
            availability=True,
        ),
        ResourceCandidate(
            resource_id="team_b",
            name="普通支援队",
            kind="rescue_team",
            capabilities=["logistics"],
            equipment=["water"],
            location=GeoPoint(lon=120.0, lat=30.0),
            availability=True,
        ),
    ]
    matcher = ResourceMatcher()
    result = matcher.match([task], candidates, incident_point=GeoPoint(lon=103.81, lat=31.61))
    assert not result.unmatched_tasks
    assert result.matches
    match = result.matches[0]
    assert match.resource_id == "team_a"
    assert match.capability_coverage == 1.0
