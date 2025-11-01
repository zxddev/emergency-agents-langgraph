"""侦察网关辅助函数测试。"""

from __future__ import annotations

from datetime import datetime

from emergency_agents.external.recon_gateway import (
    _compute_deadline,
    _priority_to_int,
    _render_plan_summary,
    _select_task_type,
)
from emergency_agents.planner.recon_models import (
    ReconConstraint,
    ReconJustification,
    ReconPlan,
    ReconPlanMeta,
    ReconTask,
    GeoPoint,
)


def _sample_plan() -> ReconPlan:
    task = ReconTask(
        task_id="task-01",
        title="低空巡检",
        objective="确认泄漏范围",
        target_points=[GeoPoint(lon=103.8, lat=31.6)],
        recommended_devices=["drone-v-1"],
        duration_minutes=30,
    )
    return ReconPlan(
        objectives=["获取灾情精准态势"],
        sectors=[],
        tasks=[task],
        assets=[],
        constraints=[ReconConstraint(name="blocked_route", detail="国道 213 号受阻")],
        justification=ReconJustification(
            summary="基于危化关键词选择无人机巡检",
            evidence=[],
            reasoning_chain=[],
            risk_warnings=[],
        ),
        meta=ReconPlanMeta(),
    )


def test_render_plan_summary_contains_command_and_task():
    plan = _sample_plan()
    summary = _render_plan_summary(plan=plan, command_text="北侧危化泄漏侦察")
    assert "北侧危化泄漏侦察" in summary
    assert "低空巡检" in summary
    assert "blocked_route" in summary


def test_select_task_type_respects_phase():
    plan = _sample_plan()
    assert _select_task_type(plan.tasks[0]) == "uav_recon"


def test_priority_to_int_mapping():
    assert _priority_to_int("critical") == 90
    assert _priority_to_int("unknown") == 50


def test_compute_deadline_adds_minutes():
    task = _sample_plan().tasks[0]
    deadline = _compute_deadline(task)
    assert deadline is not None
    assert isinstance(deadline, datetime)
