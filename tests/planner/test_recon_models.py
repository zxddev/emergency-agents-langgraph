"""Recon 模型单元测试。"""

from __future__ import annotations

from typing import List

import pytest
from pydantic import ValidationError

from emergency_agents.planner.recon_models import (
    GeoPoint,
    ReconIntent,
    ReconContext,
    ReconDevice,
    ReconAgent,
    HazardSnapshot,
    ReconPlan,
    ReconTask,
    ReconAssetPlan,
    ReconSector,
    ReconJustification,
    ReconPlanMeta,
    ReconConstraint,
    TaskPlanPayload,
)


def _sample_points() -> List[GeoPoint]:
    return [
        GeoPoint(lon=103.82, lat=31.67),
        GeoPoint(lon=103.90, lat=31.70),
        GeoPoint(lon=103.85, lat=31.60),
    ]


def test_recon_intent_basic():
    intent = ReconIntent(
        event_id="evt-001",
        raw_text="侦察北侧危化品泄漏",
        target_spots=[GeoPoint(lon=103.82, lat=31.67)],
        risk_keywords=["chemical", "leak"],
        deadline_minutes=120,
    )
    assert intent.event_id == "evt-001"
    assert intent.priority.value == "high"
    assert len(intent.target_spots) == 1
    assert intent.deadline_minutes == 120


def test_recon_context_complete():
    context = ReconContext(
        event_id="evt-001",
        hazard=HazardSnapshot(hazard_type="chemical", severity="high"),
        available_devices=[ReconDevice(device_id="uav-01", environment="air")],
        available_agents=[ReconAgent(unit_id="team-01")],
        existing_tasks=["task-01"],
        blocked_routes=["road-23"],
        weather="rain",
    )
    assert context.hazard.hazard_type == "chemical"
    assert context.available_devices[0].device_id == "uav-01"
    assert context.blocked_routes == ["road-23"]


def test_recon_plan_structure():
    plan = ReconPlan(
        objectives=["识别危化泄漏范围"],
        sectors=[
            ReconSector(
                sector_id="sec-1",
                name="北区",
                area=_sample_points(),
                priority="critical",
                tasks=["task-recon-1"],
            )
        ],
        tasks=[
            ReconTask(
                task_id="task-recon-1",
                title="无人机巡检",
                objective="航拍侦察",
                target_points=_sample_points(),
                recommended_devices=["uav-01"],
            )
        ],
        assets=[
            ReconAssetPlan(
                asset_id="uav-01",
                asset_type="uav",
                usage="低空巡检",
                duration_minutes=30,
            )
        ],
        constraints=[
            ReconConstraint(name="no_fly", detail="禁飞区 500m 内不得进入", severity="critical")
        ],
        justification=ReconJustification(
            summary="选择无人机侦察以快速确定泄漏范围",
            evidence=["img://snap-1"],
            reasoning_chain=["危化泄漏优先定位"],
            risk_warnings=["注意风向"]
        ),
        meta=ReconPlanMeta(
            generated_by="ai",
            schema_version="v1",
            data_sources=["events", "devices"],
            missing_fields=[],
        ),
    )
    assert plan.meta.schema_version == "v1"
    assert plan.justification.summary.startswith("选择无人机")
    assert plan.tasks[0].recommended_devices == ["uav-01"]


def test_task_plan_payload_required():
    payload = TaskPlanPayload(
        scheme_id="scheme-001",
        task_id="task-recon-1",
        objective="航拍侦察",
        target_points=_sample_points(),
        required_capabilities=["thermal_imaging"],
        recommended_devices=["uav-01"],
        duration_minutes=30,
        dependencies=["task-prep-1"],
    )
    assert payload.scheme_id == "scheme-001"
    assert payload.dependencies == ["task-prep-1"]


def test_recon_task_validation_error():
    with pytest.raises(ValidationError):
        ReconTask(
            task_id="task-err",
            title="",
            objective="",
        )


def test_geo_point_validation():
    with pytest.raises(ValidationError):
        GeoPoint(lon=200.0, lat=0.0)
