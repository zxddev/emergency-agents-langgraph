from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from emergency_agents.api._prompt_utils import resolve_missing_prompt
from emergency_agents.api.intent_processor import (
    Mem0Metrics,
    _handle_robotdog_control,
    process_intent_core,
)
from emergency_agents.intent.schemas import GeneralChatSlots
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


@pytest.mark.asyncio
async def test_process_intent_core_passes_raw_text_and_messages() -> None:
    class _FakeConversationManager:
        def __init__(self) -> None:
            self._messages: List[MessageRecord] = []
            self._conversation_id = 1

        async def save_message(
            self,
            *,
            user_id: str,
            thread_id: str,
            role: str,
            content: str,
            intent_type: Optional[str],
            metadata: Optional[Dict[str, Any]] = None,
            conversation_metadata: Optional[Dict[str, Any]] = None,
        ) -> MessageRecord:
            record = MessageRecord(
                id=len(self._messages) + 1,
                conversation_id=self._conversation_id,
                role=role,
                content=content,
                intent_type=intent_type,
                event_time=datetime.utcnow(),
                metadata=dict(metadata or {}),
            )
            self._messages.append(record)
            return record

        async def get_history(self, thread_id: str, limit: int = 20) -> List[MessageRecord]:
            return list(self._messages[-limit:])

    class _FakeMem:
        def __init__(self) -> None:
            self.added: List[str] = []

        def search(self, **_: Any) -> List[Dict[str, Any]]:
            return []

        def add(
            self,
            *,
            content: str,
            user_id: str,
            run_id: Optional[str],
            metadata: Optional[Dict[str, Any]] = None,
            **__: Any,
        ) -> bool:
            self.added.append(content)
            return True

    class _FakeGraph:
        async def ainvoke(self, initial_state: Dict[str, Any], **_: Any) -> Dict[str, Any]:
            return {
                **initial_state,
                "intent": {"intent_type": "general-chat", "slots": {}},
                "router_next": "general-chat",
            }

    class _FakeHandler:
        def __init__(self) -> None:
            self.received_state: Dict[str, Any] | None = None
            self.received_slots: GeneralChatSlots | Dict[str, Any] | None = None

        async def handle(self, slots: GeneralChatSlots, state: Dict[str, object]) -> Dict[str, object]:
            self.received_state = dict(state)
            self.received_slots = slots
            return {
                "response_text": "已收到",
                "intent_type": "general-chat",
                "confidence": 1.0,
            }

    class _FakeRegistry:
        def __init__(self, mapping: Dict[str, Any]) -> None:
            self._mapping = mapping

        def get(self, key: str) -> Any | None:
            return self._mapping.get(key)

    manager = _FakeConversationManager()
    mem = _FakeMem()
    handler = _FakeHandler()
    registry = _FakeRegistry({"general-chat": handler})

    metrics = Mem0Metrics(
        inc_search_success=lambda: None,
        inc_search_failure=lambda reason: None,
        observe_search_duration=lambda duration: None,
        inc_add_success=lambda: None,
        inc_add_failure=lambda reason: None,
    )

    async def _build_history(records: List[MessageRecord]) -> List[Dict[str, Any]]:
        return [
            {"role": record.role, "content": record.content}
            for record in records
        ]

    result = await process_intent_core(
        user_id="user-1",
        thread_id="thread-raw-text",
        message="你是什么大模型",
        metadata={},
        manager=manager,  # type: ignore[arg-type]
        registry=registry,
        orchestrator_graph=_FakeGraph(),
        voice_control_graph=None,
        dialogue_graph=None,
        mem=mem,  # type: ignore[arg-type]
        build_history=_build_history,
        mem0_metrics=metrics,
        channel="voice",
        context_service=None,
        enable_mem0=False,
    )

    assert result.status == "success"
    assert isinstance(handler.received_slots, GeneralChatSlots)
    assert handler.received_state is not None
    assert handler.received_state.get("raw_text") == "你是什么大模型"
    assert handler.received_state.get("messages")
    last_message = handler.received_state["messages"][-1]
    assert isinstance(last_message, dict)
    assert last_message.get("content") == "你是什么大模型"
