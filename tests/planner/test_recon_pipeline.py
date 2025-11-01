"""侦察规划流水线测试。"""

from __future__ import annotations

from typing import List

import pytest

from emergency_agents.planner.recon_models import (
    GeoPoint,
    HazardSnapshot,
    ReconAgent,
    ReconDevice,
)
from emergency_agents.planner.recon_pipeline import (
    ReconDataGateway,
    ReconPipeline,
    ReconPipelineConfig,
)
from emergency_agents.planner.recon_llm import (
    LLMJustification,
    LLMPlanBlueprint,
    LLMTaskBlueprint,
)


class DummyGateway(ReconDataGateway):
    def __init__(self) -> None:
        self._hazard = HazardSnapshot(hazard_type="chemical", severity="high")
        self._devices: List[ReconDevice] = [
            ReconDevice(
                device_id="uav-01",
                name="侦察无人机",
                category="uav",
                environment="air",
                capabilities=["thermal_imaging", "gas_detection"],
                endurance_minutes=45,
                location=GeoPoint(lon=103.82, lat=31.67),
            ),
            ReconDevice(
                device_id="robotdog-01",
                name="机器人犬",
                category="robot_dog",
                environment="land",
                capabilities=["close_inspection"],
                endurance_minutes=30,
                location=GeoPoint(lon=103.81, lat=31.66),
            ),
        ]
        self._agents = [
            ReconAgent(unit_id="team-01", name="前突侦察队", capabilities=["uav"]),
        ]
        self._blocked = ["road-101"]
        self._existing = []

    def fetch_hazard_snapshot(self, event_id: str) -> HazardSnapshot:
        return self._hazard

    def fetch_available_devices(self, event_id: str) -> List[ReconDevice]:
        return self._devices

    def fetch_available_agents(self, event_id: str) -> List[ReconAgent]:
        return self._agents

    def fetch_blocked_routes(self, event_id: str) -> List[str]:
        return self._blocked

    def fetch_existing_recon_tasks(self, event_id: str) -> List[str]:
        return self._existing


def _default_blueprint() -> LLMPlanBlueprint:
    return LLMPlanBlueprint(
        objectives=["确认危化泄漏范围"],
        tasks=[
            LLMTaskBlueprint(
                title="无人机巡检",
                objective="航拍确认chemical影响范围",
                mission_phase="recon",
                priority="critical",
                recommended_device="uav-01",
                target_points=[GeoPoint(lon=103.82, lat=31.67)],
                required_capabilities=["thermal_imaging", "gas_detection"],
                duration_minutes=40,
                safety_notes="注意风向与禁飞区",
            ),
            LLMTaskBlueprint(
                title="机器人犬近地侦察",
                objective="近地检查chemical次生风险",
                mission_phase="recon",
                priority="high",
                recommended_device="robotdog-01",
                target_points=[GeoPoint(lon=103.81, lat=31.66)],
                required_capabilities=["close_inspection"],
                duration_minutes=25,
            ),
        ],
        justification=LLMJustification(
            summary="根据危化险情安排空地协同侦察",
            reasoning_chain=["研判危化泄漏风险", "匹配空地装备能力", "编制侦察任务"],
            risk_warnings=["保持与泄漏区的安全距离"],
        ),
    )


class DummyLLMEngine:
    def __init__(self, blueprint: LLMPlanBlueprint) -> None:
        self._blueprint = blueprint
        self.calls = 0

    def generate_plan(self, *, intent, context) -> LLMPlanBlueprint:
        self.calls += 1
        return self._blueprint


def test_pipeline_build_plan():
    gateway = DummyGateway()
    llm_engine = DummyLLMEngine(_default_blueprint())
    pipeline = ReconPipeline(
        gateway=gateway,
        llm_engine=llm_engine,
        config=ReconPipelineConfig(default_deadline_minutes=120),
    )
    plan = pipeline.build_plan(command_text="北侧危化罐区泄漏, 103.82,31.67", event_id="evt-001")

    assert llm_engine.calls == 1
    assert plan.meta.schema_version == "v1"
    assert plan.objectives[0] == "确认危化泄漏范围"
    assert plan.constraints[0].name == "blocked_route"
    assert plan.justification.summary == "根据危化险情安排空地协同侦察"
    assert [task.task_id for task in plan.tasks] == ["recon-uav-01", "recon-robotdog-01"]

    payload = pipeline.build_task_payload(scheme_id="scheme-001", task=plan.tasks[0])
    assert payload.scheme_id == "scheme-001"
    assert payload.task_id == "recon-uav-01"


