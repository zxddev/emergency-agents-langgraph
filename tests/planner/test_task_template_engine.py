from __future__ import annotations

from pathlib import Path

from emergency_agents.planner.hazard_loader import HazardPackLoader
from emergency_agents.planner.task_template_engine import TaskTemplateEngine


def _load_bridge_pack() -> tuple:
    base = (
        Path(__file__)
        .resolve()
        .parent.parent.parent
        / "src"
        / "emergency_agents"
        / "knowledge"
        / "hazard_packs"
    )
    loader = HazardPackLoader(base_path=base)
    pack = loader.load_pack("bridge_collapse")
    engine = TaskTemplateEngine()
    return pack, engine


def test_build_plan_returns_ordered_tasks() -> None:
    pack, engine = _load_bridge_pack()
    plan = engine.build_plan(pack, severity_score=72.0)
    assert plan.hazard_type == "bridge_collapse"
    assert plan.severity_label in {"high", "critical"}
    task_ids = [task.task_id for task in plan.tasks]
    assert len(task_ids) == len(set(task_ids)), "不允许重复任务ID"
    # 校验依赖顺序：依赖任务应先出现
    index_map = {task.task_id: idx for idx, task in enumerate(plan.tasks)}
    for task in plan.tasks:
        for dependency in task.dependencies:
            assert index_map[dependency] < index_map[task.task_id]
