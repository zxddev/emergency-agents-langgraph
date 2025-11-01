from __future__ import annotations

import json
from typing import Any, Dict, List

from emergency_agents.agents.plan_generator import plan_generator_agent
from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.external.orchestrator_client import RescueScenarioPayload


class _FakeKGService:
    def get_equipment_requirements(self, disaster_types: List[str]) -> List[Dict[str, Any]]:
        return [
            {
                "display_name": "救援艇",
                "total_quantity": 4,
                "max_urgency": 1.0,
                "for_disasters": disaster_types,
                "category": "water_rescue",
            }
        ]


class _LLMMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _LLMChoice:
    def __init__(self, content: str) -> None:
        self.message = _LLMMessage(content)


class _LLMResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_LLMChoice(content)]


class _LLMCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **_: Any) -> _LLMResponse:
        return _LLMResponse(self._content)


class _LLMChat:
    def __init__(self, content: str) -> None:
        self.completions = _LLMCompletions(content)


class _FakeLLMClient:
    def __init__(self, content: str) -> None:
        self.chat = _LLMChat(content)


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.created: List[Any] = []
        self.scenarios: List[RescueScenarioPayload] = []

    def create_incident(self, payload: Any) -> Dict[str, Any]:
        self.created.append(payload)
        return {"incidentId": "incident-001", "title": payload.title}

    def publish_rescue_scenario(self, payload: RescueScenarioPayload) -> Dict[str, Any]:
        self.scenarios.append(payload)
        return {"status": "ok"}


def test_plan_generator_pushes_orchestrator() -> None:
    kg_service = _FakeKGService()
    llm_payload = json.dumps(
        {
            "primary_plan": {
                "name": "主救援方案",
                "priority": "P0",
                "phases": [{"phase": "初期响应", "tasks": ["勘察", "清障"]}],
                "objectives": ["保障生命安全"],
                "estimated_duration_hours": 12,
            },
            "alternative_plans": [
                {"name": "备选一号", "priority": "P1", "difference": "力量部署更集中"}
            ],
        }
    )
    llm_client = _FakeLLMClient(llm_payload)
    orchestrator = _FakeOrchestrator()

    initial_state: Dict[str, Any] = {
        "rescue_id": "rescue-123",
        "user_id": "commander-1",
        "timeline": [],
        "situation": {
            "disaster_type": "earthquake",
            "magnitude": 6.8,
            "affected_area": "测试城区",
            "epicenter": {"lng": 103.8, "lat": 30.7},
            "initial_casualties": {"estimated": 120},
        },
        "predicted_risks": [
            {"display_name": "山体滑坡", "type": "landslide", "probability": 0.7, "eta_hours": 2, "severity": "high"}
        ],
    }

    new_state = plan_generator_agent(
        state=initial_state,
        kg_service=kg_service,
        llm_client=llm_client,
        llm_model="test-model",
        orchestrator_client=orchestrator,
    )

    assert new_state["status"] == "awaiting_approval"
    assert new_state["plan"]["name"] == "主救援方案"
    incident_context = new_state.get("incident_context")
    assert isinstance(incident_context, dict)
    assert incident_context.get("incident_id") == RESCUE_DEMO_INCIDENT_ID
    assert len(orchestrator.created) == 0
    assert len(orchestrator.scenarios) == 1