def test_pipeline_no_device_error():
    class EmptyGateway(DummyGateway):
        def fetch_available_devices(self, event_id: str) -> List[ReconDevice]:
            return []

    pipeline = ReconPipeline(
        gateway=EmptyGateway(),
        llm_engine=DummyLLMEngine(_default_blueprint()),
    )
    with pytest.raises(ValueError):
        pipeline.build_plan(command_text="紧急侦察", event_id="evt-err")


def test_pipeline_missing_target_points_error():
    class NoLocationGateway(DummyGateway):
        def __init__(self) -> None:
            super().__init__()
            for device in self._devices:
                device.location = None

    blueprint = LLMPlanBlueprint(
        objectives=["确认危化泄漏范围"],
        tasks=[
            LLMTaskBlueprint(
                title="无人机巡检",
                objective="航拍确认chemical影响范围",
                mission_phase="recon",
                priority="critical",
                recommended_device="uav-01",
                target_points=[],
                required_capabilities=["thermal_imaging"],
            )
        ],
        justification=LLMJustification(
            summary="缺少坐标无法规划",
            reasoning_chain=["尝试生成任务"],
            risk_warnings=[],
        ),
    )
    pipeline = ReconPipeline(
        gateway=NoLocationGateway(),
        llm_engine=DummyLLMEngine(blueprint),
    )
    with pytest.raises(ValueError):
        pipeline.build_plan(command_text="危化泄漏", event_id="evt-no-point")


def test_parse_intent_supports_compact_coordinates():
    gateway = DummyGateway()
    pipeline = ReconPipeline(gateway=gateway, llm_engine=DummyLLMEngine(_default_blueprint()))
    intent = pipeline._parse_intent(command_text="排查103.200,31.200", event_id="evt-compact")
    assert intent.target_spots
    assert intent.target_spots[0].lon == pytest.approx(103.200)
    assert intent.target_spots[0].lat == pytest.approx(31.200)


def test_pipeline_rejects_invalid_device():
    gateway = DummyGateway()
    blueprint = LLMPlanBlueprint(
        objectives=["确认危化泄漏范围"],
        tasks=[
            LLMTaskBlueprint(
                title="非法设备",
                objective="测试错误路径",
                mission_phase="recon",
                priority="critical",
                recommended_device="ghost-device",
                target_points=[GeoPoint(lon=103.82, lat=31.67)],
            )
        ],
        justification=LLMJustification(
            summary="错误示例",
            reasoning_chain=[],
            risk_warnings=[],
        ),
    )
    pipeline = ReconPipeline(gateway=gateway, llm_engine=DummyLLMEngine(blueprint))
    with pytest.raises(ValueError):
        pipeline.build_plan(command_text="北区危化泄漏", event_id="evt-ghost")


def test_pipeline_limits_objectives_and_points():
    gateway = DummyGateway()
    blueprint = LLMPlanBlueprint(
        objectives=[
            "目标1",
            "目标2",
            "目标3",
            "目标4",
        ],
        tasks=[
            LLMTaskBlueprint(
                title="多坐标任务",
                objective="覆盖多个点位",
                mission_phase="recon",
                priority="high",
                recommended_device="uav-01",
                target_points=[
                    GeoPoint(lon=103.0, lat=31.0),
                    GeoPoint(lon=103.1, lat=31.0),
                    GeoPoint(lon=103.2, lat=31.0),
                    GeoPoint(lon=103.3, lat=31.0),
                ],
                required_capabilities=["aerial_recon"],
            )
        ],
        justification=LLMJustification(
            summary="多目标示例",
            reasoning_chain=["示例"],
            risk_warnings=[],
        ),
    )
    pipeline = ReconPipeline(gateway=gateway, llm_engine=DummyLLMEngine(blueprint))
    plan = pipeline.build_plan(command_text="测试目标限制", event_id="evt-limit")

    assert plan.objectives[:3] == ["目标1", "目标2", "目标3"]  # 来自 LLM 的目标被限制为前 3 条
    assert len(plan.tasks[0].target_points) == 3  # 任务坐标最多保留 3 个
