"""侦察 LangGraph 编排测试。"""

from __future__ import annotations

from typing import List

import pytest

from emergency_agents.external.recon_gateway import ReconPlanDraft
from emergency_agents.graph.recon_app import build_recon_graph
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


class DummyPipeline:
    """替身流水线，用于验证 Graph 节点调用。"""

    def __init__(self) -> None:
        self.calls: List[str] = []
        self._task = ReconTask(
            task_id="task-graph-1",
            title="空中巡检",
            objective="确认泄漏范围",
            target_points=[GeoPoint(lon=103.8, lat=31.6)],
            recommended_devices=["drone-v-1"],
        )

    def build_plan(self, command_text: str, event_id: str) -> ReconPlan:
        self.calls.append(f"{event_id}:{command_text}")
        return ReconPlan(
            objectives=["精准识别危化泄漏"],
            sectors=[
                ReconSector(
                    sector_id="sec-graph-1",
                    name="北区",
                    area=[GeoPoint(lon=103.8, lat=31.6)],
                    tasks=[self._task.task_id],
                )
            ],
            tasks=[self._task],
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

    def build_task_payload(self, scheme_id: str, task: ReconTask) -> TaskPlanPayload:
        return TaskPlanPayload(
            scheme_id=scheme_id,
            task_id=task.task_id,
            objective=task.objective,
            target_points=task.target_points,
            recommended_devices=task.recommended_devices,
        )


class DummyGateway:
    """替身网关，只记录草稿生成请求。"""

    def __init__(self, pipeline: DummyPipeline) -> None:
        self.pipeline = pipeline
        self.calls: List[str] = []

    def prepare_plan_draft(
        self,
        *,
        event_id: str,
        command_text: str,
        plan: ReconPlan,
        pipeline: DummyPipeline,
    ) -> ReconPlanDraft:
        self.calls.append(f"{event_id}:{command_text}")
        payload = pipeline.build_task_payload(scheme_id="scheme-graph", task=plan.tasks[0])
        return ReconPlanDraft(
            summary="测试草稿",
            plan_payload=plan.model_dump(mode="json"),
            tasks_payload=[payload],
        )


def test_recon_graph_success_flow():
    pipeline = DummyPipeline()
    gateway = DummyGateway(pipeline)
    graph = build_recon_graph(pipeline=pipeline, gateway=gateway)

    result = graph.invoke({"event_id": "evt-1001", "command_text": "侦察北侧危化泄漏"})

    assert result["plan"].objectives == ["精准识别危化泄漏"]
    assert result["draft"].summary == "测试草稿"
    assert pipeline.calls == ["evt-1001:侦察北侧危化泄漏"]
    assert gateway.calls == ["evt-1001:侦察北侧危化泄漏"]


def test_recon_graph_missing_command_raises_error():
    pipeline = DummyPipeline()
    gateway = DummyGateway(pipeline)
    graph = build_recon_graph(pipeline=pipeline, gateway=gateway)

    with pytest.raises(ValueError):
        graph.invoke({"event_id": "evt-1001"})
