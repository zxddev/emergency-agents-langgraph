from __future__ import annotations

import pytest

from emergency_agents.control.models import DeviceType
from emergency_agents.external.device_directory import DeviceEntry
from emergency_agents.graph.scout_tactical_app import (
    DeviceSelectionOutcome,
    ScoutTacticalGraph,
    _evaluate_device_selection,
)
from emergency_agents.intent.handlers.scout_task_generation import ScoutTaskGenerationHandler


class _DummyDirectory:
    def __init__(self, entries: list[DeviceEntry]) -> None:
        self._entries = entries

    def list_entries(self) -> list[DeviceEntry]:
        return list(self._entries)


def _make_entry(device_id: str, device_type: DeviceType) -> DeviceEntry:
    return DeviceEntry(
        device_id=device_id,
        name=f"{device_type.value}-{device_id}",
        device_type=device_type,
        vendor=None,
    )


def test_evaluate_device_selection_full() -> None:
    directory = _DummyDirectory([_make_entry("uav-1", DeviceType.UAV)])
    outcome = _evaluate_device_selection(
        device_directory=directory,
        required_sensors=["visible_light_camera"],
        prefer_device_type=DeviceType.UAV,
    )
    assert outcome["status"] == "full"
    assert outcome["missingSensors"] == []
    assert outcome["usableDevices"]
    assert outcome["coverageSensors"] == ["camera"]


def test_evaluate_device_selection_partial() -> None:
    directory = _DummyDirectory([_make_entry("uav-1", DeviceType.UAV)])
    outcome = _evaluate_device_selection(
        device_directory=directory,
        required_sensors=["visible_light_camera", "gas_detector"],
        prefer_device_type=DeviceType.UAV,
    )
    assert outcome["status"] == "partial"
    assert outcome["missingSensors"] == ["gas_detector"]
    assert outcome["usableDevices"]
    assert outcome["coverageSensors"] == ["camera"]


def test_evaluate_device_selection_none() -> None:
    directory = _DummyDirectory([_make_entry("robotdog-1", DeviceType.ROBOTDOG)])
    outcome = _evaluate_device_selection(
        device_directory=directory,
        required_sensors=["sonar"],
        prefer_device_type=DeviceType.UAV,
    )
    assert outcome["status"] == "none"
    assert outcome["usableDevices"] == []


def test_execution_advice_contains_display() -> None:
    graph = object.__new__(ScoutTacticalGraph)
    # type: ignore[attr-defined] - 为单测注入所需属性
    graph._build_execution_advice  # noqa: B018  # 确认方法存在
    selection: DeviceSelectionOutcome = {
        "status": "partial",
        "missingSensors": ["gas_detector"],
        "coverageSensors": ["camera"],
        "devices": [],
        "usableDevices": [],
    }
    advice = ScoutTacticalGraph._build_execution_advice(graph, selection)  # type: ignore[misc]
    assert advice["missingDisplay"] != ""
    assert "气体" in advice["missingDisplay"] or "gas" in advice["missingDisplay"]


def test_compose_ui_actions_adds_warning() -> None:
    handler = ScoutTaskGenerationHandler(  # type: ignore[call-arg]
        risk_repository=None,
        device_directory=None,
        amap_client=None,
        orchestrator_client=None,
        postgres_dsn="",
        pool=None,
    )
    plan = {
        "targets": [],
        "riskHints": [],
        "executionAdvice": {
            "status": "partial",
            "missingDisplay": "气体检测",
            "missingSensors": ["gas_detector"],
        },
    }
    actions = handler._compose_ui_actions(plan, "incident-demo")
    warning_count = sum(1 for action in actions if action["action"] == "show_risk_warning")
    assert warning_count >= 1
