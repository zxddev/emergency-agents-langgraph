from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from emergency_agents.api._prompt_utils import resolve_missing_prompt
from emergency_agents.api.intent_processor import (
    Mem0Metrics,
    _handle_robotdog_control,
)
from emergency_agents.control.models import DeviceCommand
from emergency_agents.memory.conversation_manager import MessageRecord


class TestResolveMissingPrompt:
    """验证缺字段提示生成逻辑"""

    def test_prefers_llm_prompt(self) -> None:
        """只要LLM返回非空提示则直接复用"""
        prompt, source = resolve_missing_prompt(
            canonical_intent="hazard_report",
            prompt_text="请补充现场坐标。",
            missing_fields=["location"],
        )
        assert prompt == "请补充现场坐标。"
        assert source == "llm"

    @pytest.mark.parametrize(
        "canonical_intent,missing_fields,expected_keywords",
        [
            ("rescue_task_generate", ["mission_type", "location"], ["任务类型", "现场位置"]),
            ("hazard_report", ["event_type"], ["灾害类型"]),
            ("unknown_intent", [], ["缺失的信息"]),
        ],
    )
    def test_builds_fallback_prompt(
        self,
        canonical_intent: str,
        missing_fields: list[str],
        expected_keywords: list[str],
    ) -> None:
        """缺少LLM提示时，根据槽位字段生成兜底提示"""
        prompt, source = resolve_missing_prompt(
            canonical_intent=canonical_intent,
            prompt_text=None,
            missing_fields=missing_fields,
        )
        for keyword in expected_keywords:
            assert keyword in prompt
        assert source == "fallback"


@pytest.mark.asyncio
async def test_handle_robotdog_control_success() -> None:
    class _FakeVoiceGraph:
        async def ainvoke(self, state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "status": "dispatched",
                "device_command": DeviceCommand(
                    device_id=state.get("device_id", "dog-1"),
                    device_vendor="dqDog",
                    command_type="move",
                    params={"action": "forward"},
                ),
                "adapter_result": {"status": "success", "payload": {"code": 0}},
                "audit_trail": [{"event": "voice_control_command_built"}],
            }

    class _FakeMem:
        def __init__(self) -> None:
            self.contents: List[str] = []

        def add(
            self,
            *,
            content: str,
            user_id: str,
            run_id: Optional[str],
            metadata: Optional[Dict[str, Any]] = None,
            **_: Any,
        ) -> bool:
            self.contents.append(content)
            return True

    add_success = {"count": 0}

    metrics = Mem0Metrics(
        inc_search_success=lambda: None,
        inc_search_failure=lambda reason: None,
        observe_search_duration=lambda duration: None,
        inc_add_success=lambda: add_success.__setitem__("count", add_success["count"] + 1),
        inc_add_failure=lambda reason: None,
    )

    history_records: List[MessageRecord] = []

    async def _persist(content: str, intent_type: Optional[str]) -> MessageRecord:
        record = MessageRecord(
            id=len(history_records) + 1,
            conversation_id=1,
            role="assistant",
            content=content,
            intent_type=intent_type,
            event_time=datetime.utcnow(),
            metadata={},
        )
        return record

    result = await _handle_robotdog_control(
        intent={"intent_type": "device_control_robotdog", "slots": {"action": "forward", "device_id": "dog-1"}},
        slots_payload={"action": "forward", "device_id": "dog-1"},
        voice_control_graph=_FakeVoiceGraph(),
        thread_id="thread-1",
        router_state={"audit_log": []},
        persist_message=_persist,
        history_records=history_records,
        build_history=lambda records: [{"content": record.content} for record in records],
        user_id="user-1",
        incident_id="incident-1",
        mem=_FakeMem(),
        mem0_metrics=metrics,
        channel="voice",
        memory_hits=[],
    )

    assert result.status == "success"
    assert result.result["robotdog_control"]["status"] == "dispatched"
    assert add_success["count"] == 1


@pytest.mark.asyncio
async def test_handle_robotdog_control_unavailable() -> None:
    history_records: List[MessageRecord] = []

    async def _persist(content: str, intent_type: Optional[str]) -> MessageRecord:
        return MessageRecord(
            id=1,
            conversation_id=1,
            role="assistant",
            content=content,
            intent_type=intent_type,
            event_time=datetime.utcnow(),
            metadata={},
        )

    metrics = Mem0Metrics(
        inc_search_success=lambda: None,
        inc_search_failure=lambda reason: None,
        observe_search_duration=lambda duration: None,
        inc_add_success=lambda: None,
        inc_add_failure=lambda reason: None,
    )

    result = await _handle_robotdog_control(
        intent={"intent_type": "device_control_robotdog", "slots": {"action": "forward"}},
        slots_payload={"action": "forward"},
        voice_control_graph=None,
        thread_id="thread-2",
        router_state={"audit_log": []},
        persist_message=_persist,
        history_records=history_records,
        build_history=lambda records: [{"content": record.content} for record in records],
        user_id="user-2",
        incident_id="incident-2",
        mem=type("M", (), {"add": lambda *args, **kwargs: True})(),
        mem0_metrics=metrics,
        channel="voice",
        memory_hits=[],
    )

    assert result.status == "error"
    assert "语音控制子图未启用" in result.result["response_text"]
