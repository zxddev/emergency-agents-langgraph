from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from emergency_agents.api.reports import router as reports_router


@pytest.fixture(scope="module")
def test_app() -> TestClient:
    app = FastAPI()
    app.include_router(reports_router)
    return TestClient(app)


def _build_payload() -> Dict[str, Any]:
    now = datetime(2025, 10, 29, 8, 30)
    return {
        "basic": {
            "disaster_type": "地震灾害",
            "occurrence_time": now.isoformat(),
            "report_time": now.isoformat(),
            "location": "天一市川北县",
            "command_unit": "省消防救援总队前突指挥组",
            "frontline_overview": "县城西南 15 公里山地，持续降雨导致道路塌方。",
        },
        "casualties": {
            "affected_population": 13000,
            "deaths": 12,
            "missing": 5,
            "injured": 78,
            "emergency_evacuation": 4200,
            "emergency_resettlement": 3800,
            "urgent_life_support": 2600,
            "requiring_support": 1800,
            "casualty_notes": "仍有 4 个自然村通信中断，暂无法核实。",
        },
        "disruptions": {
            "road_blocked_villages": 11,
            "power_outage_villages": 14,
            "water_outage_villages": 9,
            "telecom_outage_villages": 7,
            "infrastructure_notes": "国道 213K+87 处桥梁断裂。",
        },
        "infrastructure": {
            "collapsed_buildings": 630,
            "severely_damaged_buildings": 1280,
            "mildly_damaged_buildings": 3560,
            "transport_damage": "三座桥梁损毁，两处滑坡阻断县道。",
            "communication_damage": "应急通信车已抵达但容量受限。",
            "energy_damage": "110kV 变电站停运，待抢修。",
            "water_facility_damage": "两处提灌站停运。",
            "public_service_damage": "县人民医院局部停电，启用备用电源。",
            "direct_economic_loss": 26800.0,
        },
        "agriculture": {
            "affected_area_ha": 1450.0,
            "ruined_area_ha": 820.0,
            "destroyed_area_ha": 310.0,
            "livestock_loss": "死亡牛羊 860 头只。",
        },
        "resources": {
            "deployed_forces": [
                {
                    "name": "国家综合性消防救援队伍第一支队",
                    "personnel": 186,
                    "equipment": "生命探测仪 12 套、破拆装备 18 套",
                    "tasks": "城区倒塌建筑破拆搜救。",
                },
                {
                    "name": "省地震局快速测震组",
                    "personnel": 24,
                    "equipment": "余震监测设备 6 台",
                    "tasks": "部署临时监测网。",
                },
            ],
            "air_support": "陆航旅直升机 2 架维持空投。",
            "medical_support": "省卫健委派出 60 人医疗队，两辆移动医院车。",
            "engineering_support": "武警工程部队 120 人正在抢通 213 国道。",
            "logistics_support": "前突组搭建 3 个野战补给点。",
        },
        "support_needs": {
            "reinforcement_forces": "请求调派空降兵侦察分队进入孤立乡镇。",
            "material_shortages": "急需移动通信基站 3 套、应急桥梁 2 套。",
            "infrastructure_requests": "请求调配大功率发电车 4 台保障县医院。",
        },
        "risk_outlook": {
            "aftershock_risk": "过去 12 小时记录余震 18 次，需警惕山体滑坡。",
            "meteorological_risk": "未来 24 小时仍有中到大雨。",
            "safety_measures": "对滑坡隐患点布控雷达监测，开展提前转移。",
        },
        "operations": {
            "completed_actions": "成功搜救 63 人，转运重伤员 41 人。",
            "ongoing_actions": "正在抢通国道 213 和县道 X034。",
            "pending_actions": "待指挥部批准增派无人机编队。",
        },
    }


def test_rescue_assessment_success(monkeypatch: pytest.MonkeyPatch, test_app: TestClient) -> None:
    class _FakeCompletions:
        def create(self, *args: Any, **kwargs: Any) -> Any:
            return type(
                "Resp",
                (),
                {
                    "choices": [
                        type("Choice", (), {"message": type("Msg", (), {"content": "# 汇报文本\n"})})
                    ]
                },
            )()

    class _FakeLLM:
        def __init__(self) -> None:
            self.chat = type("Chat", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr("emergency_agents.api.reports.get_openai_client", lambda _cfg: _FakeLLM())

    response = test_app.post("/reports/rescue-assessment", json=_build_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["report_text"].startswith("# 汇报文本")
    assert "死亡 12 人" in body["key_points"]
    assert "直接经济损失 26800.0 万元" in body["key_points"]


def test_rescue_assessment_llm_failure(monkeypatch: pytest.MonkeyPatch, test_app: TestClient) -> None:
    class _FailingCompletions:
        def create(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    class _FakeLLM:
        def __init__(self) -> None:
            self.chat = type("Chat", (), {"completions": _FailingCompletions()})()

    monkeypatch.setattr("emergency_agents.api.reports.get_openai_client", lambda _cfg: _FakeLLM())

    response = test_app.post("/reports/rescue-assessment", json=_build_payload())
    assert response.status_code == 502
    assert response.json()["detail"] == "模型生成失败，请稍后重试"


def test_rescue_assessment_validation_error(test_app: TestClient) -> None:
    payload = _build_payload()
    del payload["basic"]["location"]
    response = test_app.post("/reports/rescue-assessment", json=payload)
    assert response.status_code == 422
