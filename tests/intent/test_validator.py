from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from emergency_agents.intent.validator import validate_and_prompt_node, set_default_robotdog_id

set_default_robotdog_id(None)


def _mock_llm(response_text: str) -> MagicMock:
    """构造最小化的 LLM 返回对象。"""
    message = MagicMock()
    message.content = response_text
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


class TestValidatorHazardReport:
    """验证 hazard_report 的必填字段行为。"""

    def test_missing_event_type_falls_back_to_named_field(self) -> None:
        """缺少 event_type 时应提示具体字段，而非“未知字段”"""
        state: Dict[str, Any] = {
            "intent": {
                "intent_type": "hazard_report",
                "slots": {
                    "location": "四川省阿坝州茂县南新村（东经103.8507°、北纬31.7003°）",
                    "description": "山体滑坡，8人被困。",
                },
                "meta": {"need_confirm": True},
            },
            "validation_attempt": 0,
        }
        llm_client = _mock_llm("请补充灾害类型。")

        result = validate_and_prompt_node(state, llm_client, "glm-4.5-air")

        assert result["validation_status"] == "invalid"
        assert result["missing_fields"] == ["event_type"]
        assert "灾害类型" in result["prompt"]

    def test_complete_slots_pass_validation(self) -> None:
        """event_type 和 location 齐全时应直接通过"""
        state: Dict[str, Any] = {
            "intent": {
                "intent_type": "hazard_report",
                "slots": {
                    "event_type": "secondary_hazard",
                    "location": "四川省阿坝州茂县南新村（东经103.8507°、北纬31.7003°）",
                },
                "meta": {"need_confirm": False},
            }
        }
        llm_client = _mock_llm("无需补充。")

        result = validate_and_prompt_node(state, llm_client, "glm-4.5-air")

        assert result["validation_status"] == "valid"
        assert "missing_fields" not in result
        assert "prompt" not in result


class TestValidatorRescueTaskGenerate:
    """验证 rescue_task_generate 的必填字段行为。"""

    def test_missing_coordinates_and_summary(self) -> None:
        state: Dict[str, Any] = {
            "intent": {
                "intent_type": "rescue_task_generate",
                "slots": {
                    "mission_type": "rescue",
                    "location_name": "汶川南新村",
                },
                "meta": {"need_confirm": True},
            },
            "validation_attempt": 0,
        }
        llm_client = _mock_llm("请补充经纬度和现场情况。")

        result = validate_and_prompt_node(state, llm_client, "glm-4.5-air")

        assert result["validation_status"] == "invalid"
        missing = set(result["missing_fields"])
        assert {"coordinates", "situation_summary"} <= missing
        assert "经纬度" in result["prompt"]

    def test_complete_rescue_slots_pass_validation(self) -> None:
        state: Dict[str, Any] = {
            "intent": {
                "intent_type": "rescue_task_generate",
                "slots": {
                    "mission_type": "rescue",
                    "location_name": "汶川南新村",
                    "coordinates": {"lat": 31.68, "lng": 103.85},
                    "situation_summary": "汶川南新村教学楼倒塌，约12人被困，需要破拆救援。",
                },
                "meta": {"need_confirm": False},
            }
        }
        llm_client = _mock_llm("无需补充。")

        result = validate_and_prompt_node(state, llm_client, "glm-4.5-air")

        assert result["validation_status"] == "valid"
        assert "missing_fields" not in result
